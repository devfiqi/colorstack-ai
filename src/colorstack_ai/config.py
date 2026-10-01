import os

from dotenv import load_dotenv
from pydantic import BaseModel, SecretStr


class Environment(BaseModel):
    discord_token: SecretStr


def load_environment() -> Environment:
    load_dotenv()
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "Missing required environment variable DISCORD_TOKEN. "
            "Copy .env.example to .env and add the bot token."
        )

    return Environment(discord_token=SecretStr(token))
