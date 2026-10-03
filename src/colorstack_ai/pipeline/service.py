import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from colorstack_ai.config import ExtractionEnvironment, PipelineEnvironment
from colorstack_ai.db.session import Database
from colorstack_ai.extraction.context import ContextBuilder as ExtractionContextBuilder
from colorstack_ai.extraction.ollama import OllamaClient
from colorstack_ai.extraction.processor import ExtractionProcessor
from colorstack_ai.extraction.repository import ExtractionRepository
from colorstack_ai.playbooks.evaluator import EventEvaluator
from colorstack_ai.playbooks.loader import PlaybookLoader
from colorstack_ai.playbooks.repository import PlaybookRepository
from colorstack_ai.pipeline.repository import PipelineRepository
from colorstack_ai.state.processor import StateProcessor
from colorstack_ai.state.repository import StateRepository
from colorstack_ai.state.resolution import EntityResolver

logger = logging.getLogger(__name__)

PipelineJob = Callable[[int], Awaitable[object]]
PipelineReporter = Callable[["PipelineCycleResult"], Awaitable[None]]


@dataclass(frozen=True)
class PipelineStage:
    name: str
    job: PipelineJob


@dataclass(frozen=True)
class PipelineStageResult:
    name: str
    succeeded: bool
    error: str | None = None


@dataclass(frozen=True)
class PipelineCycleResult:
    cycle: int
    started_at: datetime
    finished_at: datetime
    stages: tuple[PipelineStageResult, ...]

    @property
    def succeeded(self) -> bool:
        return all(stage.succeeded for stage in self.stages)


class ContinuousPipeline:
    """Runs the local, read-only intelligence pipeline in the background.

    A failed stage is isolated so later stages can still process previously
    persisted work. This service only updates ColorStack AI's internal derived
    state; it has no outbound communication or external action capability.
    """

    def __init__(
        self,
        stages: Sequence[PipelineStage],
        *,
        interval_seconds: float,
        reporter: PipelineReporter | None = None,
    ) -> None:
        self._stages = tuple(stages)
        self._interval_seconds = interval_seconds
        self._reporter = reporter
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None
        self._cycle = 0
        self.last_result: PipelineCycleResult | None = None

    def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(
            self._run(),
            name="colorstack-continuous-pipeline",
        )
        logger.info(
            "Continuous intelligence pipeline started (interval=%ss)",
            self._interval_seconds,
        )

    async def shutdown(self) -> None:
        self._stop.set()
        if self._task is not None:
            await self._task
        self._task = None

    async def run_once(self) -> PipelineCycleResult:
        self._cycle += 1
        started_at = datetime.now(UTC)
        results: list[PipelineStageResult] = []
        for stage in self._stages:
            try:
                await stage.job(self._cycle)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                logger.exception("Pipeline stage %s failed", stage.name)
                results.append(
                    PipelineStageResult(
                        name=stage.name,
                        succeeded=False,
                        error=str(error) or type(error).__name__,
                    )
                )
            else:
                results.append(PipelineStageResult(name=stage.name, succeeded=True))
        result = PipelineCycleResult(
            cycle=self._cycle,
            started_at=started_at,
            finished_at=datetime.now(UTC),
            stages=tuple(results),
        )
        self.last_result = result
        if self._reporter is not None:
            try:
                await self._reporter(result)
            except Exception:
                logger.exception("Could not persist pipeline health")
        logger.info(
            "Pipeline cycle %s complete (%s)",
            result.cycle,
            "healthy" if result.succeeded else "degraded",
        )
        return result

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Unexpected continuous pipeline failure")
            try:
                await asyncio.wait_for(
                    self._stop.wait(),
                    timeout=self._interval_seconds,
                )
            except TimeoutError:
                pass


def create_pipeline(
    database: Database,
    extraction: ExtractionEnvironment,
    settings: PipelineEnvironment,
) -> ContinuousPipeline:
    extraction_repository = ExtractionRepository(database)
    extraction_context = ExtractionContextBuilder(database)
    state_processor = StateProcessor(
        repository=StateRepository(database),
        resolver=EntityResolver(database),
    )
    evaluator = EventEvaluator(
        repository=PlaybookRepository(database),
        loader=PlaybookLoader(),
    )

    async def extract(cycle: int) -> None:
        async with OllamaClient(
            base_url=extraction.ollama_base_url,
            model=extraction.ollama_model,
            timeout_seconds=extraction.ollama_timeout_seconds,
        ) as ollama:
            await ollama.validate()
            processor = ExtractionProcessor(
                repository=extraction_repository,
                context_builder=extraction_context,
                extractor=ollama,
                extraction_version=extraction.extraction_version,
            )
            await processor.process(mode="new", limit=settings.batch_size)
            if cycle % settings.retry_every_cycles == 0:
                await processor.process(
                    mode="retry-failed",
                    limit=settings.batch_size,
                )

    async def reconcile(cycle: int) -> None:
        await state_processor.process(
            mode="reconcile-new",
            limit=settings.batch_size,
        )
        if cycle % settings.retry_every_cycles == 0:
            await state_processor.process(
                mode="retry-unresolved",
                limit=settings.batch_size,
            )

    async def evaluate(_: int) -> None:
        await evaluator.evaluate_all()

    repository = PipelineRepository(database)

    async def record(result: PipelineCycleResult) -> None:
        await repository.record(
            cycle_number=result.cycle,
            status="healthy" if result.succeeded else "degraded",
            stages=[
                {
                    "name": stage.name,
                    "succeeded": stage.succeeded,
                    "error": stage.error,
                }
                for stage in result.stages
            ],
            started_at=result.started_at,
            finished_at=result.finished_at,
        )

    return ContinuousPipeline(
        (
            PipelineStage("extraction", extract),
            PipelineStage("state-reconciliation", reconcile),
            PipelineStage("playbook-evaluation", evaluate),
        ),
        interval_seconds=settings.interval_seconds,
        reporter=record,
    )
