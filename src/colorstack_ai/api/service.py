from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select

from colorstack_ai.api.schemas import (
    ActivityResponse,
    EventDetailResponse,
    EventListItem,
    OverviewResponse,
    PersonResponse,
    PlaybookResponse,
    PriorityItem,
    RequirementResponse,
    TaskResponse,
)
from colorstack_ai.context.builder import ContextBuilder
from colorstack_ai.context.models import ContextLimits, EventContext, TaskContextItem
from colorstack_ai.context.retrieval import RetrievalService
from colorstack_ai.db.models import (
    DailyBriefRunRecord,
    EventPlaybookRecord,
    EventRecord,
    PlaybookRecord,
    PlaybookRequirementRecord,
    StateChangeRecord,
    TaskRecord,
)
from colorstack_ai.db.session import Database


class DashboardService:
    def __init__(self, database: Database, *, limits: ContextLimits) -> None:
        self._database = database
        self._retrieval = RetrievalService(database)
        self._context = ContextBuilder(self._retrieval, limits)

    async def overview(self) -> OverviewResponse:
        package = await self._context.organization(query="dashboard overview")
        context = package.context
        if context is None or context.kind != "organization":
            raise RuntimeError("Organization context was not available.")
        tasks = await self._retrieval.tasks()
        open_tasks = [task for task in tasks if task.status not in {"completed", "cancelled"}]
        events = [await self._event_list_item(UUID(item.event_id)) for item in context.active_events]
        events = [item for item in events if item is not None]
        priorities = await self._latest_priorities()
        if not priorities:
            priorities = [self._task_priority(task, index) for index, task in enumerate(open_tasks[:3])]
        week_end = datetime.now(UTC) + timedelta(days=7)
        deadlines_this_week = sum(
            1
            for deadline in context.upcoming_deadlines
            if (value := self._deadline_datetime(deadline.deadline)) is not None
            and datetime.now(UTC) <= value <= week_end
        )
        attention = [
            {
                "event": item.event_name or "Organization",
                "issue": item.name,
                "tone": "critical" if item.urgency == "critical" else "warning",
            }
            for item in context.critical_requirements[:5]
        ]
        changes = [
            {
                "change": self._change_message(item.field, item.previous_value, item.new_value),
                "event": await self._entity_name(item.entity_type, item.entity_id),
                "time": self._relative_time(item.effective_at),
            }
            for item in context.recent_changes[:5]
        ]
        return OverviewResponse(
            generated_at=context.generated_at,
            active_events=len(context.active_events),
            high_priority=len(context.high_urgency_events),
            open_tasks=len(open_tasks),
            deadlines_this_week=deadlines_this_week,
            priorities=priorities[:3],
            events=events,
            attention=attention,
            changes=changes,
        )

    async def events(self) -> list[EventListItem]:
        async with self._database.sessions() as session:
            ids = list((await session.scalars(select(EventRecord.id))).all())
        items = [await self._event_list_item(event_id) for event_id in ids]
        return sorted(
            [item for item in items if item is not None],
            key=lambda item: ({"critical": 0, "high": 1, "medium": 2, "low": 3}.get(item.urgency, 4), item.name),
        )

    async def event(self, event_id: UUID) -> EventDetailResponse | None:
        try:
            package = await self._context.event(event_id)
        except ValueError:
            return None
        context = package.context
        if not isinstance(context, EventContext):
            return None
        summary = await self._event_list_item(event_id)
        if summary is None:
            return None
        owner_by_requirement = {
            requirement.name: "Unassigned" for requirement in context.requirements
        }
        requirements = [
            RequirementResponse(
                id=item.requirement_id,
                label=item.name,
                group=item.playbook.replace("-", " ").title(),
                status=item.status,
                owner=owner_by_requirement[item.name],
                urgency=item.urgency,
                source=(
                    f"Discord message {item.evidence[0].source_message_id}"
                    if item.evidence and item.evidence[0].source_message_id
                    else "Playbook evaluation"
                ),
                detail=item.rationale,
            )
            for item in context.requirements
        ]
        owners = [
            {
                "name": str(item.get("name") or item.get("discord_id") or "Unknown"),
                "scope": "Event or linked task owner",
            }
            for item in context.owners
        ]
        key_dates = [
            {"label": item.entity_name, "date": self._deadline_label(item.deadline)}
            for item in context.deadlines
        ]
        blockers = [self._task_blocker(item) for item in context.blockers]
        recent_changes = [
            {
                "id": item.change_id,
                "field": item.field,
                "message": self._change_message(item.field, item.previous_value, item.new_value),
                "time": item.effective_at.isoformat(),
            }
            for item in context.recent_changes
        ]
        sponsor = self._state_text(context.current_state.get("sponsor"))
        assessment = self._assessment(context)
        return EventDetailResponse(
            **summary.model_dump(),
            sponsor=sponsor,
            assessment=assessment,
            requirements=requirements,
            owners=owners,
            key_dates=key_dates,
            blockers=blockers,
            recent_changes=recent_changes,
        )

    async def tasks(
        self,
        *,
        status: str | None = None,
        owner: str | None = None,
        event: str | None = None,
        urgency: str | None = None,
    ) -> list[TaskResponse]:
        tasks = [self._task_response(item) for item in await self._retrieval.tasks()]
        return [
            item
            for item in tasks
            if (status is None or item.status == status)
            and (owner is None or owner.casefold() in item.owner.casefold())
            and (event is None or event.casefold() in item.event.casefold())
            and (urgency is None or item.priority == urgency)
        ]

    async def people(self) -> list[PersonResponse]:
        tasks = await self._retrieval.tasks()
        identities: dict[str, str] = {}
        for task in tasks:
            if task.owner_discord_id:
                identities[task.owner_discord_id] = task.owner_name or task.owner_discord_id
        people = []
        for person_id, name in sorted(identities.items(), key=lambda item: item[1]):
            person = await self.person(person_id)
            if person is not None:
                people.append(person)
        return people

    async def person(self, person_id: str) -> PersonResponse | None:
        package = await self._context.person(person_id)
        context = package.context
        if context is None or context.kind != "person":
            return None
        name = context.name or person_id
        tasks = [self._task_response(item) for item in context.assigned_tasks]
        unresolved = [
            item.value or item.task or "Unresolved commitment"
            for item in context.commitments
            if item.status not in {"completed", "cancelled"}
        ]
        return PersonResponse(
            id=person_id,
            name=name,
            role=context.role or "Role not recorded",
            active_tasks=sum(1 for item in tasks if item.status not in {"complete", "completed"}),
            owned_events=[item.name for item in context.owned_events],
            unresolved=list(dict.fromkeys(unresolved)),
            tasks=tasks,
        )

    async def activity(self, *, hours: int = 48) -> list[ActivityResponse]:
        since = datetime.now(UTC) - timedelta(hours=hours)
        async with self._database.sessions() as session:
            records = list(
                (
                    await session.scalars(
                        select(StateChangeRecord)
                        .where(StateChangeRecord.effective_at >= since)
                        .order_by(StateChangeRecord.effective_at.desc())
                        .limit(100)
                    )
                ).all()
            )
        results = []
        for record in records:
            kind = "assignment" if record.field == "owner" else "change"
            results.append(
                ActivityResponse(
                    id=str(record.id),
                    time=record.effective_at.astimezone().strftime("%-I:%M %p"),
                    day="Today" if record.effective_at.date() == datetime.now(UTC).date() else "Yesterday",
                    event=await self._entity_name(record.entity_type, str(record.entity_id)),
                    kind=kind,
                    message=self._change_message(record.field, record.previous_value, record.new_value),
                )
            )
        return results

    async def latest_brief(self) -> dict[str, object] | None:
        async with self._database.sessions() as session:
            record = await session.scalar(
                select(DailyBriefRunRecord)
                .where(DailyBriefRunRecord.brief_payload.is_not(None))
                .order_by(DailyBriefRunRecord.created_at.desc())
                .limit(1)
            )
        if record is None or record.brief_payload is None:
            return None
        return {
            "runId": str(record.id),
            "status": record.status,
            "generated": record.completed_at or record.started_at,
            "brief": record.brief_payload,
            "renderedText": record.rendered_text,
            "messageIds": record.discord_message_ids,
        }

    async def playbooks(self) -> list[PlaybookResponse]:
        async with self._database.sessions() as session:
            books = list(
                (
                    await session.scalars(
                        select(PlaybookRecord)
                        .where(PlaybookRecord.active.is_(True))
                        .order_by(PlaybookRecord.name)
                    )
                ).all()
            )
            requirements = list(
                (
                    await session.scalars(select(PlaybookRequirementRecord))
                ).all()
            )
        by_book: dict[UUID, list[PlaybookRequirementRecord]] = {}
        for item in requirements:
            by_book.setdefault(item.playbook_id, []).append(item)
        return [
            PlaybookResponse(
                id=str(book.id),
                name=book.name,
                required=[item.name for item in by_book.get(book.id, []) if item.required],
                optional=[item.name for item in by_book.get(book.id, []) if not item.required],
                lead_time=self._lead_time(by_book.get(book.id, [])),
            )
            for book in books
        ]

    async def _event_list_item(self, event_id: UUID) -> EventListItem | None:
        summary = await self._retrieval.latest_event_summary(event_id)
        if summary is None:
            return None
        state = await self._retrieval.state_values(entity_type="event", entity_id=event_id)
        tasks = await self._retrieval.tasks(event_id=event_id)
        requirements = await self._retrieval.requirements(event_id)
        event_type = await self._event_type(event_id)
        owners = list(dict.fromkeys(item.owner_name for item in tasks if item.owner_name))
        owner_state = self._state_text(state.get("owner"))
        if owner_state:
            owners.insert(0, owner_state)
        blockers = [item for item in tasks if item.status == "blocked" or item.blocker]
        missing = [item for item in requirements if item.status in {"missing", "blocked", "in_progress"}]
        next_action = f"Resolve {missing[0].name}" if missing else "Review current event state"
        date_value = state.get("event_date_time")
        date_label = self._deadline_label(date_value.value) if date_value else "TBD"
        return EventListItem(
            id=str(event_id),
            name=summary.name,
            date=date_label,
            type=event_type,
            phase="completed" if summary.status == "completed" else "upcoming",
            readiness=round(summary.readiness or 0),
            urgency=summary.urgency or "low",
            owner=" / ".join(owners) or "Unassigned",
            blocker=self._task_blocker(blockers[0]) if blockers else "—",
            next_action=next_action,
        )

    async def _event_type(self, event_id: UUID) -> str:
        async with self._database.sessions() as session:
            value = await session.scalar(
                select(PlaybookRecord.event_type)
                .join(EventPlaybookRecord, EventPlaybookRecord.playbook_id == PlaybookRecord.id)
                .where(EventPlaybookRecord.event_id == event_id, PlaybookRecord.is_overlay.is_(False))
                .limit(1)
            )
        return (value or "Unknown").replace("_", " ").title()

    async def _entity_name(self, entity_type: str, entity_id: str) -> str:
        model = EventRecord if entity_type == "event" else TaskRecord
        field = EventRecord.canonical_name if entity_type == "event" else TaskRecord.canonical_title
        async with self._database.sessions() as session:
            value = await session.scalar(select(field).where(model.id == UUID(entity_id)))
        return value or "Organization"

    async def _latest_priorities(self) -> list[PriorityItem]:
        brief = await self.latest_brief()
        if not brief:
            return []
        payload = brief.get("brief")
        if not isinstance(payload, dict):
            return []
        raw = payload.get("top_priorities")
        if not isinstance(raw, list):
            return []
        results = []
        for index, item in enumerate(raw[:3]):
            if not isinstance(item, dict):
                continue
            results.append(
                PriorityItem(
                    id=f"brief-{index}",
                    title=str(item.get("title", "Priority")),
                    owner=str(item.get("owner_name") or item.get("owner_discord_id") or "Unassigned"),
                    due=self._iso_deadline_label(item.get("deadline")),
                    priority=str(item.get("urgency", "high")),
                    context=str(item.get("reason", "From the latest daily brief.")),
                )
            )
        return results

    def _task_response(self, item: TaskContextItem) -> TaskResponse:
        priority = "critical" if item.status == "blocked" else "medium"
        deadline = self._deadline_datetime(item.deadline or {})
        if priority != "critical" and deadline and deadline <= datetime.now(UTC) + timedelta(days=7):
            priority = "high"
        source = item.sources[0].type if item.sources else "Current state"
        status = "waiting" if item.status == "blocked" else (item.status or "open")
        if status == "completed":
            status = "complete"
        return TaskResponse(
            id=item.task_id,
            task=item.title,
            event_id=item.event_id,
            event=item.event_name or "—",
            owner=item.owner_name or item.owner_discord_id or "Unassigned",
            owner_group="execs",
            status=status,
            priority=priority,
            deadline=self._deadline_label(item.deadline or {}),
            source=source,
        )

    def _task_priority(self, item: TaskContextItem, index: int) -> PriorityItem:
        task = self._task_response(item)
        return PriorityItem(
            id=f"task-{item.task_id}-{index}",
            title=item.title,
            owner=task.owner,
            due=task.deadline,
            priority=task.priority,
            context=f"{task.event}; {task.source}",
        )

    @staticmethod
    def _assessment(context: EventContext) -> str:
        gaps = [item.name for item in context.requirements if item.status in {"missing", "blocked"}]
        if gaps:
            return f"{context.name} needs attention on {', '.join(gaps[:3])}."
        return f"{context.name} has no currently detected critical requirement gaps."

    @staticmethod
    def _state_text(item: object | None) -> str | None:
        value = getattr(item, "value", None)
        if not isinstance(value, dict):
            return None
        for key in ("name", "text", "value"):
            if isinstance(value.get(key), str):
                return value[key]
        return None

    @staticmethod
    def _task_blocker(item: TaskContextItem) -> str:
        if item.blocker:
            detail = item.blocker.get("text") or item.blocker.get("value")
            if detail:
                return str(detail)
        return f"{item.title} is blocked"

    @staticmethod
    def _deadline_datetime(value: dict[str, object]) -> datetime | None:
        raw = value.get("normalized")
        if not isinstance(raw, str):
            return None
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            return None

    @classmethod
    def _deadline_label(cls, value: dict[str, object]) -> str:
        parsed = cls._deadline_datetime(value)
        if parsed:
            return parsed.strftime("%b %d").replace(" 0", " ")
        return str(value.get("text") or "TBD")

    @staticmethod
    def _iso_deadline_label(value: object) -> str:
        if not isinstance(value, str):
            return "No deadline"
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%b %d").replace(" 0", " ")
        except ValueError:
            return value

    @staticmethod
    def _payload_text(value: dict[str, object] | None) -> str:
        if not value:
            return "unknown"
        return str(value.get("text") or value.get("name") or value.get("value") or value)

    @classmethod
    def _change_message(
        cls,
        field: str,
        previous: dict[str, object] | None,
        current: dict[str, object],
    ) -> str:
        before = cls._payload_text(previous)
        after = cls._payload_text(current)
        return f"{field.replace('_', ' ').title()}: {before} → {after}"

    @staticmethod
    def _relative_time(value: datetime) -> str:
        if value.date() == datetime.now(UTC).date():
            return value.astimezone().strftime("%-I:%M %p")
        return "Yesterday"

    @staticmethod
    def _lead_time(items: list[PlaybookRequirementRecord]) -> str:
        days = max((item.ideal_lead_days or 0 for item in items), default=0)
        return f"{days} days" if days else "Not specified"
