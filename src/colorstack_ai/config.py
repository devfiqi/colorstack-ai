import os

from dotenv import load_dotenv
from pydantic import BaseModel, SecretStr


class Environment(BaseModel):
    discord_token: SecretStr
    database_url: SecretStr


def load_environment() -> Environment:
    load_dotenv()
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "Missing required environment variable DISCORD_TOKEN. "
            "Copy .env.example to .env and add the bot token."
        )

    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError(
            "Missing required environment variable DATABASE_URL. "
            "Copy the local PostgreSQL URL from .env.example."
        )

    if not database_url.startswith("postgresql+psycopg://"):
        raise RuntimeError(
            "DATABASE_URL must be a PostgreSQL URL using the psycopg driver."
        )

    return Environment(
        discord_token=SecretStr(token),
        database_url=SecretStr(database_url),
    )
