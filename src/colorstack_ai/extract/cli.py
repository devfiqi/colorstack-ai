import argparse
import asyncio
import logging
from datetime import UTC, date, datetime, timedelta

from colorstack_ai.config import load_extraction_environment
from colorstack_ai.db.session import Database
from colorstack_ai.extraction.context import ContextBuilder
from colorstack_ai.extraction.ollama import OllamaClient
from colorstack_ai.extraction.processor import ExtractionProcessor
from colorstack_ai.extraction.repository import ExtractionRepository


EVENT_PRIORITY_PATTERN = (
    r"gen.?ai|generative ai|sibat|imposter|ideathon|hackathon|olympics|"
    r"nsbe|shark tank"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract organizational facts from raw Discord messages.",
    )
    parser.add_argument(
        "mode",
        choices=("backfill", "new", "retry-failed"),
        help="Select unprocessed history, recent messages, or failed messages.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of candidate messages to scan.",
    )
    parser.add_argument(
        "--version",
        help="Extraction version; defaults to EXTRACTION_VERSION.",
    )
    parser.add_argument(
        "--from-date",
        type=date.fromisoformat,
        help="Inclusive local calendar date (YYYY-MM-DD) for a bounded reprocess.",
    )
    parser.add_argument(
        "--to-date",
        type=date.fromisoformat,
        help="Inclusive local calendar date (YYYY-MM-DD) for a bounded reprocess.",
    )
    parser.add_argument(
        "--event-priority",
        action="store_true",
        help=(
            "Restrict processing to the confirmed Gen AI, SIBAT, Ideathon, "
            "and NSBE event terms while preserving each message's local context."
        ),
    )
    args = parser.parse_args()
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be positive")
    if args.from_date and args.to_date and args.to_date < args.from_date:
        parser.error("--to-date must not be before --from-date")
    return args


async def main(args: argparse.Namespace) -> None:
    environment = load_extraction_environment()
    extraction_version = args.version or environment.extraction_version
    limit = args.limit
    if limit is None and args.mode in {"new", "retry-failed"}:
        limit = 100

    database = Database(environment.database_url.get_secret_value())
    await database.check_connection()

    try:
        async with OllamaClient(
            base_url=environment.ollama_base_url,
            model=environment.ollama_model,
            timeout_seconds=environment.ollama_timeout_seconds,
        ) as ollama:
            await ollama.validate()
            processor = ExtractionProcessor(
                repository=ExtractionRepository(database),
                context_builder=ContextBuilder(database),
                extractor=ollama,
                extraction_version=extraction_version,
            )
            await processor.process(
                mode=args.mode,
                limit=limit,
                start_at=(
                    datetime.combine(args.from_date, datetime.min.time(), tzinfo=UTC)
                    if args.from_date
                    else None
                ),
                end_at=(
                    datetime.combine(
                        args.to_date + timedelta(days=1),
                        datetime.min.time(),
                        tzinfo=UTC,
                    )
                    if args.to_date
                    else None
                ),
                content_pattern=(EVENT_PRIORITY_PATTERN if args.event_priority else None),
            )
    finally:
        await database.close()


def run() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = parse_args()
    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        pass
    except Exception:
        logging.getLogger(__name__).exception("Extraction failed")
        raise SystemExit(1) from None
