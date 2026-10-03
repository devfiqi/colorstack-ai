from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from colorstack_ai.context.models import ContextSource, FactContextItem
from colorstack_ai.db.models import IntakeProposalRecord, IntakeSourceRecord
from colorstack_ai.db.session import Database
from colorstack_ai.extraction.models import FactDraft
from colorstack_ai.intake.models import (
    IntakeProposal,
    IntakeReview,
    IntakeSource,
    IntakeSourceCreate,
    IntakeSourceStatus,
    IntakeSourceType,
    IntakeSummary,
    ProposalStatus,
)
from colorstack_ai.state.resolution import distinctive_tokens


class IntakeRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def create(self, request: IntakeSourceCreate) -> IntakeSource:
        async with self._database.sessions.begin() as session:
            record = IntakeSourceRecord(
                title=request.title.strip(),
                source_type=request.source_type.value,
                content=request.content.strip(),
                occurred_at=request.occurred_at,
                status=IntakeSourceStatus.PENDING,
            )
            session.add(record)
            await session.flush()
            await session.refresh(record)
            return self._source(record, [])

    async def list_sources(self, *, limit: int = 50) -> list[IntakeSummary]:
        async with self._database.sessions() as session:
            records = list(
                (
                    await session.scalars(
                        select(IntakeSourceRecord)
                        .options(selectinload(IntakeSourceRecord.proposals))
                        .order_by(IntakeSourceRecord.created_at.desc())
                        .limit(limit)
                    )
                ).all()
            )
        return [
            IntakeSummary(
                id=record.id,
                title=record.title,
                source_type=IntakeSourceType(record.source_type),
                status=IntakeSourceStatus(record.status),
                created_at=record.created_at,
                proposal_count=len(record.proposals),
                pending_count=sum(
                    item.status == ProposalStatus.PENDING
                    for item in record.proposals
                ),
            )
            for record in records
        ]

    async def get(self, source_id: UUID) -> IntakeSource | None:
        async with self._database.sessions() as session:
            record = await session.scalar(
                select(IntakeSourceRecord)
                .where(IntakeSourceRecord.id == source_id)
                .options(selectinload(IntakeSourceRecord.proposals))
            )
        if record is None:
            return None
        return self._source(record, record.proposals)

    async def pending(self, *, limit: int) -> list[IntakeSourceRecord]:
        async with self._database.sessions() as session:
            return list(
                (
                    await session.scalars(
                        select(IntakeSourceRecord)
                        .where(
                            IntakeSourceRecord.status.in_(
                                [
                                    IntakeSourceStatus.PENDING,
                                    IntakeSourceStatus.PROCESSING,
                                ]
                            )
                        )
                        .order_by(IntakeSourceRecord.created_at.asc())
                        .limit(limit)
                    )
                ).all()
            )

    async def mark_processing(self, source_id: UUID) -> None:
        async with self._database.sessions.begin() as session:
            record = await session.get(IntakeSourceRecord, source_id)
            if record is None:
                raise RuntimeError(f"Intake source {source_id} was not found")
            record.status = IntakeSourceStatus.PROCESSING
            record.error = None

    async def save_success(
        self,
        source_id: UUID,
        *,
        facts: list[FactDraft],
        raw_output: dict[str, object],
    ) -> None:
        async with self._database.sessions.begin() as session:
            record = await session.get(IntakeSourceRecord, source_id)
            if record is None:
                raise RuntimeError(f"Intake source {source_id} was not found")
            await session.execute(
                delete(IntakeProposalRecord).where(
                    IntakeProposalRecord.source_id == source_id
                )
            )
            session.add_all(
                [
                    IntakeProposalRecord(
                        source_id=source_id,
                        ordinal=ordinal,
                        fact_payload=fact.model_dump(mode="json"),
                        status=ProposalStatus.PENDING,
                    )
                    for ordinal, fact in enumerate(facts)
                ]
            )
            record.status = IntakeSourceStatus.PROCESSED
            record.raw_model_output = raw_output
            record.error = None

    async def mark_failed(self, source_id: UUID, error: str) -> None:
        async with self._database.sessions.begin() as session:
            record = await session.get(IntakeSourceRecord, source_id)
            if record is None:
                return
            record.status = IntakeSourceStatus.FAILED
            record.error = error[:2_000]

    async def retry(self, source_id: UUID) -> bool:
        async with self._database.sessions.begin() as session:
            record = await session.get(IntakeSourceRecord, source_id)
            if record is None:
                return False
            record.status = IntakeSourceStatus.PENDING
            record.error = None
            return True

    async def review(
        self,
        proposal_id: UUID,
        review: IntakeReview,
    ) -> IntakeProposal | None:
        IntakeReview.validate_review_status(review.status)
        async with self._database.sessions.begin() as session:
            record = await session.get(IntakeProposalRecord, proposal_id)
            if record is None:
                return None
            record.status = review.status
            record.reviewer_note = review.reviewer_note
            record.reviewed_at = datetime.now(UTC)
            await session.flush()
            return self._proposal(record)

    async def approved_context(
        self,
        *,
        entity_text: str | None = None,
        limit: int = 30,
    ) -> list[FactContextItem]:
        async with self._database.sessions() as session:
            rows = (
                await session.execute(
                    select(IntakeProposalRecord, IntakeSourceRecord)
                    .join(
                        IntakeSourceRecord,
                        IntakeSourceRecord.id == IntakeProposalRecord.source_id,
                    )
                    .where(
                        IntakeProposalRecord.status == ProposalStatus.APPROVED
                    )
                    .order_by(IntakeProposalRecord.reviewed_at.desc())
                    .limit(200)
                )
            ).all()
        results: list[FactContextItem] = []
        requested = distinctive_tokens(entity_text or "")
        for proposal, source in rows:
            fact = FactDraft.model_validate(proposal.fact_payload)
            searchable = " ".join(
                item
                for item in (
                    source.title,
                    fact.event_name,
                    fact.task,
                    fact.owner_name,
                    fact.deadline_text,
                    fact.value,
                )
                if item
            )
            if requested and not requested <= distinctive_tokens(searchable):
                continue
            results.append(
                FactContextItem(
                    fact_id=str(proposal.id),
                    fact_type=fact.type,
                    event_name=fact.event_name,
                    task=fact.task,
                    owner_name=fact.owner_name,
                    owner_discord_id=fact.owner_discord_id,
                    status=fact.status,
                    value=fact.value,
                    deadline=fact.normalized_deadline,
                    confidence=fact.confidence,
                    evidence_kind=fact.evidence_kind,
                    source=ContextSource(
                        type="reviewed_intake",
                        id=str(source.id),
                        timestamp=source.occurred_at or source.created_at,
                    ),
                )
            )
            if len(results) >= limit:
                break
        return results

    @staticmethod
    def _source(
        record: IntakeSourceRecord,
        proposals: list[IntakeProposalRecord],
    ) -> IntakeSource:
        return IntakeSource(
            id=record.id,
            title=record.title,
            source_type=IntakeSourceType(record.source_type),
            content=record.content,
            occurred_at=record.occurred_at,
            status=IntakeSourceStatus(record.status),
            error=record.error,
            created_at=record.created_at,
            updated_at=record.updated_at,
            proposals=[IntakeRepository._proposal(item) for item in proposals],
        )

    @staticmethod
    def _proposal(record: IntakeProposalRecord) -> IntakeProposal:
        return IntakeProposal(
            id=record.id,
            ordinal=record.ordinal,
            fact=FactDraft.model_validate(record.fact_payload),
            status=ProposalStatus(record.status),
            reviewer_note=record.reviewer_note,
            reviewed_at=record.reviewed_at,
        )
