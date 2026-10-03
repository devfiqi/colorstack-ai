import unittest
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from colorstack_ai.advisor.models import AdvisorAnswer
from colorstack_ai.advisor.service import AdvisorService
from colorstack_ai.api.app import create_app
from colorstack_ai.db.session import Database
from colorstack_ai.extraction.models import (
    EvidenceKind,
    FactDraft,
    FactStatus,
    FactType,
)
from colorstack_ai.intake.models import (
    IntakeProposal,
    IntakeReview,
    IntakeSource,
    IntakeSourceCreate,
    IntakeSourceStatus,
    IntakeSourceType,
    IntakeSummary,
    ProposalStatus,
)
from colorstack_ai.intake.repository import IntakeRepository


class _FakeDatabase:
    async def check_connection(self) -> None:
        return None

    async def close(self) -> None:
        return None


class _FakeIntakeRepository:
    def __init__(self) -> None:
        self.source_id = uuid4()
        self.proposal_id = uuid4()
        self.reviewed: IntakeReview | None = None

    def source(self) -> IntakeSource:
        now = datetime(2026, 10, 2, tzinfo=UTC)
        return IntakeSource(
            id=self.source_id,
            title="Board notes",
            source_type=IntakeSourceType.MEETING_NOTES,
            content="Jordan will reserve the room.",
            occurred_at=now,
            status=IntakeSourceStatus.PROCESSED,
            error=None,
            created_at=now,
            updated_at=now,
            proposals=[
                IntakeProposal(
                    id=self.proposal_id,
                    ordinal=0,
                    fact=FactDraft(
                        type=FactType.TASK,
                        task="Reserve the room",
                        status=FactStatus.OPEN,
                        confidence=0.95,
                        evidence_kind=EvidenceKind.EXPLICIT,
                    ),
                    status=(
                        self.reviewed.status
                        if self.reviewed is not None
                        else ProposalStatus.PENDING
                    ),
                )
            ],
        )

    async def create(self, request: IntakeSourceCreate) -> IntakeSource:
        return self.source()

    async def list_sources(self, *, limit: int) -> list[IntakeSummary]:
        source = self.source()
        return [
            IntakeSummary(
                id=source.id,
                title=source.title,
                source_type=source.source_type,
                status=source.status,
                created_at=source.created_at,
                proposal_count=1,
                pending_count=1,
            )
        ][:limit]

    async def get(self, source_id: UUID) -> IntakeSource | None:
        return self.source() if source_id == self.source_id else None

    async def retry(self, source_id: UUID) -> bool:
        return source_id == self.source_id

    async def review(
        self,
        proposal_id: UUID,
        review: IntakeReview,
    ) -> IntakeProposal | None:
        if proposal_id != self.proposal_id:
            return None
        self.reviewed = review
        return self.source().proposals[0]


class _FakeAdvisorService:
    async def answer(self, question: str) -> AdvisorAnswer:
        return AdvisorAnswer(warnings=[f"Clarify: {question}"])


class Phase2ApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.intake = _FakeIntakeRepository()
        app = create_app(cast(Database, _FakeDatabase()))
        app.state.intake_repository_factory = lambda: cast(
            IntakeRepository, self.intake
        )
        app.state.advisor_service_factory = lambda: cast(
            AdvisorService, _FakeAdvisorService()
        )
        self.client = TestClient(app)

    def test_create_and_review_intake_source(self) -> None:
        with self.client:
            created = self.client.post(
                "/api/intake/sources",
                json={
                    "title": "Board notes",
                    "source_type": "meeting_notes",
                    "content": "Jordan will reserve the room.",
                },
            )
            reviewed = self.client.patch(
                f"/api/intake/proposals/{self.intake.proposal_id}",
                json={"status": "approved"},
            )

        self.assertEqual(created.status_code, 202)
        self.assertEqual(reviewed.status_code, 200)
        self.assertEqual(reviewed.json()["status"], "approved")

    def test_advisor_question_route(self) -> None:
        with self.client:
            response = self.client.post(
                "/api/advisor/questions",
                json={"question": "What needs my attention?"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["warnings"],
            ["Clarify: What needs my attention?"],
        )
