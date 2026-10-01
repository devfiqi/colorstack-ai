import os
from urllib.parse import urlparse

from dotenv import load_dotenv
from pydantic import BaseModel, SecretStr


class Environment(BaseModel):
    discord_token: SecretStr
    database_url: SecretStr


class ExtractionEnvironment(BaseModel):
    database_url: SecretStr
    ollama_base_url: str
    ollama_model: str
    extraction_version: str
    ollama_timeout_seconds: float


def _load_database_url() -> SecretStr:
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
    return SecretStr(database_url)


def load_environment() -> Environment:
    load_dotenv()
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "Missing required environment variable DISCORD_TOKEN. "
            "Copy .env.example to .env and add the bot token."
        )

    return Environment(
        discord_token=SecretStr(token),
        database_url=_load_database_url(),
    )


def load_extraction_environment() -> ExtractionEnvironment:
    load_dotenv()
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip()
    parsed_url = urlparse(base_url)
    if parsed_url.scheme not in {"http", "https"} or parsed_url.hostname not in {
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        raise RuntimeError(
            "OLLAMA_BASE_URL must point to Ollama on localhost."
        )

    model = os.getenv("OLLAMA_MODEL", "").strip()
    if not model:
        raise RuntimeError(
            "Missing required environment variable OLLAMA_MODEL. "
            "Run `ollama list` and set one of the installed model names."
        )

    extraction_version = os.getenv("EXTRACTION_VERSION", "v1").strip()
    if not extraction_version:
        raise RuntimeError("EXTRACTION_VERSION cannot be empty.")

    try:
        timeout = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))
    except ValueError as error:
        raise RuntimeError("OLLAMA_TIMEOUT_SECONDS must be numeric.") from error
    if timeout <= 0:
        raise RuntimeError("OLLAMA_TIMEOUT_SECONDS must be positive.")

    return ExtractionEnvironment(
        database_url=_load_database_url(),
        ollama_base_url=base_url.rstrip("/"),
        ollama_model=model,
        extraction_version=extraction_version,
        ollama_timeout_seconds=timeout,
    )
