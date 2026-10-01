import json
import unittest
from datetime import UTC, datetime

import httpx

from colorstack_ai.extraction.models import ExtractionContext
from colorstack_ai.extraction.ollama import OllamaClient, OllamaError


def make_context() -> ExtractionContext:
    return ExtractionContext(
        source_message_id="1",
        reply_to_message_id=None,
        source_author_id="2",
        source_author_name="Member",
        channel_name="events",
        created_at=datetime.now(UTC),
        content="No organizational content here.",
        messages=[],
    )


class OllamaClientTest(unittest.IsolatedAsyncioTestCase):
    async def test_no_fact_response_is_parsed_without_live_model(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/api/version":
                return httpx.Response(200, json={"version": "test"})
            if request.url.path == "/api/tags":
                return httpx.Response(
                    200,
                    json={"models": [{"name": "test-model"}]},
                )
            if request.url.path == "/api/chat":
                return httpx.Response(
                    200,
                    json={
                        "message": {
                            "content": json.dumps({"facts": []}),
                        }
                    },
                )
            return httpx.Response(404)

        client = OllamaClient(
            base_url="http://localhost:11434",
            model="test-model",
            timeout_seconds=1,
            transport=httpx.MockTransport(handler),
        )
        try:
            await client.validate()
            response, raw = await client.extract(make_context())
        finally:
            await client.close()

        self.assertEqual(response.facts, [])
        self.assertEqual(raw, {"facts": []})

    async def test_missing_model_has_clear_error(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/api/version":
                return httpx.Response(200, json={"version": "test"})
            return httpx.Response(
                200,
                json={"models": [{"name": "installed-model"}]},
            )

        client = OllamaClient(
            base_url="http://localhost:11434",
            model="missing-model",
            timeout_seconds=1,
            transport=httpx.MockTransport(handler),
        )
        try:
            with self.assertRaisesRegex(OllamaError, "is not installed"):
                await client.validate()
        finally:
            await client.close()
