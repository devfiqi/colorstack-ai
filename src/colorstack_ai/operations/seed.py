from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from colorstack_ai.db.models import EventAliasRecord, EventRecord, MessageRecord, TaskRecord
from colorstack_ai.db.session import Database
from colorstack_ai.state.resolution import EVENT_NAMESPACE, TASK_NAMESPACE, normalize_name


@dataclass(frozen=True)
class ConfirmedEvent:
    name: str
    date: datetime
    event_type: str
    aliases: tuple[str, ...]


CONFIRMED_EVENTS = (
    ConfirmedEvent(
        "Gen AI Event",
        # Store date-only commitments at local midnight in the chapter timezone.
        # The database connection renders timestamps in America/Chicago.
        datetime(2026, 10, 7, 5, tzinfo=UTC),
        "workshop",
        ("GenAI with Google", "Gen AI Workflow", "AI Workflow", "GenAI"),
    ),
    ConfirmedEvent(
        "Seagate Recruiting Panel",
        datetime(2026, 10, 13, 5, tzinfo=UTC),
        "career_panel",
        ("Seagate Recruiting 101", "Seagate panel", "Recruiting 101"),
    ),
    ConfirmedEvent(
        "SIBAT x ColorStack: Find the Imposter",
        datetime(2026, 10, 14, 5, tzinfo=UTC),
        "social",
        ("SIBAT x CStack", "Find the Imposter", "SIBAT collab"),
    ),
    ConfirmedEvent(
        "ColorStack Ideathon",
        datetime(2026, 10, 23, 5, tzinfo=UTC),
        "ideathon",
        ("ColorStack x SHPE Ideathon", "Olympics / Hackathon with SHPE", "Adobe Ideathon"),
    ),
    ConfirmedEvent(
        "NSBE Collab",
        datetime(2026, 10, 29, 23, 0, tzinfo=UTC),
        "networking",
        ("ColorStack x NSBE Shark Tank", "NSBE x CStack", "CSTACK x NSBE"),
    ),
)


WORK_BY_DIVISION = {
    "Executive leadership": {
        "before": ("Approve scope, decisions, and contingency plan", "A recorded go/no-go decision, scope, and escalation path."),
        "during": ("Own executive escalation and decision log", "Issues are resolved quickly with an accountable decision-maker."),
        "after": ("Review outcomes and approve follow-up priorities", "Leadership has a clear post-event decision record."),
    },
    "Event coordinators": {
        "before": ("Confirm venue, registration, staffing, materials, and run of show", "The event can operate on a verified plan."),
        "during": ("Run check-in, staffing handoffs, issue escalation, and cleanup", "Attendees experience a coordinated event."),
        "after": ("Document attendance, incidents, and postmortem actions", "Lessons and operational records are retained."),
    },
    "Public relations and marketing": {
        "before": ("Publish promotion plan, flyer, RSVP messaging, and reminders", "The intended audience knows what, when, and how to attend."),
        "during": ("Capture approved photos, content, and live updates", "The chapter has usable event content and accurate messaging."),
        "after": ("Publish recap, photos, and attendee follow-up messaging", "The event closes with clear communications and reusable content."),
    },
    "Outreach and partnerships": {
        "before": ("Confirm partner roles, speaker commitments, and contact plan", "Partners know their responsibilities and decision points."),
        "during": ("Support partners, speakers, and relationship handoffs", "External guests have a reliable point of contact."),
        "after": ("Send partner thank-yous, outcomes, and next-step follow-up", "Relationships are strengthened while evidence is preserved."),
    },
    "Treasury": {
        "before": ("Confirm budget, funding, purchases, and reimbursement path", "Spending is approved and no critical cost is unowned."),
        "during": ("Track purchases, receipts, and budget exceptions", "Financial decisions remain auditable in real time."),
        "after": ("Reconcile receipts, reimbursements, and final spend", "The event budget is closed accurately."),
    },
    "Academic or career programming": {
        "before": ("Finalize learning objectives, content, speakers, and participant materials", "The program delivers its promised academic or career value."),
        "during": ("Support program flow, speakers, questions, and participant experience", "Program delivery stays useful and on schedule."),
        "after": ("Collect feedback, outcomes, and program improvements", "Future programming is improved with evidence."),
    },
    "Secretary and operations": {
        "before": ("Maintain planning notes, approvals, decision log, and contact list", "The team works from one current operational record."),
        "during": ("Record decisions, attendance, incidents, and follow-ups", "Key operational facts do not get lost during delivery."),
        "after": ("Archive notes, files, metrics, and postmortem decisions", "The chapter retains a complete event record."),
    },
    "IT and automation": {
        "before": ("Prepare registration, check-in, data capture, and AV contingency", "Systems support reliable attendance and program delivery."),
        "during": ("Support AV, check-in systems, attendance capture, and incident triage", "Technical failures are visible and recoverable."),
        "after": ("Export metrics, secure records, and document technical lessons", "Event data is available for reporting without exposing raw data."),
    },
}


