import json
from types import TracebackType
from typing import Any, Protocol, Self

import httpx
from pydantic import ValidationError

from colorstack_ai.state.models import (
    AmbiguityResponse,
    EntityResolution,
    FactEnvelope,
)
from colorstack_ai.state.prompt import SYSTEM_PROMPT


class AmbiguityError(RuntimeError):
    pass


class AmbiguityResolver(Protocol):
    async def interpret(
        self,
        fact: FactEnvelope,
        resolution: EntityResolution,
    ) -> tuple[AmbiguityResponse, dict[str, Any]]: ...


class OllamaAmbiguityResolver:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout_seconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.model = model
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout_seconds,
            transport=transport,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    async def validate(self) -> None:
        try:
            response = await self._client.get("/api/tags")
            response.raise_for_status()
            models = response.json().get("models", [])
            names = {
                item.get("name")
                for item in models
                if isinstance(item, dict)
            }
            if self.model not in names:
                raise AmbiguityError(
                    f"Ollama model {self.model!r} is not installed."
                )
        except (httpx.HTTPError, ValueError, TypeError) as error:
            raise AmbiguityError(
                "Could not validate the local Ollama model."
            ) from error

    async def interpret(
        self,
        fact: FactEnvelope,
        resolution: EntityResolution,
    ) -> tuple[AmbiguityResponse, dict[str, Any]]:
        payload = {
            "model": self.model,
            "stream": False,
            "format": AmbiguityResponse.model_json_schema(),
            "options": {"temperature": 0},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "resolved_entity_type": resolution.entity_type,
                            "fact": fact.model_dump(
                                mode="json",
                                exclude={"message_content"},
                            ),
                            "source_message": fact.message_content[:2_000],
                        }
                    ),
                },
            ],
        }
        try:
            response = await self._client.post("/api/chat", json=payload)
            response.raise_for_status()
            raw = response.json()
            content = raw["message"]["content"]
            parsed = json.loads(content)
            return AmbiguityResponse.model_validate(parsed), raw
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
            ValidationError,
        ) as error:
            raise AmbiguityError(
                "Ollama returned an invalid ambiguity proposal."
            ) from error
