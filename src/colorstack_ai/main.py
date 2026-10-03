import asyncio
import logging
from datetime import date

from colorstack_ai.briefing.factory import create_briefing_service
from colorstack_ai.briefing.scheduler import DailyBriefScheduler
from colorstack_ai.config import (
    load_daily_brief_environment,
    load_environment,
    load_extraction_environment,
    load_pipeline_environment,
    load_reasoning_environment,
)
from colorstack_ai.db.session import Database
from colorstack_ai.discord.client import DiscordIngestionClient
from colorstack_ai.ingestion.postgres_store import PostgresMessageStore
from colorstack_ai.pipeline.service import create_pipeline


async def main() -> None:
    environment = load_environment()
    database = Database(environment.database_url.get_secret_value())
    await database.check_connection()
    store = PostgresMessageStore(database)
    client = DiscordIngestionClient(store)
    pipeline_settings = load_pipeline_environment()
    if pipeline_settings.enabled:
        extraction_environment = load_extraction_environment()
        client.set_intelligence_pipeline(
            create_pipeline(database, extraction_environment, pipeline_settings)
        )
    brief_settings = load_daily_brief_environment()
    if brief_settings.enabled:
        reasoning_environment = load_reasoning_environment()
        service = create_briefing_service(
            database,
            reasoning_environment,
            channel_id=None,
        )

        async def generate_scheduled(scheduled_date: date) -> object:
            return await service.generate_scheduled(scheduled_date)

        client.set_brief_scheduler(
            DailyBriefScheduler(
                enabled=True,
                scheduled_time=brief_settings.scheduled_time,
                timezone=brief_settings.timezone,
                job=generate_scheduled,
            )
        )

    try:
        async with client:
            await client.start(environment.discord_token.get_secret_value())
    finally:
        await store.close()


def run() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception:
        logging.getLogger(__name__).exception("Fatal ingestion error")
        raise SystemExit(1) from None
