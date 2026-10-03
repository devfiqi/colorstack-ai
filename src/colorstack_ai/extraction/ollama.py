import json
from datetime import datetime
from typing import Any

import httpx
from pydantic import ValidationError

from colorstack_ai.extraction.models import (
    ExtractionContext,
    ExtractionResponse,
)
from colorstack_ai.extraction.prompt import SYSTEM_PROMPT, build_user_prompt
from colorstack_ai.intake.prompt import (
    SYSTEM_PROMPT as INTAKE_SYSTEM_PROMPT,
    build_user_prompt as build_intake_prompt,
)


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout_seconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.model = model
        self.server_version: str | None = None
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout_seconds,
            transport=transport,
        )

    async def validate(self) -> None:
        try:
            version_response = await self._client.get("/api/version")
            version_response.raise_for_status()
            self.server_version = str(
                version_response.json().get("version", "unknown")
            )

            tags_response = await self._client.get("/api/tags")
            tags_response.raise_for_status()
        except (httpx.HTTPError, ValueError) as error:
            raise OllamaError(
                "Could not reach Ollama locally. Start it with `ollama serve` "
                "or open the Ollama application."
            ) from error

        installed_models = {
            str(model.get("name") or model.get("model"))
            for model in tags_response.json().get("models", [])
        }
        if self.model not in installed_models:
            available = ", ".join(sorted(installed_models)) or "none"
            raise OllamaError(
                f"Ollama model {self.model!r} is not installed. "
                f"Available models: {available}. Run `ollama pull <model>`."
            )

    async def extract(
        self,
        context: ExtractionContext,
    ) -> tuple[ExtractionResponse, dict[str, Any]]:
        return await self._extract_structured(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=build_user_prompt(context),
        )

    async def extract_intake(
        self,
        *,
        source_id: str,
        source_type: str,
        title: str,
        content: str,
        occurred_at: datetime | None,
    ) -> tuple[ExtractionResponse, dict[str, Any]]:
        return await self._extract_structured(
            system_prompt=INTAKE_SYSTEM_PROMPT,
            user_prompt=build_intake_prompt(
                source_id=source_id,
                source_type=source_type,
                title=title,
                content=content,
                occurred_at=occurred_at,
            ),
        )

    async def _extract_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> tuple[ExtractionResponse, dict[str, Any]]:
        try:
            response = await self._client.post(
                "/api/chat",
                json={
                    "model": self.model,
                    "stream": False,
                    "format": ExtractionResponse.model_json_schema(),
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "options": {"temperature": 0},
                },
            )
            response.raise_for_status()
            content = response.json()["message"]["content"]
            raw_output = json.loads(content)
            if not isinstance(raw_output, dict):
                raise ValueError("Ollama output must be a JSON object")
            extraction = ExtractionResponse.model_validate(raw_output)
            return extraction, raw_output
        except (httpx.HTTPError, KeyError, TypeError, ValueError, ValidationError) as error:
            raise OllamaError(
                f"Ollama returned invalid extraction output: {error}"
            ) from error

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "OllamaClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()
