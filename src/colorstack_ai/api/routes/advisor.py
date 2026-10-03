from fastapi import APIRouter, Depends

from colorstack_ai.advisor.models import AdvisorAnswer, AdvisorQuestion
from colorstack_ai.advisor.service import AdvisorService
from colorstack_ai.api.dependencies import get_advisor_service

router = APIRouter(prefix="/api/advisor", tags=["advisor"])


@router.post("/questions", response_model=AdvisorAnswer)
async def ask_advisor(
    request: AdvisorQuestion,
    service: AdvisorService = Depends(get_advisor_service),
) -> AdvisorAnswer:
    return await service.answer(request.question)
