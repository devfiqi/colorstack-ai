from colorstack_ai.briefing.repository import BriefRunRepository
from colorstack_ai.briefing.service import BriefingService
from colorstack_ai.config import ReasoningEnvironment
from colorstack_ai.context.builder import ContextBuilder
from colorstack_ai.context.config import load_context_limits
from colorstack_ai.context.retrieval import RetrievalService
from colorstack_ai.db.session import Database
from colorstack_ai.reasoning.providers.openai import OpenAIReasoningProvider
from colorstack_ai.reasoning.repository import ReasoningRepository
from colorstack_ai.reasoning.service import ReasoningService


def create_briefing_service(
    database: Database,
    environment: ReasoningEnvironment,
    *,
    channel_id: str | None,
) -> BriefingService:
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
    return BriefingService(
        ContextBuilder(RetrievalService(database), load_context_limits()),
        reasoning,
        BriefRunRepository(database),
        channel_id=channel_id,
        max_output_tokens=environment.max_output_tokens,
    )
