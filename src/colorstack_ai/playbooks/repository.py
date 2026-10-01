from datetime import UTC, datetime
from uuid import UUID, uuid5

from sqlalchemy import delete, or_, select, update

from colorstack_ai.db.models import (
    CurrentStateValueRecord,
    EventAliasRecord,
    EventPlaybookRecord,
    EventRecord,
    ExtractedFactRecord,
    FactReconciliationStateRecord,
    PlaybookRecord,
    PlaybookRequirementRecord,
    ReconciliationRunRecord,
    RequirementDependencyRecord,
    RequirementEvaluationRecord,
    RequirementEvaluationRunRecord,
    EventRequirementStateRecord,
    TaskRecord,
)
from colorstack_ai.db.session import Database
from colorstack_ai.playbooks.loader import PlaybookError, definition_hash
from colorstack_ai.playbooks.models import (
    DetectedPlaybook,
    EventSnapshot,
    PlaybookDefinition,
    ReadinessSummary,
    StateEvidence,
    TaskSnapshot,
)

PLAYBOOK_NAMESPACE = UUID("b4149a63-91c2-43b0-b35f-23b2428481fc")
REQUIREMENT_NAMESPACE = UUID("a439453a-7d86-4fd2-8944-67e928739682")


def playbook_id(definition: PlaybookDefinition) -> UUID:
    return uuid5(
        PLAYBOOK_NAMESPACE,
        f"{definition.key}:{definition.version}",
    )


def requirement_id(
    definition: PlaybookDefinition,
    requirement_key: str,
) -> UUID:
    return uuid5(
        REQUIREMENT_NAMESPACE,
        f"{definition.key}:{definition.version}:{requirement_key}",
    )


class PlaybookRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def sync_definitions(
        self,
        definitions: list[PlaybookDefinition],
    ) -> dict[str, UUID]:
        ids: dict[str, UUID] = {}
        async with self._database.sessions.begin() as session:
            for definition in definitions:
                record_id = playbook_id(definition)
                ids[definition.key] = record_id
                current = await session.get(PlaybookRecord, record_id)
                digest = definition_hash(definition)
                if current is not None:
                    if current.definition_hash != digest:
                        raise PlaybookError(
                            f"Playbook {definition.key!r} version "
                            f"{definition.version!r} changed; increment its "
                            "version instead of rewriting history."
                        )
                    current.active = definition.active
                    continue

                await session.execute(
                    update(PlaybookRecord)
                    .where(
                        PlaybookRecord.playbook_key == definition.key,
                        PlaybookRecord.active.is_(True),
                    )
                    .values(active=False)
                )
                session.add(
                    PlaybookRecord(
                        id=record_id,
                        playbook_key=definition.key,
                        name=definition.name,
                        event_type=definition.event_type,
                        version=definition.version,
                        active=definition.active,
                        is_overlay=definition.overlay,
                        definition_hash=digest,
                    )
                )
                requirement_records: dict[str, UUID] = {}
                for requirement in definition.requirements:
                    record_requirement_id = requirement_id(
                        definition,
                        requirement.key,
                    )
                    requirement_records[requirement.key] = (
                        record_requirement_id
                    )
                    session.add(
                        PlaybookRequirementRecord(
                            id=record_requirement_id,
                            playbook_id=record_id,
                            requirement_key=requirement.key,
                            name=requirement.name,
                            description=requirement.description,
                            required=requirement.required,
                            criticality=requirement.criticality,
                            typical_owner=requirement.typical_owner,
                            ideal_lead_days=requirement.ideal_lead_days,
                            minimum_lead_days=requirement.minimum_lead_days,
                            done_when=requirement.done_when,
                            common_failure_modes=(
                                requirement.common_failure_modes
                            ),
                            evidence_expected=requirement.evidence_expected,
                            sponsor_dependent=requirement.sponsor_dependent,
                            event_type_specific=(
                                requirement.event_type_specific
                            ),
                            next_step=requirement.next_step,
                            evaluation_config=(
                                requirement.evaluation.model_dump(mode="json")
                            ),
                        )
                    )
                for requirement in definition.requirements:
                    for dependency in requirement.dependencies:
                        session.add(
                            RequirementDependencyRecord(
                                requirement_id=requirement_records[
                                    requirement.key
                                ],
                                depends_on_requirement_id=(
                                    requirement_records[dependency]
                                ),
                            )
                        )
        return ids

    async def active_event_ids(self) -> list[UUID]:
        async with self._database.sessions() as session:
            events = list((await session.scalars(select(EventRecord))).all())
            active: list[UUID] = []
            for event in events:
                status = await session.scalar(
                    select(CurrentStateValueRecord).where(
                        CurrentStateValueRecord.entity_type == "event",
                        CurrentStateValueRecord.entity_id == event.id,
                        CurrentStateValueRecord.field == "status",
                    )
                )
                value = status.value.get("text") if status else None
                if value not in {"completed", "cancelled"}:
                    active.append(event.id)
            return active

    async def event_snapshot(self, event_id: UUID) -> EventSnapshot | None:
        async with self._database.sessions() as session:
            event = await session.get(EventRecord, event_id)
            if event is None:
                return None
            aliases = list(
                (
                    await session.scalars(
                        select(EventAliasRecord.alias).where(
                            EventAliasRecord.event_id == event_id
                        )
                    )
                ).all()
            )
            event_values = list(
                (
                    await session.scalars(
                        select(CurrentStateValueRecord).where(
                            CurrentStateValueRecord.entity_type == "event",
                            CurrentStateValueRecord.entity_id == event_id,
                        )
                    )
                ).all()
            )
            tasks = list(
                (
                    await session.scalars(
                        select(TaskRecord).where(
                            TaskRecord.event_id == event_id
                        )
                    )
                ).all()
            )
            task_ids = [task.id for task in tasks]
            task_values = (
                list(
                    (
                        await session.scalars(
                            select(CurrentStateValueRecord).where(
                                CurrentStateValueRecord.entity_type == "task",
                                CurrentStateValueRecord.entity_id.in_(task_ids),
                            )
                        )
                    ).all()
                )
                if task_ids
                else []
            )
            fact_statement = (
                select(ExtractedFactRecord)
                .join(
                    FactReconciliationStateRecord,
                    FactReconciliationStateRecord.fact_id
                    == ExtractedFactRecord.id,
                )
                .where(
                    or_(
                        (
                            FactReconciliationStateRecord.entity_type
                            == "event"
                        )
                        & (
                            FactReconciliationStateRecord.entity_id
                            == event_id
                        ),
                        (
                            FactReconciliationStateRecord.entity_type
                            == "task"
                        )
                        & FactReconciliationStateRecord.entity_id.in_(task_ids),
                    )
                )
            )
            facts = list((await session.scalars(fact_statement)).all())

        task_state: dict[UUID, dict[str, StateEvidence]] = {
            task.id: {} for task in tasks
        }
        for value in task_values:
            task_state[value.entity_id][value.field] = self._evidence(value)
        fact_text = [
            " ".join(
                part
                for part in (
                    fact.event_name,
                    fact.task,
                    fact.value,
                    fact.status,
                )
                if part
            )
            for fact in facts
        ]
        return EventSnapshot(
            id=str(event.id),
            name=event.canonical_name,
            aliases=aliases,
            state={
                value.field: self._evidence(value) for value in event_values
            },
            tasks=[
                TaskSnapshot(
                    id=str(task.id),
                    title=task.canonical_title,
                    state=task_state[task.id],
                )
                for task in tasks
            ],
            fact_text=fact_text,
        )

    async def assign_playbooks(
        self,
        *,
        event_id: UUID,
        detected: list[DetectedPlaybook],
        ids: dict[str, UUID],
    ) -> None:
        async with self._database.sessions.begin() as session:
            await session.execute(
                delete(EventPlaybookRecord).where(
                    EventPlaybookRecord.event_id == event_id
                )
            )
            for item in detected:
                session.add(
                    EventPlaybookRecord(
                        event_id=event_id,
                        playbook_id=ids[item.key],
                        detection_reason=item.reason,
                        confidence=item.confidence,
                    )
                )

    async def save_evaluation(
        self,
        *,
        event_id: UUID,
        summary: ReadinessSummary,
        definition_by_requirement: dict[
            str,
            tuple[PlaybookDefinition, str],
        ],
    ) -> UUID:
        now = datetime.now(UTC)
        async with self._database.sessions.begin() as session:
            run = RequirementEvaluationRunRecord(
                event_id=event_id,
                status="completed",
                finished_at=now,
                readiness_score=summary.readiness_score,
                complete_count=summary.complete,
                in_progress_count=summary.in_progress,
                missing_count=summary.missing,
                blocked_count=summary.blocked,
                unknown_count=summary.unknown,
                not_applicable_count=summary.not_applicable,
                critical_gap_count=summary.critical_gaps,
            )
            session.add(run)
            await session.flush()
            for result in summary.requirements:
                definition, original_key = definition_by_requirement[
                    result.requirement_key
                ]
                record_requirement_id = requirement_id(
                    definition,
                    original_key,
                )
                evidence: list[object] = [
                    item.model_dump(mode="json") for item in result.evidence
                ]
                current = await session.get(
                    EventRequirementStateRecord,
                    (event_id, record_requirement_id),
                )
                if current is None:
                    current = EventRequirementStateRecord(
                        event_id=event_id,
                        requirement_id=record_requirement_id,
                        status=result.status,
                        urgency=result.urgency,
                        confidence=result.confidence,
                        evidence=evidence,
                        recommendation=result.recommendation,
                        rationale=result.rationale,
                        last_run_id=run.id,
                        evaluated_at=now,
                    )
                    session.add(current)
                else:
                    current.status = result.status
                    current.urgency = result.urgency
                    current.confidence = result.confidence
                    current.evidence = evidence
                    current.recommendation = result.recommendation
                    current.rationale = result.rationale
                    current.last_run_id = run.id
                    current.evaluated_at = now
                session.add(
                    RequirementEvaluationRecord(
                        run_id=run.id,
                        event_id=event_id,
                        requirement_id=record_requirement_id,
                        status=result.status,
                        urgency=result.urgency,
                        confidence=result.confidence,
                        evidence=evidence,
                        recommendation=result.recommendation,
                        rationale=result.rationale,
                        readiness_weight=result.readiness_weight,
                        readiness_earned=result.readiness_earned,
                        evaluated_at=now,
                    )
                )
            return run.id

    @staticmethod
    def _evidence(
        value: CurrentStateValueRecord,
    ) -> StateEvidence:
        return StateEvidence(
            field=value.field,
            value=value.value,
            source_fact_id=str(value.source_fact_id),
            source_message_id=value.source_message_id,
            confidence=value.confidence,
        )
