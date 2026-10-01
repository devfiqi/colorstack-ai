import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from colorstack_ai.playbooks.detection import detect_playbooks
from colorstack_ai.playbooks.loader import PlaybookError, PlaybookLoader
from colorstack_ai.playbooks.models import (
    Criticality,
    RequirementDefinition,
    RequirementResult,
    RequirementStatus,
)
from colorstack_ai.playbooks.scoring import (
    calculate_urgency,
    readiness_points,
    readiness_score,
)


class PlaybookLoaderTest(unittest.TestCase):
    def test_built_in_playbooks_validate(self) -> None:
        definitions = PlaybookLoader().load_all()

        self.assertEqual(len(definitions), 7)
        self.assertGreaterEqual(
            sum(len(item.requirements) for item in definitions),
            100,
        )
        self.assertIn("ideathon", {item.key for item in definitions})
        self.assertTrue(
            next(
                item
                for item in definitions
                if item.key == "company_sponsored"
            ).overlay
        )

    def test_custom_playbook_can_extend_a_generic_definition(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "base.yaml").write_text(
                """
key: base
name: Base
event_type: workshop
version: "1"
requirements:
  - key: venue
    name: Venue
"""
            )
            custom = root / "custom"
            custom.mkdir()
            (custom / "colorstack.yaml").write_text(
                """
key: colorstack
name: ColorStack Workshop
event_type: workshop
version: "1"
extends: [base]
requirements:
  - key: venue
    name: Accessible venue
    required: true
"""
            )

            definitions = PlaybookLoader(root).load_all()

        extended = next(item for item in definitions if item.key == "colorstack")
        self.assertEqual(len(extended.requirements), 1)
        self.assertTrue(extended.requirements[0].required)
        self.assertEqual(extended.requirements[0].name, "Accessible venue")

    def test_unknown_dependency_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.yaml"
            path.write_text(
                """
key: bad
name: Bad
event_type: panel
version: "1"
requirements:
  - key: questions
    name: Questions
    dependencies: [missing]
"""
            )
            with self.assertRaisesRegex(PlaybookError, "unknown dependencies"):
                PlaybookLoader(Path(directory)).load_all()


class EventTypeDetectionTest(unittest.TestCase):
    def test_ideathon_and_sponsor_overlay_are_detected(self) -> None:
        definitions = PlaybookLoader().load_all()

        detected = detect_playbooks(
            event_name="Adobe Ideathon",
            aliases=["Adobe event"],
            state_text=["sponsor Adobe confirmed"],
            fact_text=[],
            definitions=definitions,
        )

        self.assertEqual(
            {item.key for item in detected},
            {"ideathon", "company_sponsored"},
        )

    def test_unknown_type_is_not_forced(self) -> None:
        detected = detect_playbooks(
            event_name="October Event",
            aliases=[],
            state_text=[],
            fact_text=[],
            definitions=PlaybookLoader().load_all(),
        )

        self.assertEqual(detected, [])


class ScoringTest(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 10, 1, tzinfo=UTC)
        self.requirement = RequirementDefinition(
            key="judges",
            name="Judges",
            required=True,
            criticality=Criticality.CRITICAL,
            ideal_lead_days=21,
            minimum_lead_days=10,
        )

    def test_urgency_increases_as_event_approaches(self) -> None:
        medium, _ = calculate_urgency(
            requirement=self.requirement,
            status=RequirementStatus.MISSING,
            event_at=self.now + timedelta(days=30),
            now=self.now,
            dependent_count=1,
            sponsored_event=False,
        )
        high, _ = calculate_urgency(
            requirement=self.requirement,
            status=RequirementStatus.MISSING,
            event_at=self.now + timedelta(days=14),
            now=self.now,
            dependent_count=1,
            sponsored_event=False,
        )
        critical, _ = calculate_urgency(
            requirement=self.requirement,
            status=RequirementStatus.MISSING,
            event_at=self.now + timedelta(days=5),
            now=self.now,
            dependent_count=1,
            sponsored_event=False,
        )

        self.assertEqual(medium, "medium")
        self.assertEqual(high, "high")
        self.assertEqual(critical, "critical")

    def test_readiness_weights_required_critical_work_more(self) -> None:
        critical_weight, critical_earned = readiness_points(
            self.requirement,
            RequirementStatus.MISSING,
        )
        optional = self.requirement.model_copy(
            update={
                "key": "photos",
                "required": False,
                "criticality": Criticality.LOW,
            }
        )
        optional_weight, optional_earned = readiness_points(
            optional,
            RequirementStatus.COMPLETE,
        )
        results = [
            RequirementResult(
                requirement_key="judges",
                requirement_name="Judges",
                required=True,
                criticality=Criticality.CRITICAL,
                status=RequirementStatus.MISSING,
                urgency="high",
                confidence=1,
                evidence=[],
                rationale="missing",
                recommendation="act",
                readiness_weight=critical_weight,
                readiness_earned=critical_earned,
            ),
            RequirementResult(
                requirement_key="photos",
                requirement_name="Photos",
                required=False,
                criticality=Criticality.LOW,
                status=RequirementStatus.COMPLETE,
                urgency="low",
                confidence=1,
                evidence=[],
                rationale="done",
                recommendation=None,
                readiness_weight=optional_weight,
                readiness_earned=optional_earned,
            ),
        ]

        self.assertEqual(critical_weight, 4)
        self.assertEqual(optional_weight, 0.4)
        self.assertLess(readiness_score(results), 10)
