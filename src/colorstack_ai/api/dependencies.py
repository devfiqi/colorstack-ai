from fastapi import HTTPException, Request

from colorstack_ai.advisor.service import AdvisorService
from colorstack_ai.api.service import DashboardService
from colorstack_ai.config import load_reasoning_environment
from colorstack_ai.context.builder import ContextBuilder
from colorstack_ai.context.config import load_context_limits
from colorstack_ai.context.retrieval import RetrievalService
from colorstack_ai.db.session import Database
from colorstack_ai.intake.repository import IntakeRepository
from colorstack_ai.reasoning.providers.openai import OpenAIReasoningProvider
from colorstack_ai.reasoning.repository import ReasoningRepository
from colorstack_ai.reasoning.service import ReasoningService


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


def get_intake_repository(request: Request) -> IntakeRepository:
    factory = getattr(request.app.state, "intake_repository_factory", None)
    if factory is not None:
        return factory()
    return IntakeRepository(get_database(request))


def get_advisor_service(request: Request) -> AdvisorService:
    factory = getattr(request.app.state, "advisor_service_factory", None)
    if factory is not None:
        return factory()
    try:
        environment = load_reasoning_environment()
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    database = get_database(request)
    provider = OpenAIReasoningProvider(
        api_key=environment.openai_api_key.get_secret_value(),
        model=environment.model,
        timeout_seconds=environment.timeout_seconds,
    )
    reasoning = ReasoningService(
        provider,
        ReasoningRepository(database),
        max_context_chars=environment.max_context_chars,
        input_cost_per_million=environment.input_cost_per_million,
        output_cost_per_million=environment.output_cost_per_million,
    )
    return AdvisorService(
        ContextBuilder(RetrievalService(database), load_context_limits()),
        IntakeRepository(database),
        reasoning,
        max_output_tokens=environment.max_output_tokens,
    )
