import os
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select

from colorstack_ai.api.schemas import (
    ActivityResponse,
    EventDetailResponse,
    EventListItem,
    GuidanceCoverage,
    GuidanceMarker,
    GuidanceResponse,
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
    EventRequirementStateRecord,
    EventPlaybookRecord,
    EventRecord,
    ExtractedFactRecord,
    MessageProcessingStateRecord,
    MessageRecord,
    PlaybookRecord,
    PlaybookRequirementRecord,
    PipelineRunRecord,
    StateChangeRecord,
    TaskRecord,
    TaskStatusOverrideRecord,
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
        tasks = await self._task_responses()
        open_tasks = [task for task in tasks if task.status != "complete"]
        urgency_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        open_tasks.sort(
            key=lambda task: (
                urgency_order.get(task.priority, 4),
                task.owner_group != "mine",
                task.deadline == "TBD",
                task.task.casefold(),
            )
        )
        events = [await self._event_list_item(UUID(item.event_id)) for item in context.active_events]
        events = [item for item in events if item is not None]
        priorities = await self._latest_priorities(open_tasks)
        linked_task_ids = {item.task_id for item in priorities if item.task_id}
        for task in open_tasks:
            if len(priorities) >= 3:
                break
            if task.id not in linked_task_ids:
                priorities.append(self._task_priority(task, len(priorities)))
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
        event_tasks = await self._task_responses(context.tasks)
        division_readiness = self._division_readiness(event_tasks)
        return EventDetailResponse(
            **summary.model_dump(),
            sponsor=sponsor,
            assessment=assessment,
            requirements=requirements,
            owners=owners,
            key_dates=key_dates,
            blockers=blockers,
            recent_changes=recent_changes,
            division_readiness=division_readiness,
        )

    async def tasks(
        self,
        *,
        status: str | None = None,
        owner: str | None = None,
        event: str | None = None,
        urgency: str | None = None,
        division: str | None = None,
        phase: str | None = None,
        deadline: str | None = None,
    ) -> list[TaskResponse]:
        tasks = await self._task_responses()
        return [
            item
            for item in tasks
            if (status is None or item.status == status)
            and (owner is None or owner.casefold() in item.owner.casefold())
            and (event is None or event.casefold() in item.event.casefold())
            and (urgency is None or item.priority == urgency)
            and (division is None or (item.division or "").casefold() == division.casefold())
            and (phase is None or (item.event_phase or "").casefold() == phase.casefold())
            and (deadline is None or deadline.casefold() in item.deadline.casefold())
        ]

    async def update_task_status(
        self,
        task_id: UUID,
        status: str,
    ) -> TaskResponse | None:
        async with self._database.sessions.begin() as session:
            task = await session.get(TaskRecord, task_id)
            if task is None:
                return None
            session.add(
                TaskStatusOverrideRecord(
                    task_id=task_id,
                    status=status,
                    actor=os.getenv("VP_NAME", "Salman").strip() or "VP",
                )
            )
        return next(
            (item for item in await self._task_responses() if item.id == str(task_id)),
            None,
        )

    async def guidance(self) -> GuidanceResponse:
        tasks = await self._task_responses()
        open_tasks = [item for item in tasks if item.status != "complete"]
        urgency_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        open_tasks.sort(
            key=lambda item: (
                item.owner_group != "mine",
                urgency_order.get(item.priority, 4),
                item.deadline == "TBD",
                item.task.casefold(),
            )
        )

        do_now: list[GuidanceMarker] = []
        missing: list[GuidanceMarker] = []
        improve: list[GuidanceMarker] = []
        for item in open_tasks:
            if item.owner_group == "mine" or item.priority in {"critical", "high"}:
                do_now.append(
                    GuidanceMarker(
                        id=f"task-action-{item.id}",
                        category="action",
                        title=item.task,
                        reason=self._task_guidance_reason(item),
                        recommendation=item.next_step,
                        question=self._task_guidance_question(item),
                        urgency=item.priority,
                        event=None if item.event == "—" else item.event,
                        task_id=item.id,
                    )
                )
            if "No owner" in item.markers:
                missing.append(
                    GuidanceMarker(
                        id=f"task-owner-{item.id}",
                        category="missing",
                        title=f"Owner missing: {item.task}",
                        reason="No accountable owner is recorded.",
                        recommendation="Choose one person who owns the next step.",
                        question=f"Who is accountable for {item.task}?",
                        urgency="high",
                        event=None if item.event == "—" else item.event,
                        task_id=item.id,
                    )
                )
            if "No deadline" in item.markers:
                missing.append(
                    GuidanceMarker(
                        id=f"task-deadline-{item.id}",
                        category="missing",
                        title=f"Deadline missing: {item.task}",
                        reason="The work has no recorded due date, so it cannot be prioritized reliably.",
                        recommendation="Set a specific due date or explicitly defer it.",
                        question=f"When does {item.task} need to be complete?",
                        urgency="medium",
                        event=None if item.event == "—" else item.event,
                        task_id=item.id,
                    )
                )

        async with self._database.sessions() as session:
            requirement_rows = list(
                (
                    await session.execute(
                        select(
                            EventRequirementStateRecord,
                            PlaybookRequirementRecord.name,
                            EventRecord.canonical_name,
                        )
                        .join(
                            PlaybookRequirementRecord,
                            PlaybookRequirementRecord.id
                            == EventRequirementStateRecord.requirement_id,
                        )
                        .join(
                            EventRecord,
                            EventRecord.id == EventRequirementStateRecord.event_id,
                        )
                        .where(
                            EventRequirementStateRecord.status.in_(("missing", "blocked"))
                        )
                        .order_by(EventRequirementStateRecord.evaluated_at.desc())
                        .limit(12)
                    )
                ).all()
            )
            archived_messages = int(
                await session.scalar(
                    select(func.count()).select_from(MessageRecord).where(MessageRecord.is_deleted.is_(False))
                )
                or 0
            )
            reviewed_messages = int(
                await session.scalar(
                    select(func.count(func.distinct(MessageProcessingStateRecord.message_id)))
                )
                or 0
            )
            structured_facts = int(
                await session.scalar(
                    select(func.count()).select_from(ExtractedFactRecord).where(ExtractedFactRecord.active.is_(True))
                )
                or 0
            )
            latest_pipeline = await session.scalar(
                select(PipelineRunRecord).order_by(PipelineRunRecord.finished_at.desc()).limit(1)
            )

        for state, requirement_name, event_name in requirement_rows:
            missing.append(
                GuidanceMarker(
                    id=f"requirement-{state.event_id}-{state.requirement_id}",
                    category="missing",
                    title=str(requirement_name),
                    reason=state.rationale,
                    recommendation=state.recommendation or f"Confirm and document {requirement_name}.",
                    question=f"What is the current plan for {requirement_name} on {event_name}?",
                    urgency=state.urgency,
                    event=str(event_name),
                )
            )

        reviewed_percent = (
            round(reviewed_messages / archived_messages * 100, 1)
            if archived_messages
            else 100.0
        )
        if reviewed_messages < archived_messages:
            backlog = archived_messages - reviewed_messages
            improve.append(
                GuidanceMarker(
                    id="system-extraction-coverage",
                    category="improvement",
                    title="Complete the knowledge backlog",
                    reason=f"{backlog:,} archived messages have not been reviewed by the local extraction pipeline.",
                    recommendation="Keep the ingestion worker and Ollama running until coverage reaches 100%.",
                    question="Which channels or date ranges should be processed first?",
                    urgency="high" if reviewed_percent < 50 else "medium",
                )
            )
        if latest_pipeline is None:
            improve.append(
                GuidanceMarker(
                    id="system-pipeline-never-ran",
                    category="improvement",
                    title="Start continuous intelligence processing",
                    reason="No completed pipeline cycle is recorded.",
                    recommendation="Run the ColorStack worker continuously with the dashboard.",
                    question="Should processing prioritize the newest messages first?",
                    urgency="critical",
                )
            )
        elif datetime.now(UTC) - latest_pipeline.finished_at > timedelta(minutes=5):
            improve.append(
                GuidanceMarker(
                    id="system-pipeline-stale",
                    category="improvement",
                    title="Restore continuous processing",
                    reason="The latest pipeline cycle is more than five minutes old.",
                    recommendation="Restart the local worker and verify Ollama remains available.",
                    question="Did this Mac sleep or was the worker stopped?",
                    urgency="critical",
                )
            )

        return GuidanceResponse(
            generated_at=datetime.now(UTC),
            do_now=do_now[:6],
            missing=self._deduplicate_markers(missing)[:10],
            improve=improve[:5],
            coverage=GuidanceCoverage(
                archived_messages=archived_messages,
                reviewed_messages=reviewed_messages,
                reviewed_percent=reviewed_percent,
                structured_facts=structured_facts,
            ),
        )

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
        tasks = await self._task_responses(context.assigned_tasks)
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
        tasks = await self._task_responses(await self._retrieval.tasks(event_id=event_id))
        requirements = await self._retrieval.requirements(event_id)
        event_type = await self._event_type(event_id)
        owners = list(dict.fromkeys(item.owner for item in tasks if item.owner != "Unassigned"))
        owner_state = self._state_text(state.get("owner"))
        if owner_state:
            owners.insert(0, owner_state)
        blockers = [item for item in tasks if item.status == "waiting" or "Blocked" in item.markers]
        missing = [item for item in requirements if item.status in {"missing", "blocked", "in_progress"}]
        next_action = f"Resolve {missing[0].name}" if missing else "Review current event state"
        async with self._database.sessions() as session:
            event_record = await session.get(EventRecord, event_id)
        date_value = state.get("event_date_time")
        date_label = (
            event_record.authoritative_date.strftime("%b %d").replace(" 0", " ")
            if event_record and event_record.authoritative_date
            else self._deadline_label(date_value.value) if date_value else "TBD"
        )
        event_type = (
            str((event_record.source_evidence or {}).get("event_type", event_type)).replace("_", " ").title()
            if event_record and event_record.record_kind == "authoritative"
            else event_type
        )
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
            authoritative=bool(event_record and event_record.record_kind == "authoritative"),
            needs_clarification=bool(event_record and event_record.needs_clarification),
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

    async def _latest_priorities(
        self,
        open_tasks: list[TaskResponse],
    ) -> list[PriorityItem]:
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
        task_by_title = {task.task.strip().casefold(): task for task in open_tasks}
        for index, item in enumerate(raw[:3]):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "Priority"))
            task = task_by_title.get(title.strip().casefold())
            if task is None:
                continue
            results.append(
                PriorityItem(
                    id=f"brief-{index}",
                    title=title,
                    owner=str(item.get("owner_name") or item.get("owner_discord_id") or "Unassigned"),
                    due=self._iso_deadline_label(item.get("deadline")),
                    priority=str(item.get("urgency", "high")),
                    context=str(item.get("reason", "From the latest daily brief.")),
                    task_id=task.id,
                )
            )
        return results

    async def _task_responses(
        self,
        task_items: list[TaskContextItem] | None = None,
    ) -> list[TaskResponse]:
        overrides: dict[UUID, str] = {}
        async with self._database.sessions() as session:
            records = list(
                (
                    await session.scalars(
                        select(TaskStatusOverrideRecord).order_by(
                            TaskStatusOverrideRecord.created_at.desc(),
                            TaskStatusOverrideRecord.id.desc(),
                        )
                    )
                ).all()
            )
        for record in records:
            overrides.setdefault(record.task_id, record.status)
        items = task_items if task_items is not None else await self._retrieval.tasks()
        task_ids = [UUID(item.task_id) for item in items]
        async with self._database.sessions() as session:
            records = {
                record.id: record
                for record in (
                    await session.scalars(select(TaskRecord).where(TaskRecord.id.in_(task_ids)))
                ).all()
            } if task_ids else {}
        return [
            self._task_response(
                item,
                overrides.get(UUID(item.task_id)),
                records.get(UUID(item.task_id)),
            )
            for item in items
        ]

    def _task_response(
        self,
        item: TaskContextItem,
        status_override: str | None = None,
        record: TaskRecord | None = None,
    ) -> TaskResponse:
        raw_status = (status_override or item.status or "open").casefold()
        status = self._normalize_task_status(raw_status)
        priority = "critical" if status == "waiting" else "medium"
        deadline = self._deadline_datetime(item.deadline or {})
        if status != "complete" and deadline and deadline < datetime.now(UTC):
            priority = "critical"
        elif (
            status != "complete"
            and priority != "critical"
            and deadline
            and deadline <= datetime.now(UTC) + timedelta(days=7)
        ):
            priority = "high"
        source = item.sources[0].type if item.sources else "Current state"
        owner = item.owner_name or item.owner_discord_id or "Unassigned"
        deadline_label = self._deadline_label(item.deadline or {})
        markers: list[str] = []
        if status != "complete" and owner == "Unassigned":
            markers.append("No owner")
        if status != "complete" and deadline_label == "TBD":
            markers.append("No deadline")
        if status == "waiting":
            markers.append("Blocked")
        if deadline and deadline < datetime.now(UTC) and status != "complete":
            markers.append("Overdue")
        elif deadline and deadline <= datetime.now(UTC) + timedelta(days=7) and status != "complete":
            markers.append("Due soon")
        return TaskResponse(
            id=item.task_id,
            task=item.title,
            event_id=item.event_id,
            event=item.event_name or "—",
            owner=owner,
            owner_group="mine" if self._is_vp_owner(owner) else "execs",
            status=status,
            priority=priority,
            deadline=deadline_label,
            source=source,
            markers=markers,
            next_step=self._task_next_step(status, markers),
            manually_updated=status_override is not None,
            division=record.division if record else None,
            event_phase=record.event_phase if record else None,
            expected_result=record.expected_result if record else None,
            why_it_matters=record.why_it_matters if record else None,
            source_evidence=record.source_evidence if record else None,
            recommended=record.recommended if record else False,
            needs_clarification=(record.needs_clarification if record else False) or bool(markers),
        )

    @staticmethod
    def _normalize_task_status(status: str) -> str:
        if status in {"complete", "completed", "done", "cancelled"}:
            return "complete"
        if status in {"in_progress", "in progress", "started"}:
            return "in_progress"
        if status in {"blocked", "waiting", "on_hold", "on hold"}:
            return "waiting"
        return "open"

    @staticmethod
    def _is_vp_owner(owner: str) -> bool:
        vp_name = os.getenv("VP_NAME", "Salman").strip().casefold()
        return bool(vp_name) and vp_name in owner.casefold()

    @staticmethod
    def _task_next_step(status: str, markers: list[str]) -> str:
        if status == "complete":
            return "No action needed unless the completion evidence needs verification."
        if "Overdue" in markers:
            return "Reconfirm the deadline and finish, delegate, or explicitly reschedule it."
        if "Blocked" in markers:
            return "Identify the blocker owner and decide the unblock path."
        if "No owner" in markers:
            return "Assign one accountable owner."
        if "No deadline" in markers:
            return "Set a concrete due date or explicitly defer it."
        if status == "in_progress":
            return "Confirm the next concrete deliverable and checkpoint."
        return "Confirm ownership, deadline, and the first concrete step."

    @staticmethod
    def _task_guidance_reason(item: TaskResponse) -> str:
        if item.markers:
            return f"This task is marked: {', '.join(item.markers)}."
        return f"This is an open {item.priority}-priority task assigned to {item.owner}."

    @staticmethod
    def _task_guidance_question(item: TaskResponse) -> str:
        if "Blocked" in item.markers:
            return f"What decision or person would unblock {item.task}?"
        if "No owner" in item.markers:
            return f"Who should own {item.task}?"
        if "No deadline" in item.markers:
            return f"When should {item.task} be done?"
        return f"What is the next concrete step for {item.task}?"

    @staticmethod
    def _deduplicate_markers(items: list[GuidanceMarker]) -> list[GuidanceMarker]:
        seen: set[str] = set()
        results: list[GuidanceMarker] = []
        for item in items:
            key = item.title.casefold()
            if key not in seen:
                seen.add(key)
                results.append(item)
        return results

    def _task_priority(self, task: TaskResponse, index: int) -> PriorityItem:
        return PriorityItem(
            id=f"task-{task.id}-{index}",
            title=task.task,
            owner=task.owner,
            due=task.deadline,
            priority=task.priority,
            context=f"{task.event}; {task.source}",
            task_id=task.id,
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
    def _task_blocker(item: TaskContextItem | TaskResponse) -> str:
        blocker = getattr(item, "blocker", None)
        if blocker:
            detail = blocker.get("text") or blocker.get("value")
            if detail:
                return str(detail)
        title = getattr(item, "title", None) or getattr(item, "task", "Task")
        return f"{title} is blocked"

    @staticmethod
    def _division_readiness(tasks: list[TaskResponse]) -> list[dict[str, object]]:
        groups: dict[str, list[TaskResponse]] = {}
        for task in tasks:
            if task.division:
                groups.setdefault(task.division, []).append(task)
        results = []
        for division, items in sorted(groups.items()):
            complete = sum(item.status == "complete" for item in items)
            confirmed = sum(not item.recommended for item in items)
            results.append(
                {
                    "division": division,
                    "readiness": round(complete / len(items) * 100) if items else 0,
                    "complete": complete,
                    "total": len(items),
                    "confirmed": confirmed,
                    "needsClarification": sum(item.needs_clarification for item in items),
                }
            )
        return results

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
