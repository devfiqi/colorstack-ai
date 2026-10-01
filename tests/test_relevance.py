import unittest
from datetime import UTC, datetime

from colorstack_ai.extraction.models import ExtractionContext
from colorstack_ai.extraction.relevance import assess_relevance


def context(content: str) -> ExtractionContext:
    return ExtractionContext(
        source_message_id="1",
        reply_to_message_id=None,
        source_author_id="2",
        source_author_name="Member",
        channel_name="events",
        created_at=datetime.now(UTC),
        content=content,
        messages=[],
    )


class RelevanceFilterTest(unittest.TestCase):
    def test_commitment_with_deadline_is_relevant(self) -> None:
        decision = assess_relevance(
            context("I'll handle food for the Adobe event by Friday.")
        )

        self.assertTrue(decision.is_relevant)
        self.assertIn("ownership or commitment", decision.reasons)
        self.assertIn("date or deadline", decision.reasons)

    def test_low_value_chatter_is_skipped(self) -> None:
        decision = assess_relevance(context("lol that was wild"))

        self.assertFalse(decision.is_relevant)
        self.assertEqual(decision.reason_text, "no signals")

    def test_reply_to_relevant_message_is_conservatively_included(self) -> None:
        decision = assess_relevance(
            context("yeah I can do it"),
            reply_is_relevant=True,
        )

        self.assertTrue(decision.is_relevant)
        self.assertIn("reply to relevant message", decision.reasons)
