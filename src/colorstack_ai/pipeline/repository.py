from datetime import datetime

from sqlalchemy import select

from colorstack_ai.db.models import PipelineRunRecord
from colorstack_ai.db.session import Database


class PipelineRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def record(
        self,
        *,
        cycle_number: int,
        status: str,
        stages: list[dict[str, object]],
        started_at: datetime,
        finished_at: datetime,
    ) -> None:
        async with self._database.sessions.begin() as session:
            session.add(
                PipelineRunRecord(
                    cycle_number=cycle_number,
                    status=status,
                    stages=stages,
                    started_at=started_at,
                    finished_at=finished_at,
                )
            )

    async def latest(self) -> PipelineRunRecord | None:
        async with self._database.sessions() as session:
            return await session.scalar(
                select(PipelineRunRecord)
                .order_by(PipelineRunRecord.finished_at.desc())
                .limit(1)
            )
