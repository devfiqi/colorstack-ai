import os
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends

from colorstack_ai.api.dependencies import get_database
from colorstack_ai.api.schemas import SystemResponse
from colorstack_ai.config import (
    load_daily_brief_environment,
    load_pipeline_environment,
)
from colorstack_ai.db.session import Database
from colorstack_ai.pipeline.repository import PipelineRepository

router = APIRouter(prefix="/api")


@router.get("/system", response_model=SystemResponse)
@router.get("/system/status", response_model=SystemResponse)
async def system_status(database: Database = Depends(get_database)) -> SystemResponse:
    await database.check_connection()
    settings = load_daily_brief_environment()
    pipeline = load_pipeline_environment()
    latest_run = await PipelineRepository(database).latest()
    pipeline_status = "Disabled"
    if pipeline.enabled:
        if latest_run is None:
            pipeline_status = "Waiting for first run"
        else:
            stale_after = timedelta(
                seconds=max(pipeline.interval_seconds * 3, 300)
            )
            pipeline_status = (
                "Stale"
                if datetime.now(UTC) - latest_run.finished_at > stale_after
                else latest_run.status.title()
            )
    pipeline_stages: list[dict[str, object]] = []
    if latest_run is not None:
        for item in latest_run.stages:
            if isinstance(item, dict):
                pipeline_stages.append(
                    {str(key): value for key, value in item.items()}
                )
    return SystemResponse(
        database="Connected",
        discord=(
            "Configured"
            if os.getenv("DISCORD_TOKEN", "").strip()
            else "Not configured"
        ),
        extraction=(
            "Configured"
            if os.getenv("OLLAMA_MODEL", "").strip()
            else "Not configured"
        ),
        reasoning=(
            "Configured"
            if os.getenv("REASONING_MODEL", "").strip()
            and os.getenv("OPENAI_API_KEY", "").strip()
            else "Not configured"
        ),
        daily_brief_enabled=settings.enabled,
        daily_brief_schedule=(
            f"{settings.scheduled_time.strftime('%H:%M')} {settings.timezone}"
        ),
        pipeline_enabled=pipeline.enabled,
        pipeline_interval_seconds=pipeline.interval_seconds,
        pipeline_status=pipeline_status,
        pipeline_last_run_at=(
            latest_run.finished_at if latest_run is not None else None
        ),
        pipeline_stages=pipeline_stages,
        advisory_only=True,
        automatic_actions=False,
    )


@router.get("/health")
async def health(database: Database = Depends(get_database)) -> dict[str, str]:
    await database.check_connection()
    return {"status": "ok"}
