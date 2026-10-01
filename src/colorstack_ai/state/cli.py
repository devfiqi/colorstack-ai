import argparse
import asyncio
import logging

from colorstack_ai.config import (
    load_database_environment,
    load_extraction_environment,
)
from colorstack_ai.db.session import Database
from colorstack_ai.state.ambiguity import OllamaAmbiguityResolver
from colorstack_ai.state.processor import StateProcessor
from colorstack_ai.state.repository import StateRepository
from colorstack_ai.state.resolution import EntityResolver


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reconcile extracted facts into organizational state.",
    )
    parser.add_argument(
        "mode",
        choices=("reconcile-new", "rebuild", "retry-unresolved"),
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum facts to reconcile (not valid for rebuild).",
    )
    parser.add_argument(
        "--resolve-ambiguous",
        action="store_true",
        help="Ask the configured local Ollama model for safe classifications.",
    )
    args = parser.parse_args()
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be positive")
    if args.mode == "rebuild" and args.limit is not None:
        parser.error("rebuild must process all facts; omit --limit")
    return args


async def main(args: argparse.Namespace) -> None:
    if args.resolve_ambiguous:
        environment = load_extraction_environment()
        database_url = environment.database_url.get_secret_value()
    else:
        environment = None
        database_url = (
            load_database_environment().database_url.get_secret_value()
        )

    database = Database(database_url)
    await database.check_connection()
    repository = StateRepository(database)
    resolver = EntityResolver(database)
    limit = args.limit
    if limit is None and args.mode in {"reconcile-new", "retry-unresolved"}:
        limit = 100

    try:
        if environment is None:
            processor = StateProcessor(
                repository=repository,
                resolver=resolver,
            )
            await processor.process(mode=args.mode, limit=limit)
        else:
            async with OllamaAmbiguityResolver(
                base_url=environment.ollama_base_url,
                model=environment.ollama_model,
                timeout_seconds=environment.ollama_timeout_seconds,
            ) as ambiguity_resolver:
                await ambiguity_resolver.validate()
                processor = StateProcessor(
                    repository=repository,
                    resolver=resolver,
                    ambiguity_resolver=ambiguity_resolver,
                )
                await processor.process(mode=args.mode, limit=limit)
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
        logging.getLogger(__name__).exception("State reconciliation failed")
        raise SystemExit(1) from None
