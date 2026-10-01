import unittest

from pydantic import ValidationError

from colorstack_ai.extraction.models import ExtractionResponse


class ExtractionSchemaTest(unittest.TestCase):
    def test_no_fact_response_is_valid(self) -> None:
        response = ExtractionResponse.model_validate({"facts": []})
        self.assertEqual(response.facts, [])

    def test_multiple_facts_are_validated(self) -> None:
        response = ExtractionResponse.model_validate(
            {
                "facts": [
                    {
                        "type": "commitment",
                        "event_name": "Adobe Ideathon",
                        "task": "Handle food",
                        "owner_name": "Member",
                        "owner_discord_id": "123",
                        "deadline_text": "Friday",
                        "normalized_deadline": None,
                        "status": "open",
                        "value": None,
                        "confidence": 0.95,
                        "evidence_kind": "explicit",
                    },
                    {
                        "type": "deadline",
                        "event_name": "Adobe Ideathon",
                        "task": "Handle food",
                        "owner_name": None,
                        "owner_discord_id": None,
                        "deadline_text": "Friday",
                        "normalized_deadline": None,
                        "status": None,
                        "value": "Friday",
                        "confidence": 0.9,
                        "evidence_kind": "explicit",
                    },
                ]
            }
        )
        self.assertEqual(len(response.facts), 2)

    def test_invalid_confidence_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            ExtractionResponse.model_validate(
                {
                    "facts": [
                        {
                            "type": "task",
                            "confidence": 1.5,
                            "evidence_kind": "explicit",
                        }
                    ]
                }
            )
