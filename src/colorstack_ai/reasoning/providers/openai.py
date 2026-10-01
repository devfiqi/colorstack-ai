from typing import Any

from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AsyncOpenAI,
    RateLimitError,
)

from colorstack_ai.reasoning.models import (
    ProviderResult,
    ProviderUsage,
    ReasoningRequest,
    ReasoningResponse,
)
from colorstack_ai.reasoning.prompts import SYSTEM_PROMPT, build_user_prompt
from colorstack_ai.reasoning.providers.base import ReasoningProviderError


class OpenAIReasoningProvider:
    provider_name = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        client: Any | None = None,
    ) -> None:
        self.model = model
        self._timeout_seconds = timeout_seconds
        self._client = client or AsyncOpenAI(
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=2,
        )

    async def reason(self, request: ReasoningRequest) -> ProviderResult:
        try:
            result = await self._client.responses.parse(
                model=self.model,
                instructions=SYSTEM_PROMPT,
                input=build_user_prompt(request),
                text_format=ReasoningResponse,
                max_output_tokens=request.max_output_tokens,
                store=False,
                timeout=self._timeout_seconds,
            )
        except APITimeoutError as error:
            raise ReasoningProviderError(
                "OpenAI reasoning request timed out."
            ) from error
        except RateLimitError as error:
            raise ReasoningProviderError(
                "OpenAI reasoning request was rate limited."
            ) from error
        except APIConnectionError as error:
            raise ReasoningProviderError(
                "Could not connect to the OpenAI reasoning API."
            ) from error
        except APIError as error:
            raise ReasoningProviderError(
                f"OpenAI reasoning request failed: {error}"
            ) from error
        except Exception as error:
            raise ReasoningProviderError(
                "OpenAI reasoning response could not be parsed."
            ) from error

        parsed = result.output_parsed
        if not isinstance(parsed, ReasoningResponse):
            raise ReasoningProviderError(
                "OpenAI returned no valid structured reasoning response."
            )
        usage = result.usage
        if usage is None:
            provider_usage = ProviderUsage(
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
            )
        else:
            provider_usage = ProviderUsage(
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                total_tokens=usage.total_tokens,
            )
        return ProviderResult(
            response=parsed,
            usage=provider_usage,
            provider_request_id=result.id,
        )
