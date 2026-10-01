from fastapi import APIRouter, Depends

from colorstack_ai.api.dependencies import get_database
from colorstack_ai.api.schemas import SystemResponse
from colorstack_ai.config import load_daily_brief_environment
from colorstack_ai.db.session import Database

router = APIRouter(prefix="/api")


@router.get("/system", response_model=SystemResponse)
async def system_status(database: Database = Depends(get_database)) -> SystemResponse:
    await database.check_connection()
    settings = load_daily_brief_environment()
    return SystemResponse(
        database="Connected",
        discord="Configured",
        extraction="Local Ollama",
        reasoning="Configured",
        daily_brief_enabled=settings.enabled,
        daily_brief_schedule=(
            f"{settings.scheduled_time.strftime('%H:%M')} {settings.timezone}"
        ),
    )


@router.get("/health")
async def health(database: Database = Depends(get_database)) -> dict[str, str]:
    await database.check_connection()
    return {"status": "ok"}
