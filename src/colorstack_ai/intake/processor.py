import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from colorstack_ai.extraction.models import ExtractionResponse
from colorstack_ai.intake.repository import IntakeRepository

logger = logging.getLogger(__name__)


class IntakeExtractor(Protocol):
    async def extract_intake(
        self,
        *,
        source_id: str,
        source_type: str,
        title: str,
        content: str,
        occurred_at: datetime | None,
    ) -> tuple[ExtractionResponse, dict[str, Any]]: ...


@dataclass
class IntakeProcessingSummary:
    scanned: int = 0
    processed: int = 0
    proposals: int = 0
    failed: int = 0


class IntakeProcessor:
    def __init__(self, repository: IntakeRepository, extractor: IntakeExtractor) -> None:
        self._repository = repository
        self._extractor = extractor

    async def process_pending(self, *, limit: int) -> IntakeProcessingSummary:
        sources = await self._repository.pending(limit=limit)
        summary = IntakeProcessingSummary(scanned=len(sources))
        for source in sources:
            await self._repository.mark_processing(source.id)
            try:
                response, raw_output = await self._extractor.extract_intake(
                    source_id=str(source.id),
                    source_type=source.source_type,
                    title=source.title,
                    content=source.content,
                    occurred_at=source.occurred_at,
                )
                await self._repository.save_success(
                    source.id,
                    facts=response.facts,
                    raw_output=raw_output,
                )
                summary.processed += 1
                summary.proposals += len(response.facts)
            except Exception as error:
                logger.exception("Intake source %s failed extraction", source.id)
                await self._repository.mark_failed(
                    source.id,
                    str(error) or type(error).__name__,
                )
                summary.failed += 1
        return summary
