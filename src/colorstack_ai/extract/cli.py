import argparse
import asyncio
import logging

from colorstack_ai.config import load_extraction_environment
from colorstack_ai.db.session import Database
from colorstack_ai.extraction.context import ContextBuilder
from colorstack_ai.extraction.ollama import OllamaClient
from colorstack_ai.extraction.processor import ExtractionProcessor
from colorstack_ai.extraction.repository import ExtractionRepository


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
    args = parser.parse_args()
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be positive")
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
