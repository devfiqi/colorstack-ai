from typing import Protocol

from colorstack_ai.reasoning.models import ProviderResult, ReasoningRequest


class ReasoningProviderError(RuntimeError):
    pass


class ReasoningProvider(Protocol):
    provider_name: str
    model: str

    async def reason(self, request: ReasoningRequest) -> ProviderResult: ...
