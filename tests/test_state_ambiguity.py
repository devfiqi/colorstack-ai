import json
import unittest
from datetime import UTC, datetime
from uuid import uuid4

import httpx

from colorstack_ai.state.ambiguity import (
    AmbiguityError,
    OllamaAmbiguityResolver,
)
from colorstack_ai.state.models import (
    EntityResolution,
    EntityType,
    FactEnvelope,
)


def make_fact() -> FactEnvelope:
    return FactEnvelope(
        id=uuid4(),
        source_message_id="message",
        extraction_version="v1",
        ordinal=0,
        fact_type="event_update",
        event_name="Adobe Ideathon",
        task=None,
        owner_name=None,
        owner_discord_id=None,
        deadline_text=None,
        normalized_deadline=None,
        status=None,
        value="Do not worry about judges anymore.",
        confidence=0.8,
        evidence_kind="explicit",
        guild_id="guild",
        channel_id="channel",
        thread_id=None,
        reply_to_message_id=None,
        message_created_at=datetime.now(UTC),
        message_content="Don't worry about the judges anymore.",
    )


class StateAmbiguityTest(unittest.IsolatedAsyncioTestCase):
    async def test_validated_proposal_is_parsed(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
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
                            "content": json.dumps(
                                {
                                    "proposal": {
                                        "entity_type": "event",
                                        "field": "judges_speakers",
                                        "value": {
                                            "text": "no longer required"
                                        },
                                        "change_type": "cancellation",
                                        "confidence": 0.75,
                                        "reason": "explicitly no longer needed",
                                    }
                                }
                            )
                        }
                    },
                )
            return httpx.Response(404)

        resolver = OllamaAmbiguityResolver(
            base_url="http://localhost:11434",
            model="test-model",
            timeout_seconds=1,
            transport=httpx.MockTransport(handler),
        )
        try:
            await resolver.validate()
            response, _ = await resolver.interpret(
                make_fact(),
                EntityResolution(
                    entity_type=EntityType.EVENT,
                    entity_id=uuid4(),
                    reason="test",
                    confidence=1,
                ),
            )
        finally:
            await resolver.close()

        self.assertIsNotNone(response.proposal)
        assert response.proposal is not None
        self.assertEqual(response.proposal.field, "judges_speakers")

    async def test_invalid_proposal_is_rejected(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={"message": {"content": '{"proposal":{"field":"made_up"}}'}},
            )

        resolver = OllamaAmbiguityResolver(
            base_url="http://localhost:11434",
            model="test-model",
            timeout_seconds=1,
            transport=httpx.MockTransport(handler),
        )
        try:
            with self.assertRaises(AmbiguityError):
                await resolver.interpret(
                    make_fact(),
                    EntityResolution(
                        entity_type=EntityType.EVENT,
                        entity_id=uuid4(),
                        reason="test",
                        confidence=1,
                    ),
                )
        finally:
            await resolver.close()
