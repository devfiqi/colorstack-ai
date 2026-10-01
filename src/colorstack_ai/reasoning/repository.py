from datetime import UTC, datetime
from uuid import UUID

from colorstack_ai.db.models import ReasoningUsageRecord
from colorstack_ai.db.session import Database
from colorstack_ai.reasoning.models import ProviderResult, ReasoningRequest


class ReasoningRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def start(
        self,
        *,
        provider: str,
        model: str,
        request: ReasoningRequest,
        query_hash: str,
        context_chars: int,
        context_stats: dict[str, object],
    ) -> UUID:
        record = ReasoningUsageRecord(
            provider=provider,
            model=model,
            mode=request.mode.value,
            scope=request.scope,
            intent=request.intent,
            query_hash=query_hash,
            prompt_version=request.prompt_version,
            status="started",
            context_chars=context_chars,
            context_stats=context_stats,
        )
        async with self._database.sessions.begin() as session:
            session.add(record)
            await session.flush()
        return record.id

    async def succeed(
        self,
        request_id: UUID,
        result: ProviderResult,
        *,
        latency_ms: int,
        estimated_cost: float | None,
    ) -> None:
        async with self._database.sessions.begin() as session:
            record = await session.get(ReasoningUsageRecord, request_id)
            if record is None:
                raise RuntimeError(f"Reasoning usage {request_id} was not found.")
            record.status = "completed"
            record.completed_at = datetime.now(UTC)
            record.latency_ms = latency_ms
            record.input_tokens = result.usage.input_tokens
            record.output_tokens = result.usage.output_tokens
            record.total_tokens = result.usage.total_tokens
            record.estimated_cost = estimated_cost
            record.provider_request_id = result.provider_request_id

    async def fail(
        self,
        request_id: UUID,
        error: str,
        *,
        latency_ms: int,
    ) -> None:
        async with self._database.sessions.begin() as session:
            record = await session.get(ReasoningUsageRecord, request_id)
            if record is None:
                raise RuntimeError(f"Reasoning usage {request_id} was not found.")
            record.status = "failed"
            record.completed_at = datetime.now(UTC)
            record.latency_ms = latency_ms
            record.error = error[:2000]
