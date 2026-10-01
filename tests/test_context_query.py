import unittest
from datetime import UTC, datetime, timedelta

from pydantic import ValidationError

from colorstack_ai.context.models import (
    ContextLimits,
    ContextSource,
    MessageContextItem,
    RequirementContextItem,
)
from colorstack_ai.context.query_parser import parse_query
from colorstack_ai.context.ranking import (
    message_score,
    rank_requirements,
)


class QueryParserTest(unittest.TestCase):
    def test_event_missing_requirements_query(self) -> None:
        parsed = parse_query(
            "What are we missing for the Adobe Ideathon?"
        )
        self.assertEqual(parsed.scope, "event")
        self.assertEqual(parsed.intent, "missing_requirements")
        self.assertEqual(parsed.entity_text, "Adobe Ideathon")
        self.assertFalse(parsed.ambiguous)

    def test_owner_task_query(self) -> None:
        parsed = parse_query("Who owns food?")
        self.assertEqual(parsed.scope, "task")
        self.assertEqual(parsed.intent, "owner_lookup")
        self.assertEqual(parsed.entity_text, "food")

    def test_recent_event_query(self) -> None:
        parsed = parse_query("What changed with Adobe today?")
        self.assertEqual(parsed.scope, "event")
        self.assertEqual(parsed.intent, "recent_changes")
        self.assertEqual(parsed.entity_text, "Adobe")

    def test_person_responsibility_query(self) -> None:
        parsed = parse_query("What is Salman responsible for?")
        self.assertEqual(parsed.scope, "person")
        self.assertEqual(parsed.entity_text, "Salman")

    def test_board_meeting_query_is_organization_scope(self) -> None:
        parsed = parse_query(
            "What should we discuss at the next board meeting?"
        )
        self.assertEqual(parsed.scope, "organization")
        self.assertEqual(parsed.intent, "organization_status")

    def test_ambiguous_query_fails_closed(self) -> None:
        parsed = parse_query("What's happening?")
        self.assertTrue(parsed.ambiguous)
        self.assertEqual(parsed.scope, "unknown")


class ContextRankingTest(unittest.TestCase):
    def test_critical_missing_requirement_ranks_first(self) -> None:
        now = datetime.now(UTC)
        source = ContextSource(type="test", id="1")
        low = RequirementContextItem(
            requirement_id="low",
            playbook="test",
            key="photos",
            name="Photos",
            required=False,
            criticality="low",
            status="unknown",
            urgency="low",
            confidence=1,
            rationale="none",
            evidence=[source],
            evaluated_at=now,
        )
        critical = RequirementContextItem(
            requirement_id="critical",
            playbook="test",
            key="judges",
            name="Judges",
            required=True,
            criticality="critical",
            status="missing",
            urgency="critical",
            confidence=1,
            rationale="missing",
            evidence=[],
            evaluated_at=now,
        )

        ranked = rank_requirements(
            [low, critical],
            query=None,
            limit=1,
        )

        self.assertEqual(ranked[0].key, "judges")

    def test_provenance_outweighs_random_recency(self) -> None:
        now = datetime.now(UTC)
        linked_score, _ = message_score(
            content="Judge update",
            created_at=now - timedelta(days=2),
            query=None,
            entity_terms=set(),
            provenance_match=True,
            now=now,
        )
        random_score, _ = message_score(
            content="Unrelated chatter",
            created_at=now,
            query=None,
            entity_terms=set(),
            provenance_match=False,
            now=now,
        )
        self.assertGreater(linked_score, random_score)

    def test_limits_are_explicitly_bounded(self) -> None:
        limits = ContextLimits(messages=1, tasks=2, requirements=3)
        self.assertEqual(limits.messages, 1)
        with self.assertRaises(ValidationError):
            ContextLimits(messages=101)
