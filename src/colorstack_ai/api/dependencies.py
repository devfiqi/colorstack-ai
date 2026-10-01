from fastapi import Request

from colorstack_ai.api.service import DashboardService
from colorstack_ai.context.config import load_context_limits
from colorstack_ai.db.session import Database


def get_database(request: Request) -> Database:
    return request.app.state.database


def get_dashboard_service(request: Request) -> DashboardService:
    factory = getattr(request.app.state, "dashboard_service_factory", None)
    if factory is not None:
        return factory()
    return DashboardService(
        get_database(request),
        limits=load_context_limits(),
    )
