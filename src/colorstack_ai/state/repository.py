from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, delete, select

from colorstack_ai.db.models import (
    CurrentStateValueRecord,
    EventAliasRecord,
    EventRecord,
    ExtractedFactRecord,
    FactReconciliationStateRecord,
    MessageRecord,
    ReconciliationRunRecord,
    StateChangeRecord,
    TaskRecord,
    UnresolvedFactRecord,
)
from colorstack_ai.db.session import Database
from colorstack_ai.state.models import (
    ChangeType,
    CurrentValue,
    EntityResolution,
    FactEnvelope,
    ReconciliationStatus,
    ReconciliationSummary,
    RunStatus,
    StateProposal,
    UnresolvedStatus,
)
from colorstack_ai.state.policy import evaluate_update


class StateRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def reset_derived_state(self) -> None:
        async with self._database.sessions.begin() as session:
            for record in (
                StateChangeRecord,
                CurrentStateValueRecord,
                UnresolvedFactRecord,
                FactReconciliationStateRecord,
                ReconciliationRunRecord,
            ):
                await session.execute(delete(record))
            await session.execute(
                delete(EventAliasRecord).where(
                    EventAliasRecord.event_id.in_(
                        select(EventRecord.id).where(EventRecord.record_kind == "derived")
                    )
                )
            )
            await session.execute(
                delete(TaskRecord).where(TaskRecord.task_kind == "derived")
            )
            await session.execute(
                delete(EventRecord).where(EventRecord.record_kind == "derived")
            )

    async def create_run(self, mode: str) -> UUID:
        async with self._database.sessions.begin() as session:
            run = ReconciliationRunRecord(
                mode=mode,
                status=RunStatus.RUNNING,
            )
            session.add(run)
            await session.flush()
            return run.id

    async def finish_run(
        self,
        *,
        run_id: UUID,
        status: RunStatus,
        summary: ReconciliationSummary,
        error: str | None = None,
    ) -> None:
        async with self._database.sessions.begin() as session:
            run = await session.get(ReconciliationRunRecord, run_id)
            if run is None:
                raise RuntimeError(f"Reconciliation run {run_id} was not found")
            run.status = status
            run.finished_at = datetime.now(UTC)
            run.scanned_count = summary.scanned
            run.applied_count = summary.applied
            run.deferred_count = summary.deferred
            run.no_change_count = summary.no_change
            run.failed_count = summary.failed
            run.error = error[:2_000] if error else None

    async def candidate_facts(
        self,
        *,
        mode: str,
        limit: int | None,
    ) -> list[FactEnvelope]:
        statement = (
            select(ExtractedFactRecord, MessageRecord)
            .join(
                MessageRecord,
                MessageRecord.id == ExtractedFactRecord.source_message_id,
            )
            .where(
                ExtractedFactRecord.active.is_(True),
                MessageRecord.is_deleted.is_(False),
            )
        )
        if mode in {"reconcile-new", "rebuild"}:
            if mode == "reconcile-new":
                statement = statement.outerjoin(
                    FactReconciliationStateRecord,
                    FactReconciliationStateRecord.fact_id
                    == ExtractedFactRecord.id,
                ).where(FactReconciliationStateRecord.fact_id.is_(None))
        elif mode == "retry-unresolved":
            statement = statement.join(
                FactReconciliationStateRecord,
                FactReconciliationStateRecord.fact_id
                == ExtractedFactRecord.id,
            ).where(
                FactReconciliationStateRecord.status.in_(
                    [
                        ReconciliationStatus.UNRESOLVED,
                        ReconciliationStatus.FAILED,
                    ]
                )
            )
        else:
            raise ValueError(f"Unsupported reconciliation mode: {mode}")

        statement = statement.order_by(
            MessageRecord.created_at.asc(),
            ExtractedFactRecord.ordinal.asc(),
            ExtractedFactRecord.id.asc(),
        )
        if limit is not None:
            statement = statement.limit(limit)

        async with self._database.sessions() as session:
            rows = (await session.execute(statement)).all()
        return [self._to_envelope(fact, message) for fact, message in rows]

    async def mark_processing(self, fact_id: UUID, run_id: UUID) -> None:
        async with self._database.sessions.begin() as session:
            state = await session.get(FactReconciliationStateRecord, fact_id)
            if state is None:
                state = FactReconciliationStateRecord(
                    fact_id=fact_id,
                    status=ReconciliationStatus.PROCESSING,
                    attempt_count=0,
                )
                session.add(state)
            state.status = ReconciliationStatus.PROCESSING
            state.reconciliation_run_id = run_id
            state.attempt_count += 1
            state.reason = None
            state.processed_at = None

    async def mark_unresolved(
        self,
        *,
        fact_id: UUID,
        run_id: UUID,
        reason: str,
        candidate_data: dict[str, object] | None = None,
        proposed_interpretation: dict[str, object] | None = None,
    ) -> None:
        now = datetime.now(UTC)
        async with self._database.sessions.begin() as session:
            state = await session.get(FactReconciliationStateRecord, fact_id)
            if state is None:
                raise RuntimeError(f"Fact {fact_id} was not claimed")
            state.status = ReconciliationStatus.UNRESOLVED
            state.reconciliation_run_id = run_id
            state.outcome = None
            state.reason = reason
            state.processed_at = now

            unresolved = await session.get(UnresolvedFactRecord, fact_id)
            if unresolved is None:
                unresolved = UnresolvedFactRecord(
                    fact_id=fact_id,
                    status=UnresolvedStatus.UNRESOLVED,
                    reason=reason,
                    candidate_data=candidate_data,
                    proposed_interpretation=proposed_interpretation,
                    attempt_count=1,
                    last_attempted_at=now,
                )
                session.add(unresolved)
            else:
                unresolved.status = UnresolvedStatus.UNRESOLVED
                unresolved.reason = reason
                unresolved.candidate_data = candidate_data
                unresolved.proposed_interpretation = proposed_interpretation
                unresolved.attempt_count += 1
                unresolved.last_attempted_at = now
                unresolved.resolved_at = None

    async def apply_fact(
        self,
        *,
        fact: FactEnvelope,
        run_id: UUID,
        resolution: EntityResolution,
        proposals: list[StateProposal],
    ) -> tuple[bool, str]:
        now = datetime.now(UTC)
        applied = False
        conflict_reasons: list[str] = []
        async with self._database.sessions.begin() as session:
            processing = await session.get(
                FactReconciliationStateRecord,
                fact.id,
            )
            if processing is None:
                raise RuntimeError(f"Fact {fact.id} was not claimed")

            for proposal in proposals:
                current_record = await session.scalar(
                    select(CurrentStateValueRecord)
                    .where(
                        CurrentStateValueRecord.entity_type
                        == resolution.entity_type,
                        CurrentStateValueRecord.entity_id
                        == resolution.entity_id,
                        CurrentStateValueRecord.field == proposal.field,
                    )
                    .with_for_update()
                )
                current = (
                    CurrentValue(
                        value=current_record.value,
                        confidence=current_record.confidence,
                        evidence_kind=current_record.evidence_kind,
                        effective_at=current_record.effective_at,
                    )
                    if current_record
                    else None
                )
                decision = evaluate_update(
                    current=current,
                    proposal=proposal,
                    fact=fact,
                )
                if not decision.apply:
                    if decision.outcome == ChangeType.CONTRADICTION:
                        conflict_reasons.append(decision.reason)
                    continue

                session.add(
                    StateChangeRecord(
                        reconciliation_run_id=run_id,
                        entity_type=resolution.entity_type,
                        entity_id=resolution.entity_id,
                        field=proposal.field,
                        previous_value=(
                            current_record.value if current_record else None
                        ),
                        new_value=proposal.value,
                        change_type=decision.outcome or proposal.change_type,
                        source_fact_id=fact.id,
                        source_message_id=fact.source_message_id,
                        reason=decision.reason,
                        reconciliation_confidence=min(
                            resolution.confidence,
                            proposal.reconciliation_confidence,
                        ),
                        effective_at=fact.message_created_at,
                    )
                )
                if current_record is None:
                    current_record = CurrentStateValueRecord(
                        entity_type=resolution.entity_type,
                        entity_id=resolution.entity_id,
                        field=proposal.field,
                        value=proposal.value,
                        source_fact_id=fact.id,
                        source_message_id=fact.source_message_id,
                        confidence=fact.confidence,
                        evidence_kind=fact.evidence_kind,
                        effective_at=fact.message_created_at,
                    )
                    session.add(current_record)
                else:
                    current_record.value = proposal.value
                    current_record.source_fact_id = fact.id
                    current_record.source_message_id = fact.source_message_id
                    current_record.confidence = fact.confidence
                    current_record.evidence_kind = fact.evidence_kind
                    current_record.effective_at = fact.message_created_at
                applied = True

            processing.status = (
                ReconciliationStatus.APPLIED
                if applied
                else ReconciliationStatus.NO_CHANGE
            )
            processing.reconciliation_run_id = run_id
            processing.entity_type = resolution.entity_type
            processing.entity_id = resolution.entity_id
            processing.outcome = (
                ChangeType.CONTRADICTION
                if conflict_reasons
                else ("applied" if applied else "no_change")
            )
            processing.reason = (
                "; ".join(conflict_reasons)
                if conflict_reasons
                else (
                    "state updated"
                    if applied
                    else "fact created no current-state change"
                )
            )
            processing.processed_at = now

            unresolved = await session.get(UnresolvedFactRecord, fact.id)
            if unresolved is not None:
                unresolved.status = UnresolvedStatus.RESOLVED
                unresolved.resolved_at = now
                unresolved.last_attempted_at = now

        reason = (
            "; ".join(conflict_reasons)
            if conflict_reasons
            else ("applied" if applied else "no change")
        )
        return applied, reason

    async def mark_failed(
        self,
        *,
        fact_id: UUID,
        run_id: UUID,
        error: str,
    ) -> None:
        async with self._database.sessions.begin() as session:
            state = await session.get(FactReconciliationStateRecord, fact_id)
            if state is None:
                state = FactReconciliationStateRecord(
                    fact_id=fact_id,
                    attempt_count=1,
                    status=ReconciliationStatus.FAILED,
                )
                session.add(state)
            state.status = ReconciliationStatus.FAILED
            state.reconciliation_run_id = run_id
            state.reason = error[:2_000]
            state.processed_at = datetime.now(UTC)

    async def state_for_entity(
        self,
        *,
        entity_type: str,
        entity_id: UUID,
    ) -> dict[str, dict[str, Any]]:
        async with self._database.sessions() as session:
            records = list(
                (
                    await session.scalars(
                        select(CurrentStateValueRecord).where(
                            CurrentStateValueRecord.entity_type == entity_type,
                            CurrentStateValueRecord.entity_id == entity_id,
                        )
                    )
                ).all()
            )
        return {record.field: record.value for record in records}

    @staticmethod
    def _to_envelope(
        fact: ExtractedFactRecord,
        message: MessageRecord,
    ) -> FactEnvelope:
        return FactEnvelope(
            id=fact.id,
            source_message_id=fact.source_message_id,
            extraction_version=fact.extraction_version,
            ordinal=fact.ordinal,
            fact_type=fact.fact_type,
            event_name=fact.event_name,
            task=fact.task,
            owner_name=fact.owner_name,
            owner_discord_id=fact.owner_discord_id,
            deadline_text=fact.deadline_text,
            normalized_deadline=fact.normalized_deadline,
            status=fact.status,
            value=fact.value,
            confidence=fact.confidence,
            evidence_kind=fact.evidence_kind,
            guild_id=message.guild_id,
            channel_id=message.channel_id,
            thread_id=message.thread_id,
            reply_to_message_id=message.reply_to_message_id,
            message_created_at=message.created_at,
            message_content=message.content,
        )
