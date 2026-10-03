import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from colorstack_ai.api.routes.advisor import router as advisor_router
from colorstack_ai.api.routes.dashboard import router as dashboard_router
from colorstack_ai.api.routes.intake import router as intake_router
from colorstack_ai.api.routes.system import router as system_router
from colorstack_ai.config import load_database_environment
from colorstack_ai.db.session import Database


def create_app(database: Database | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        owned_database = database is None
        active_database = database
        if active_database is None:
            environment = load_database_environment()
            active_database = Database(environment.database_url.get_secret_value())
        await active_database.check_connection()
        app.state.database = active_database
        try:
            yield
        finally:
            if owned_database:
                await active_database.close()

    app = FastAPI(
        title="ColorStack AI Dashboard API",
        version="0.1.0",
        lifespan=lifespan,
    )
    origins = [
        item.strip()
        for item in os.getenv(
            "DASHBOARD_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if item.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["*"],
    )
    app.include_router(dashboard_router)
    app.include_router(intake_router)
    app.include_router(advisor_router)
    app.include_router(system_router)
    return app


app = create_app()


def run() -> None:
    uvicorn.run(
        "colorstack_ai.api.app:app",
        host="127.0.0.1",
        port=int(os.getenv("API_PORT", "8000")),
        reload=os.getenv("API_RELOAD", "false").casefold() == "true",
    )
