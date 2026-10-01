import unittest
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from colorstack_ai.state.models import (
    CurrentValue,
    EntityType,
    FactEnvelope,
)
from colorstack_ai.state.policy import evaluate_update, proposals_for_fact


def fact(**overrides: object) -> FactEnvelope:
    values: dict[str, object] = {
        "id": uuid4(),
        "source_message_id": "message",
        "extraction_version": "v1",
        "ordinal": 0,
        "fact_type": "location_change",
        "event_name": "Adobe Ideathon",
        "task": None,
        "owner_name": None,
        "owner_discord_id": None,
        "deadline_text": None,
        "normalized_deadline": None,
        "status": None,
        "value": "Rapson Hall",
        "confidence": 0.9,
        "evidence_kind": "explicit",
        "guild_id": "guild",
        "channel_id": "channel",
        "thread_id": None,
        "reply_to_message_id": None,
        "message_created_at": datetime.now(UTC),
        "message_content": "The room is Rapson Hall.",
    }
    values.update(overrides)
    return FactEnvelope.model_validate(values)


class StatePolicyTest(unittest.TestCase):
    def test_inferred_update_cannot_replace_explicit_state(self) -> None:
        candidate = fact(evidence_kind="inferred", confidence=0.99)
        proposal = proposals_for_fact(candidate, EntityType.EVENT)[0]
        current = CurrentValue(
            value={"text": "Lind Hall"},
            confidence=0.8,
            evidence_kind="explicit",
            effective_at=candidate.message_created_at - timedelta(days=1),
        )

        decision = evaluate_update(
            current=current,
            proposal=proposal,
            fact=candidate,
        )

        self.assertFalse(decision.apply)
        self.assertIn("inferred", decision.reason)

    def test_exact_deadline_replaces_vague_deadline(self) -> None:
        candidate = fact(
            fact_type="deadline",
            value=None,
            deadline_text="October 10 at 5 PM",
            normalized_deadline=datetime(2026, 10, 10, 22, tzinfo=UTC),
        )
        proposal = proposals_for_fact(candidate, EntityType.EVENT)[0]
        current = CurrentValue(
            value={"text": "next week", "normalized": None, "exact": False},
            confidence=0.95,
            evidence_kind="explicit",
            effective_at=candidate.message_created_at - timedelta(days=1),
        )

        decision = evaluate_update(
            current=current,
            proposal=proposal,
            fact=candidate,
        )

        self.assertTrue(decision.apply)

    def test_completed_task_requires_explicit_reopen(self) -> None:
        candidate = fact(
            fact_type="status_change",
            event_name=None,
            task="Find judges",
            status="in_progress",
            value=None,
            message_content="We reopened finding judges.",
        )
        proposal = proposals_for_fact(candidate, EntityType.TASK)[0]
        current = CurrentValue(
            value={"text": "completed"},
            confidence=0.9,
            evidence_kind="explicit",
            effective_at=candidate.message_created_at - timedelta(days=1),
        )

        decision = evaluate_update(
            current=current,
            proposal=proposal,
            fact=candidate,
        )

        self.assertTrue(decision.apply)
        self.assertEqual(decision.outcome, "reopen")
