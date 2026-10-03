from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from colorstack_ai.api.dependencies import get_intake_repository
from colorstack_ai.intake.models import (
    IntakeProposal,
    IntakeReview,
    IntakeSource,
    IntakeSourceCreate,
    IntakeSummary,
)
from colorstack_ai.intake.repository import IntakeRepository

router = APIRouter(prefix="/api/intake", tags=["vp-intake"])


@router.post(
    "/sources",
    response_model=IntakeSource,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_source(
    request: IntakeSourceCreate,
    repository: IntakeRepository = Depends(get_intake_repository),
) -> IntakeSource:
    return await repository.create(request)


@router.get("/sources", response_model=list[IntakeSummary])
async def list_sources(
    limit: int = Query(default=50, ge=1, le=100),
    repository: IntakeRepository = Depends(get_intake_repository),
) -> list[IntakeSummary]:
    return await repository.list_sources(limit=limit)


@router.get("/sources/{source_id}", response_model=IntakeSource)
async def get_source(
    source_id: UUID,
    repository: IntakeRepository = Depends(get_intake_repository),
) -> IntakeSource:
    source = await repository.get(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Intake source not found")
    return source


@router.post("/sources/{source_id}/retry", response_model=IntakeSource)
async def retry_source(
    source_id: UUID,
    repository: IntakeRepository = Depends(get_intake_repository),
) -> IntakeSource:
    if not await repository.retry(source_id):
        raise HTTPException(status_code=404, detail="Intake source not found")
    source = await repository.get(source_id)
    assert source is not None
    return source


@router.patch("/proposals/{proposal_id}", response_model=IntakeProposal)
async def review_proposal(
    proposal_id: UUID,
    review: IntakeReview,
    repository: IntakeRepository = Depends(get_intake_repository),
) -> IntakeProposal:
    if review.status.value == "pending":
        raise HTTPException(
            status_code=422,
            detail="Review status must be approved or rejected",
        )
    proposal = await repository.review(proposal_id, review)
    if proposal is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return proposal
