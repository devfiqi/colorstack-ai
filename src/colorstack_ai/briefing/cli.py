import argparse
import asyncio

import discord

from colorstack_ai.briefing.delivery import DiscordBriefDelivery
from colorstack_ai.briefing.factory import create_briefing_service
from colorstack_ai.briefing.models import BriefGenerationResult
from colorstack_ai.briefing.service import BriefingService
from colorstack_ai.config import (
    load_daily_brief_environment,
    load_environment,
    load_reasoning_environment,
)
from colorstack_ai.db.session import Database


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate and deliver executive briefs.")
    parser.add_argument("command", choices=("generate", "preview", "send", "schedule"))
    return parser.parse_args()


class _SendClient(discord.Client):
    def __init__(self, service: BriefingService, channel_id: str) -> None:
        intents = discord.Intents.none()
        intents.guilds = True
        super().__init__(intents=intents)
        self._service = service
        self._channel_id = channel_id
        self.error: Exception | None = None
        self.result: BriefGenerationResult | None = None

    async def on_ready(self) -> None:
        try:
            self.result = await self._service.send_manual(
                DiscordBriefDelivery(self, self._channel_id)
            )
        except Exception as error:
            self.error = error
        finally:
            await self.close()


async def main(args: argparse.Namespace) -> None:
    settings = load_daily_brief_environment(require_channel=args.command == "send")
    if args.command == "schedule":
        print(
            f"enabled={str(settings.enabled).lower()} "
            f"time={settings.scheduled_time.strftime('%H:%M')} "
            f"timezone={settings.timezone} channel={settings.channel_id or 'unset'}"
        )
        return

    reasoning_environment = load_reasoning_environment()
    database = Database(reasoning_environment.database_url.get_secret_value())
    await database.check_connection()
    service = create_briefing_service(
        database,
        reasoning_environment,
        channel_id=settings.channel_id,
    )
    try:
        if args.command == "generate":
            result = await service.generate()
            print(result.brief.model_dump_json(indent=2))
        elif args.command == "preview":
            result = await service.preview()
            print(result.rendered_text)
        else:
            bot_environment = load_environment()
            assert settings.channel_id is not None
            client = _SendClient(service, settings.channel_id)
            await client.start(bot_environment.discord_token.get_secret_value())
            if client.error is not None:
                raise client.error
            result = client.result
            if result is None:
                raise RuntimeError("Discord client closed before sending the brief.")
            print(result.model_dump_json(indent=2))
    finally:
        await database.close()


def run() -> None:
    args = parse_args()
    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        pass
    except Exception as error:
        raise SystemExit(f"Daily brief command failed: {error}") from None
