import unittest

from sqlalchemy import Text

from colorstack_ai.db.models import ReasoningUsageRecord


class ReasoningUsageSchemaTest(unittest.TestCase):
    def test_request_metadata_accepts_descriptive_values(self) -> None:
        table = ReasoningUsageRecord.__table__

        self.assertIsInstance(table.c.scope.type, Text)
        self.assertIsInstance(table.c.intent.type, Text)
