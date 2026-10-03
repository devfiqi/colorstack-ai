import unittest
from datetime import UTC, datetime
from typing import cast
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from colorstack_ai.api.app import create_app
from colorstack_ai.api.schemas import (
    EventListItem,
    OverviewResponse,
    PriorityItem,
    TaskResponse,
)
from colorstack_ai.api.service import DashboardService
from colorstack_ai.db.session import Database


class FakeDatabase:
    async def check_connection(self) -> None:
        return None

    async def close(self) -> None:
        return None


class FakeDashboardService:
    async def overview(self) -> OverviewResponse:
        event = EventListItem(
            id="11111111-1111-1111-1111-111111111111",
            name="Adobe Ideathon",
            date="Oct 22",
            type="Ideathon",
            phase="upcoming",
            readiness=63,
            urgency="high",
            owner="Salman",
            blocker="Judges missing",
            next_action="Begin judge outreach",
        )
        return OverviewResponse(
            generated_at=datetime(2026, 10, 1, tzinfo=UTC),
            active_events=1,
            high_priority=1,
            open_tasks=2,
            deadlines_this_week=1,
            priorities=[
                PriorityItem(
                    id="p1",
                    title="Begin judge outreach",
                    owner="Salman",
                    due="Today",
                    priority="high",
                    context="No judges confirmed.",
                )
            ],
            events=[event],
            attention=[],
            changes=[],
        )

    async def tasks(self, **filters: object) -> list[TaskResponse]:
        self.filters = filters
        return [
            TaskResponse(
                id="task-1",
                task="Begin judge outreach",
                event_id="11111111-1111-1111-1111-111111111111",
                event="Adobe Ideathon",
                owner="Salman",
                owner_group="execs",
                status="open",
                priority="high",
                deadline="Oct 3",
                source="Current state",
            )
        ]

    async def event(self, event_id: object) -> None:
        return None


class DashboardApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = FakeDashboardService()
        app = create_app(cast(Database, FakeDatabase()))
        app.state.dashboard_service_factory = lambda: cast(
            DashboardService,
            self.service,
        )
        self.client = TestClient(app)

    def test_overview_uses_frontend_contract_aliases(self) -> None:
        with self.client:
            response = self.client.get("/api/overview")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["activeEvents"], 1)
        self.assertEqual(payload["events"][0]["nextAction"], "Begin judge outreach")

    def test_task_filters_are_forwarded(self) -> None:
        with self.client:
            response = self.client.get(
                "/api/tasks?status=open&owner=Salman&event=Adobe&urgency=high"
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.service.filters,
            {
                "status": "open",
                "owner": "Salman",
                "event": "Adobe",
                "urgency": "high",
            },
        )

    def test_missing_event_returns_404(self) -> None:
        with self.client:
            response = self.client.get(
                "/api/events/11111111-1111-1111-1111-111111111111"
            )
        self.assertEqual(response.status_code, 404)

    def test_system_status_reflects_configuration_presence(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "DISCORD_TOKEN": "test",
                "OLLAMA_MODEL": "test-model",
                "REASONING_MODEL": "test-reasoning-model",
                "OPENAI_API_KEY": "test",
                "DAILY_BRIEF_ENABLED": "false",
            },
            clear=False,
        ):
            with patch(
                "colorstack_ai.api.routes.system.PipelineRepository.latest",
                new_callable=AsyncMock,
                return_value=None,
            ):
                with self.client:
                    response = self.client.get("/api/system")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["discord"], "Configured")
        self.assertEqual(payload["extraction"], "Configured")
        self.assertEqual(payload["reasoning"], "Configured")
        self.assertTrue(payload["advisoryOnly"])
        self.assertFalse(payload["automaticActions"])

    def test_system_status_alias(self) -> None:
        with patch.dict(
            "os.environ",
            {"DAILY_BRIEF_ENABLED": "false"},
            clear=False,
        ):
            with patch(
                "colorstack_ai.api.routes.system.PipelineRepository.latest",
                new_callable=AsyncMock,
                return_value=None,
            ):
                with self.client:
                    response = self.client.get("/api/system/status")
        self.assertEqual(response.status_code, 200)
