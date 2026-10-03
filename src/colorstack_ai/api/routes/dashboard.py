from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from colorstack_ai.api.dependencies import get_dashboard_service
from colorstack_ai.api.schemas import (
    ActivityResponse,
    EventDetailResponse,
    EventListItem,
    GuidanceResponse,
    OverviewResponse,
    PersonResponse,
    PlaybookResponse,
    TaskResponse,
    TaskStatusUpdate,
)
from colorstack_ai.api.service import DashboardService

router = APIRouter(prefix="/api")


@router.get("/overview", response_model=OverviewResponse)
async def overview(
    service: DashboardService = Depends(get_dashboard_service),
) -> OverviewResponse:
    return await service.overview()


@router.get("/events", response_model=list[EventListItem])
async def events(
    service: DashboardService = Depends(get_dashboard_service),
) -> list[EventListItem]:
    return await service.events()


@router.get("/events/{event_id}", response_model=EventDetailResponse)
async def event_detail(
    event_id: UUID,
    service: DashboardService = Depends(get_dashboard_service),
) -> EventDetailResponse:
    event = await service.event(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.get("/tasks", response_model=list[TaskResponse])
async def tasks(
    status: str | None = None,
    owner: str | None = None,
    event: str | None = None,
    urgency: str | None = None,
    service: DashboardService = Depends(get_dashboard_service),
) -> list[TaskResponse]:
    return await service.tasks(
        status=status,
        owner=owner,
        event=event,
        urgency=urgency,
    )


@router.patch("/tasks/{task_id}", response_model=TaskResponse)
async def update_task_status(
    task_id: UUID,
    update: TaskStatusUpdate,
    service: DashboardService = Depends(get_dashboard_service),
) -> TaskResponse:
    task = await service.update_task_status(task_id, update.status)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/guidance", response_model=GuidanceResponse)
async def guidance(
    service: DashboardService = Depends(get_dashboard_service),
) -> GuidanceResponse:
    return await service.guidance()


@router.get("/people", response_model=list[PersonResponse])
async def people(
    service: DashboardService = Depends(get_dashboard_service),
) -> list[PersonResponse]:
    return await service.people()


@router.get("/people/{person_id}", response_model=PersonResponse)
async def person_detail(
    person_id: str,
    service: DashboardService = Depends(get_dashboard_service),
) -> PersonResponse:
    person = await service.person(person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Person not found")
    return person


@router.get("/activity", response_model=list[ActivityResponse])
async def activity(
    hours: int = Query(default=48, ge=1, le=24 * 30),
    service: DashboardService = Depends(get_dashboard_service),
) -> list[ActivityResponse]:
    return await service.activity(hours=hours)


@router.get("/briefs/latest")
async def latest_brief(
    service: DashboardService = Depends(get_dashboard_service),
) -> dict[str, object]:
    brief = await service.latest_brief()
    if brief is None:
        raise HTTPException(status_code=404, detail="No generated brief is available")
    return brief


@router.get("/playbooks", response_model=list[PlaybookResponse])
async def playbooks(
    service: DashboardService = Depends(get_dashboard_service),
) -> list[PlaybookResponse]:
    return await service.playbooks()
