import asyncio
import os
import unittest
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete

from colorstack_ai.db.models import PipelineRunRecord
from colorstack_ai.db.session import Database
from colorstack_ai.pipeline.repository import PipelineRepository
from colorstack_ai.pipeline.service import ContinuousPipeline, PipelineStage

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


class ContinuousPipelineTest(unittest.IsolatedAsyncioTestCase):
    async def test_failed_stage_does_not_stop_later_stages(self) -> None:
        calls: list[tuple[str, int]] = []

        async def fail(cycle: int) -> None:
            calls.append(("fail", cycle))
            raise RuntimeError("ollama unavailable")

        async def continue_processing(cycle: int) -> None:
            calls.append(("continue", cycle))

        pipeline = ContinuousPipeline(
            (
                PipelineStage("extraction", fail),
                PipelineStage("state", continue_processing),
            ),
            interval_seconds=60,
        )

        result = await pipeline.run_once()

        self.assertFalse(result.succeeded)
        self.assertEqual(calls, [("fail", 1), ("continue", 1)])
        self.assertEqual(result.stages[0].error, "ollama unavailable")
        self.assertTrue(result.stages[1].succeeded)

    async def test_background_loop_starts_once_and_shuts_down_cleanly(self) -> None:
        called = asyncio.Event()
        cycles: list[int] = []

        async def record(cycle: int) -> None:
            cycles.append(cycle)
            called.set()

        pipeline = ContinuousPipeline(
            (PipelineStage("record", record),),
            interval_seconds=60,
        )

        pipeline.start()
        pipeline.start()
        await asyncio.wait_for(called.wait(), timeout=1)
        await pipeline.shutdown()

        self.assertEqual(cycles, [1])
        self.assertIsNotNone(pipeline.last_result)


@unittest.skipUnless(
    TEST_DATABASE_URL,
    "TEST_DATABASE_URL is required for PostgreSQL integration tests",
)
class PipelineRepositoryTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        assert TEST_DATABASE_URL is not None
        self.database = Database(TEST_DATABASE_URL)
        self.repository = PipelineRepository(self.database)
        async with self.database.sessions.begin() as session:
            await session.execute(delete(PipelineRunRecord))

    async def asyncTearDown(self) -> None:
        await self.database.close()

    async def test_latest_returns_persisted_stage_health(self) -> None:
        started_at = datetime(2026, 10, 2, 12, tzinfo=UTC)
        finished_at = started_at + timedelta(seconds=4)
        await self.repository.record(
            cycle_number=1,
            status="degraded",
            stages=[
                {
                    "name": "extraction",
                    "succeeded": False,
                    "error": "ollama unavailable",
                }
            ],
            started_at=started_at,
            finished_at=finished_at,
        )

        latest = await self.repository.latest()

        self.assertIsNotNone(latest)
        assert latest is not None
        self.assertEqual(latest.status, "degraded")
        self.assertEqual(latest.finished_at, finished_at)
        self.assertEqual(latest.stages[0]["name"], "extraction")
