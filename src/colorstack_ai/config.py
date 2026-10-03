import os
from datetime import time
from urllib.parse import urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv
from pydantic import BaseModel, SecretStr


class Environment(BaseModel):
    discord_token: SecretStr
    database_url: SecretStr


class DatabaseEnvironment(BaseModel):
    database_url: SecretStr


class ExtractionEnvironment(BaseModel):
    database_url: SecretStr
    ollama_base_url: str
    ollama_model: str
    extraction_version: str
    ollama_timeout_seconds: float


class ReasoningEnvironment(BaseModel):
    database_url: SecretStr
    provider: str
    model: str
    openai_api_key: SecretStr
    timeout_seconds: float
    max_context_chars: int
    max_output_tokens: int
    input_cost_per_million: float | None
    output_cost_per_million: float | None


class DailyBriefEnvironment(BaseModel):
    enabled: bool
    scheduled_time: time
    timezone: str
    channel_id: str | None


class PipelineEnvironment(BaseModel):
    enabled: bool
    interval_seconds: float
    batch_size: int
    retry_every_cycles: int


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


def load_database_environment() -> DatabaseEnvironment:
    load_dotenv()
    return DatabaseEnvironment(database_url=_load_database_url())


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


def load_reasoning_environment() -> ReasoningEnvironment:
    load_dotenv()
    provider = os.getenv("REASONING_PROVIDER", "openai").strip().casefold()
    if provider != "openai":
        raise RuntimeError(
            "REASONING_PROVIDER must be 'openai'; other providers are not "
            "implemented yet."
        )
    model = os.getenv("REASONING_MODEL", "").strip()
    if not model:
        raise RuntimeError("Missing required environment variable REASONING_MODEL.")
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Missing required environment variable OPENAI_API_KEY.")

    def positive_float(name: str, default: str) -> float:
        try:
            value = float(os.getenv(name, default))
        except ValueError as error:
            raise RuntimeError(f"{name} must be numeric.") from error
        if value <= 0:
            raise RuntimeError(f"{name} must be positive.")
        return value

    def positive_int(name: str, default: str) -> int:
        try:
            value = int(os.getenv(name, default))
        except ValueError as error:
            raise RuntimeError(f"{name} must be an integer.") from error
        if value <= 0:
            raise RuntimeError(f"{name} must be positive.")
        return value

    def optional_cost(name: str) -> float | None:
        raw = os.getenv(name, "").strip()
        if not raw:
            return None
        try:
            value = float(raw)
        except ValueError as error:
            raise RuntimeError(f"{name} must be numeric.") from error
        if value < 0:
            raise RuntimeError(f"{name} cannot be negative.")
        return value

    return ReasoningEnvironment(
        database_url=_load_database_url(),
        provider=provider,
        model=model,
        openai_api_key=SecretStr(api_key),
        timeout_seconds=positive_float("REASONING_TIMEOUT_SECONDS", "60"),
        max_context_chars=positive_int(
            "REASONING_MAX_CONTEXT_CHARS",
            "100000",
        ),
        max_output_tokens=positive_int(
            "REASONING_MAX_OUTPUT_TOKENS",
            "2000",
        ),
        input_cost_per_million=optional_cost(
            "REASONING_INPUT_COST_PER_MILLION"
        ),
        output_cost_per_million=optional_cost(
            "REASONING_OUTPUT_COST_PER_MILLION"
        ),
    )


def load_daily_brief_environment(
    *,
    require_channel: bool = False,
) -> DailyBriefEnvironment:
    load_dotenv()
    enabled_raw = os.getenv("DAILY_BRIEF_ENABLED", "false").strip().casefold()
    if enabled_raw not in {"true", "false"}:
        raise RuntimeError("DAILY_BRIEF_ENABLED must be true or false.")
    time_raw = os.getenv("DAILY_BRIEF_TIME", "08:00").strip()
    try:
        hour_text, minute_text = time_raw.split(":", maxsplit=1)
        scheduled_time = time(hour=int(hour_text), minute=int(minute_text))
    except (TypeError, ValueError) as error:
        raise RuntimeError("DAILY_BRIEF_TIME must use 24-hour HH:MM format.") from error
    timezone = os.getenv(
        "DAILY_BRIEF_TIMEZONE",
        "America/Chicago",
    ).strip()
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError as error:
        raise RuntimeError("DAILY_BRIEF_TIMEZONE is not a valid timezone.") from error
    channel_id = os.getenv("DAILY_BRIEF_CHANNEL_ID", "").strip() or None
    if channel_id is not None and not channel_id.isdecimal():
        raise RuntimeError("DAILY_BRIEF_CHANNEL_ID must be a Discord channel ID.")
    if require_channel and channel_id is None:
        raise RuntimeError("DAILY_BRIEF_CHANNEL_ID is required for delivery.")
    return DailyBriefEnvironment(
        enabled=enabled_raw == "true",
        scheduled_time=scheduled_time,
        timezone=timezone,
        channel_id=channel_id,
    )


def load_pipeline_environment() -> PipelineEnvironment:
    enabled_raw = os.getenv("PIPELINE_ENABLED", "true").strip().casefold()
    if enabled_raw not in {"true", "false"}:
        raise RuntimeError("PIPELINE_ENABLED must be true or false.")

    try:
        interval_seconds = float(os.getenv("PIPELINE_INTERVAL_SECONDS", "60"))
    except ValueError as error:
        raise RuntimeError("PIPELINE_INTERVAL_SECONDS must be numeric.") from error
    if interval_seconds <= 0:
        raise RuntimeError("PIPELINE_INTERVAL_SECONDS must be positive.")

    try:
        batch_size = int(os.getenv("PIPELINE_BATCH_SIZE", "100"))
    except ValueError as error:
        raise RuntimeError("PIPELINE_BATCH_SIZE must be an integer.") from error
    if batch_size <= 0:
        raise RuntimeError("PIPELINE_BATCH_SIZE must be positive.")

    try:
        retry_every_cycles = int(os.getenv("PIPELINE_RETRY_EVERY_CYCLES", "10"))
    except ValueError as error:
        raise RuntimeError("PIPELINE_RETRY_EVERY_CYCLES must be an integer.") from error
    if retry_every_cycles <= 0:
        raise RuntimeError("PIPELINE_RETRY_EVERY_CYCLES must be positive.")

    return PipelineEnvironment(
        enabled=enabled_raw == "true",
        interval_seconds=interval_seconds,
        batch_size=batch_size,
        retry_every_cycles=retry_every_cycles,
    )
