from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import and_, delete, select

from colorstack_ai.db.models import (
    ExtractedFactRecord,
    ExtractionRunRecord,
    MessageProcessingStateRecord,
    MessageRecord,
)
from colorstack_ai.db.session import Database
from colorstack_ai.extraction.models import FactDraft


class ProcessingStatus(StrEnum):
    PROCESSING = "processing"
    SKIPPED = "skipped_low_relevance"
    SUCCESS = "processed_successfully"
    FAILED = "failed"


class RunStatus(StrEnum):
    RUNNING = "running"
    SUCCESS = "completed"
    FAILED = "failed"


class ExtractionRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def create_run(
        self,
        *,
        model_name: str,
        model_config: dict[str, object],
        extraction_version: str,
    ) -> UUID:
        async with self._database.sessions.begin() as session:
            run = ExtractionRunRecord(
                model_name=model_name,
                model_config=model_config,
                extraction_version=extraction_version,
                status=RunStatus.RUNNING,
            )
            session.add(run)
            await session.flush()
            return run.id

    async def candidate_message_ids(
        self,
        *,
        mode: str,
        extraction_version: str,
        limit: int | None,
    ) -> list[str]:
        state_match = and_(
            MessageProcessingStateRecord.message_id == MessageRecord.id,
            MessageProcessingStateRecord.extraction_version
            == extraction_version,
        )
        statement = select(MessageRecord.id).where(
            MessageRecord.is_deleted.is_(False)
        )

        if mode in {"backfill", "new"}:
            statement = statement.outerjoin(
                MessageProcessingStateRecord,
                state_match,
            ).where(MessageProcessingStateRecord.message_id.is_(None))
        elif mode == "retry-failed":
            statement = statement.join(
                MessageProcessingStateRecord,
                state_match,
            ).where(
                MessageProcessingStateRecord.status.in_(
                    [ProcessingStatus.FAILED, ProcessingStatus.PROCESSING]
                )
            )
        else:
            raise ValueError(f"Unsupported extraction mode: {mode}")

        if mode == "new":
            statement = statement.order_by(MessageRecord.created_at.desc())
        else:
            statement = statement.order_by(MessageRecord.created_at.asc())
        if limit is not None:
            statement = statement.limit(limit)

        async with self._database.sessions() as session:
            return list((await session.scalars(statement)).all())

    async def mark_skipped(
        self,
        *,
        message_id: str,
        extraction_version: str,
        run_id: UUID,
        reason: str,
    ) -> None:
        async with self._database.sessions.begin() as session:
            state = await session.get(
                MessageProcessingStateRecord,
                (message_id, extraction_version),
            )
            if state is None:
                state = MessageProcessingStateRecord(
                    message_id=message_id,
                    extraction_version=extraction_version,
                    status=ProcessingStatus.SKIPPED,
                    attempt_count=0,
                )
                session.add(state)
            state.status = ProcessingStatus.SKIPPED
            state.is_relevant = False
            state.relevance_reason = reason
            state.extraction_run_id = run_id
            state.error = None
            state.processed_at = datetime.now(UTC)

    async def mark_processing(
        self,
        *,
        message_id: str,
        extraction_version: str,
        run_id: UUID,
        reason: str,
    ) -> None:
        async with self._database.sessions.begin() as session:
            state = await session.get(
                MessageProcessingStateRecord,
                (message_id, extraction_version),
            )
            if state is None:
                state = MessageProcessingStateRecord(
                    message_id=message_id,
                    extraction_version=extraction_version,
                    status=ProcessingStatus.PROCESSING,
                    attempt_count=0,
                )
                session.add(state)
            state.status = ProcessingStatus.PROCESSING
            state.is_relevant = True
            state.relevance_reason = reason
            state.extraction_run_id = run_id
            state.attempt_count += 1
            state.error = None
            state.processed_at = None

    async def save_success(
        self,
        *,
        message_id: str,
        extraction_version: str,
        run_id: UUID,
        facts: list[FactDraft],
        raw_output: dict[str, Any],
    ) -> None:
        async with self._database.sessions.begin() as session:
            state = await session.get(
                MessageProcessingStateRecord,
                (message_id, extraction_version),
            )
            if state is None:
                raise RuntimeError(
                    f"Message {message_id} was not claimed for extraction"
                )

            await session.execute(
                delete(ExtractedFactRecord).where(
                    and_(
                        ExtractedFactRecord.source_message_id == message_id,
                        ExtractedFactRecord.extraction_version
                        == extraction_version,
                    )
                )
            )
            session.add_all(
                [
                    ExtractedFactRecord(
                        source_message_id=message_id,
                        extraction_run_id=run_id,
                        extraction_version=extraction_version,
                        ordinal=ordinal,
                        fact_type=fact.type,
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
                    )
                    for ordinal, fact in enumerate(facts)
                ]
            )

            state.status = ProcessingStatus.SUCCESS
            state.raw_model_output = raw_output
            state.error = None
            state.processed_at = datetime.now(UTC)

    async def mark_failed(
        self,
        *,
        message_id: str,
        extraction_version: str,
        run_id: UUID,
        error: str,
    ) -> None:
        async with self._database.sessions.begin() as session:
            state = await session.get(
                MessageProcessingStateRecord,
                (message_id, extraction_version),
            )
            if state is None:
                state = MessageProcessingStateRecord(
                    message_id=message_id,
                    extraction_version=extraction_version,
                    status=ProcessingStatus.FAILED,
                    attempt_count=1,
                )
                session.add(state)
            state.status = ProcessingStatus.FAILED
            state.is_relevant = True
            state.extraction_run_id = run_id
            state.error = error[:2_000]
            state.processed_at = datetime.now(UTC)

    async def finish_run(
        self,
        *,
        run_id: UUID,
        status: RunStatus,
        scanned_count: int,
        relevant_count: int,
        skipped_count: int,
        processed_count: int,
        fact_count: int,
        failed_count: int,
        error: str | None = None,
    ) -> None:
        async with self._database.sessions.begin() as session:
            run = await session.get(ExtractionRunRecord, run_id)
            if run is None:
                raise RuntimeError(f"Extraction run {run_id} was not found")
            run.status = status
            run.finished_at = datetime.now(UTC)
            run.scanned_count = scanned_count
            run.relevant_count = relevant_count
            run.skipped_count = skipped_count
            run.processed_count = processed_count
            run.fact_count = fact_count
            run.failed_count = failed_count
            run.error = error[:2_000] if error else None