class AuthoritativeEventSeeder:
    """Seeds VP-confirmed events without treating recommendations as facts."""

    def __init__(self, database: Database) -> None:
        self._database = database

    async def seed(self) -> dict[str, int]:
        guild_id = await self._guild_id()
        event_count = 0
        task_count = 0
        async with self._database.sessions.begin() as session:
            for definition in CONFIRMED_EVENTS:
                event_id = uuid5(EVENT_NAMESPACE, f"{guild_id}:{normalize_name(definition.name)}")
                event = await session.get(EventRecord, event_id)
                if event is None:
                    event = EventRecord(
                        id=event_id,
                        guild_id=guild_id,
                        canonical_name=definition.name,
                        normalized_name=normalize_name(definition.name),
                    )
                    session.add(event)
                    event_count += 1
                event.record_kind = "authoritative"
                event.authoritative_date = definition.date
                event.date_confidence = "confirmed"
                event.needs_clarification = False
                event.source_evidence = {
                    "kind": "VP-confirmed record",
                    "detail": f"Confirmed date: {definition.date.date().isoformat()}",
                    "event_type": definition.event_type,
                }
                for alias in (definition.name, *definition.aliases):
                    normalized = normalize_name(alias)
                    exists = await session.scalar(
                        select(EventAliasRecord.id).where(
                            EventAliasRecord.guild_id == guild_id,
                            EventAliasRecord.normalized_alias == normalized,
                        )
                    )
                    if exists is None:
                        session.add(
                            EventAliasRecord(
                                guild_id=guild_id,
                                event_id=event_id,
                                alias=alias,
                                normalized_alias=normalized,
                            )
                        )
                for division, phases in WORK_BY_DIVISION.items():
                    for phase, (action, expected_result) in phases.items():
                        created = await self._ensure_recommended_task(
                            session=session,
                            guild_id=guild_id,
                            event=event,
                            division=division,
                            phase=phase,
                            action=action,
                            expected_result=expected_result,
                        )
                        task_count += int(created)
        return {"events_created": event_count, "recommended_tasks_created": task_count}

    async def _guild_id(self) -> str:
        async with self._database.sessions() as session:
            guild_ids = list(
                (await session.scalars(select(MessageRecord.guild_id).distinct())).all()
            )
        if len(guild_ids) != 1 or guild_ids[0] is None:
            raise RuntimeError("Authoritative seeding requires exactly one archived Discord guild.")
        return guild_ids[0]

    async def _ensure_recommended_task(
        self,
        *,
        session: AsyncSession,
        guild_id: str,
        event: EventRecord,
        division: str,
        phase: str,
        action: str,
        expected_result: str,
    ) -> bool:
        task_id = uuid5(TASK_NAMESPACE, f"{guild_id}:{event.id}:{division}:{phase}:{action}")
        task = await session.get(TaskRecord, task_id)
        if task is not None:
            return False
        session.add(
            TaskRecord(
                id=task_id,
                guild_id=guild_id,
                event_id=event.id,
                canonical_title=action,
                normalized_title=normalize_name(f"{division} {phase} {action}"),
                task_kind="playbook_recommendation",
                division=division,
                event_phase=phase,
                expected_result=expected_result,
                why_it_matters="Recommended operating work; confirm the owner, deadline, and applicability before treating it as a commitment.",
                source_evidence={
                    "kind": "Playbook recommendation",
                    "detail": "Generated from the ColorStack event operating plan; no source conversation confirms this work yet.",
                },
                recommended=True,
                needs_clarification=True,
            )
        )
        return True
