from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgres_insert

from colorstack_ai.briefing.models import BriefRunStatus, DailyBrief
from colorstack_ai.db.models import DailyBriefRunRecord
from colorstack_ai.db.session import Database


class BriefRunRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def start(
        self,
        *,
        scheduled_date: date,
        manually_triggered: bool,
        channel_id: str | None,
    ) -> UUID | None:
        values = {
            "scheduled_date": scheduled_date,
            "status": BriefRunStatus.STARTED.value,
            "discord_channel_id": channel_id,
            "discord_message_ids": [],
            "manually_triggered": manually_triggered,
        }
        async with self._database.sessions.begin() as session:
            if manually_triggered:
                record = DailyBriefRunRecord(**values)
                session.add(record)
                await session.flush()
                return record.id
            result = await session.execute(
                postgres_insert(DailyBriefRunRecord)
                .values(**values)
                .on_conflict_do_nothing(
                    index_elements=[DailyBriefRunRecord.scheduled_date],
                    index_where=DailyBriefRunRecord.manually_triggered.is_(False),
                )
                .returning(DailyBriefRunRecord.id)
            )
            return result.scalar_one_or_none()

    async def generated(
        self,
        run_id: UUID,
        *,
        brief: DailyBrief,
        rendered_text: str,
        reasoning_usage_id: UUID,
        previewed: bool,
    ) -> None:
        async with self._database.sessions.begin() as session:
            record = await self._record(session, run_id)
            record.status = (
                BriefRunStatus.PREVIEWED.value
                if previewed
                else BriefRunStatus.GENERATED.value
            )
            record.brief_payload = brief.model_dump(mode="json")
            record.rendered_text = rendered_text
            record.reasoning_usage_id = reasoning_usage_id
            if previewed:
                record.completed_at = datetime.now(UTC)

    async def delivered(self, run_id: UUID, message_ids: list[str]) -> None:
        async with self._database.sessions.begin() as session:
            record = await self._record(session, run_id)
            record.status = BriefRunStatus.COMPLETED.value
            record.discord_message_ids = list(message_ids)
            record.completed_at = datetime.now(UTC)

    async def fail(self, run_id: UUID, *, stage: str, error: str) -> None:
        async with self._database.sessions.begin() as session:
            record = await self._record(session, run_id)
            record.status = BriefRunStatus.FAILED.value
            record.failure_stage = stage
            record.error = error[:2000]
            record.completed_at = datetime.now(UTC)

    async def get(self, run_id: UUID) -> DailyBriefRunRecord | None:
        async with self._database.sessions() as session:
            return await session.get(DailyBriefRunRecord, run_id)

    @staticmethod
    async def _record(session: object, run_id: UUID) -> DailyBriefRunRecord:
        record = await session.get(DailyBriefRunRecord, run_id)  # type: ignore[attr-defined]
        if record is None:
            raise RuntimeError(f"Daily brief run {run_id} was not found.")
        return record
