import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from colorstack_ai.extraction.context import ContextBuilder
from colorstack_ai.extraction.models import (
    ExtractionContext,
    ExtractionResponse,
    FactDraft,
    FactType,
)
from colorstack_ai.extraction.prompt import PROMPT_VERSION
from colorstack_ai.extraction.relevance import assess_relevance
from colorstack_ai.extraction.repository import (
    ExtractionRepository,
    RunStatus,
)

logger = logging.getLogger(__name__)
FIRST_PERSON_COMMITMENT = re.compile(
    r"\b(?:i(?:'ll| will| can)|i can|i got|i've got)\b",
    re.IGNORECASE,
)


class FactExtractor(Protocol):
    model: str
    server_version: str | None

    async def extract(
        self,
        context: ExtractionContext,
    ) -> tuple[ExtractionResponse, dict[str, Any]]: ...


@dataclass
class ExtractionSummary:
    scanned: int = 0
    relevant: int = 0
    skipped: int = 0
    processed: int = 0
    facts_created: int = 0
    failed: int = 0


class ExtractionProcessor:
    def __init__(
        self,
        *,
        repository: ExtractionRepository,
        context_builder: ContextBuilder,
        extractor: FactExtractor,
        extraction_version: str,
    ) -> None:
        self._repository = repository
        self._context_builder = context_builder
        self._extractor = extractor
        self._extraction_version = extraction_version

    async def process(
        self,
        *,
        mode: str,
        limit: int | None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> ExtractionSummary:
        run_id = await self._repository.create_run(
            model_name=self._extractor.model,
            model_config={
                "ollama_version": self._extractor.server_version or "unknown",
                "prompt_version": PROMPT_VERSION,
                "temperature": 0,
            },
            extraction_version=self._extraction_version,
        )
        summary = ExtractionSummary()

        try:
            candidate_ids = await self._repository.candidate_message_ids(
                mode=mode,
                extraction_version=self._extraction_version,
                limit=limit,
                start_at=start_at,
                end_at=end_at,
            )
            summary.scanned = len(candidate_ids)
            logger.info("Scanning %d candidate messages", summary.scanned)

            relevant_contexts: list[ExtractionContext] = []
            for index, message_id in enumerate(candidate_ids, start=1):
                try:
                    context = await self._context_builder.build(message_id)
                    reply_is_relevant = (
                        await self._context_builder.reply_is_relevant(
                            context.reply_to_message_id,
                            self._extraction_version,
                        )
                    )
                    decision = assess_relevance(
                        context,
                        reply_is_relevant=reply_is_relevant,
                    )
                    if not decision.is_relevant:
                        await self._repository.mark_skipped(
                            message_id=message_id,
                            extraction_version=self._extraction_version,
                            run_id=run_id,
                            reason=decision.reason_text,
                        )
                        summary.skipped += 1
                    else:
                        await self._repository.mark_processing(
                            message_id=message_id,
                            extraction_version=self._extraction_version,
                            run_id=run_id,
                            reason=decision.reason_text,
                        )
                        relevant_contexts.append(context)
                        summary.relevant += 1
                except Exception as error:
                    await self._repository.mark_failed(
                        message_id=message_id,
                        extraction_version=self._extraction_version,
                        run_id=run_id,
                        error=self._error_text(error),
                    )
                    summary.failed += 1
                    logger.error(
                        "Message %s failed during relevance scanning (%s)",
                        message_id,
                        type(error).__name__,
                    )

                if index % 100 == 0:
                    logger.info(
                        "Scanned %d/%d messages",
                        index,
                        summary.scanned,
                    )

            logger.info(
                "Relevance scan complete — relevant: %d, skipped: %d, failed: %d",
                summary.relevant,
                summary.skipped,
                summary.failed,
            )

            for index, context in enumerate(relevant_contexts, start=1):
                logger.info(
                    "Extracting message %d/%d (%s)",
                    index,
                    len(relevant_contexts),
                    context.source_message_id,
                )
                try:
                    response, raw_output = await self._extractor.extract(context)
                    facts = self._resolve_speaker_ownership(
                        context,
                        response.facts,
                    )
                    await self._repository.save_success(
                        message_id=context.source_message_id,
                        extraction_version=self._extraction_version,
                        run_id=run_id,
                        facts=facts,
                        raw_output=raw_output,
                    )
                    summary.processed += 1
                    summary.facts_created += len(facts)
                    logger.info(
                        "Message %s produced %d facts",
                        context.source_message_id,
                        len(facts),
                    )
                except Exception as error:
                    await self._repository.mark_failed(
                        message_id=context.source_message_id,
                        extraction_version=self._extraction_version,
                        run_id=run_id,
                        error=self._error_text(error),
                    )
                    summary.failed += 1
                    logger.error(
                        "Message %s extraction failed (%s)",
                        context.source_message_id,
                        type(error).__name__,
                    )

            await self._repository.finish_run(
                run_id=run_id,
                status=RunStatus.SUCCESS,
                scanned_count=summary.scanned,
                relevant_count=summary.relevant,
                skipped_count=summary.skipped,
                processed_count=summary.processed,
                fact_count=summary.facts_created,
                failed_count=summary.failed,
            )
        except Exception as error:
            await self._repository.finish_run(
                run_id=run_id,
                status=RunStatus.FAILED,
                scanned_count=summary.scanned,
                relevant_count=summary.relevant,
                skipped_count=summary.skipped,
                processed_count=summary.processed,
                fact_count=summary.facts_created,
                failed_count=summary.failed,
                error=self._error_text(error),
            )
            raise

        logger.info("Extraction complete")
        logger.info("Processed: %d", summary.processed)
        logger.info("Facts created: %d", summary.facts_created)
        logger.info("Skipped: %d", summary.skipped)
        logger.info("Failed: %d", summary.failed)
        return summary

    @staticmethod
    def _error_text(error: Exception) -> str:
        return f"{type(error).__name__}: {error}"

    @staticmethod
    def _resolve_speaker_ownership(
        context: ExtractionContext,
        facts: list[FactDraft],
    ) -> list[FactDraft]:
        if not FIRST_PERSON_COMMITMENT.search(context.content):
            return facts

        return [
            fact.model_copy(
                update={
                    "owner_name": context.source_author_name,
                    "owner_discord_id": context.source_author_id,
                }
            )
            if fact.type == FactType.COMMITMENT
            and fact.owner_name is None
            and fact.owner_discord_id is None
            else fact
            for fact in facts
        ]
