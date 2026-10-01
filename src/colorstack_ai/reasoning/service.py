import hashlib
import json
from time import monotonic

from colorstack_ai.reasoning.models import (
    ReasoningRequest,
    ReasoningRunResult,
)
from colorstack_ai.reasoning.providers.base import ReasoningProvider
from colorstack_ai.reasoning.repository import ReasoningRepository


class ReasoningService:
    def __init__(
        self,
        provider: ReasoningProvider,
        repository: ReasoningRepository,
        *,
        max_context_chars: int,
        input_cost_per_million: float | None = None,
        output_cost_per_million: float | None = None,
    ) -> None:
        self._provider = provider
        self._repository = repository
        self._max_context_chars = max_context_chars
        self._input_cost = input_cost_per_million
        self._output_cost = output_cost_per_million

    async def run(self, request: ReasoningRequest) -> ReasoningRunResult:
        context_json = request.context.model_dump_json()
        context_chars = len(context_json)
        if context_chars > self._max_context_chars:
            raise RuntimeError(
                "Structured context exceeds REASONING_MAX_CONTEXT_CHARS."
            )
        query_hash = hashlib.sha256(request.query.encode()).hexdigest()
        context = request.context.context
        stats = {
            "kind": getattr(context, "kind", None),
            "warnings": len(request.context.warnings),
        }
        request_id = await self._repository.start(
            provider=self._provider.provider_name,
            model=self._provider.model,
            request=request,
            query_hash=query_hash,
            context_chars=context_chars,
            context_stats=stats,
        )
        started = monotonic()
        try:
            provider_result = await self._provider.reason(request)
        except Exception as error:
            latency_ms = round((monotonic() - started) * 1000)
            await self._repository.fail(
                request_id,
                str(error) or type(error).__name__,
                latency_ms=latency_ms,
            )
            raise

        latency_ms = round((monotonic() - started) * 1000)
        estimated_cost = self._estimate_cost(
            provider_result.usage.input_tokens,
            provider_result.usage.output_tokens,
        )
        await self._repository.succeed(
            request_id,
            provider_result,
            latency_ms=latency_ms,
            estimated_cost=estimated_cost,
        )
        return ReasoningRunResult(
            request_id=request_id,
            response=provider_result.response,
            provider=self._provider.provider_name,
            model=self._provider.model,
            usage=provider_result.usage,
            estimated_cost=estimated_cost,
            latency_ms=latency_ms,
        )

    def _estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
    ) -> float | None:
        if self._input_cost is None or self._output_cost is None:
            return None
        return (
            input_tokens * self._input_cost
            + output_tokens * self._output_cost
        ) / 1_000_000
