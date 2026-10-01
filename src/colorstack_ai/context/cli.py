import argparse
import asyncio
from uuid import UUID

from colorstack_ai.config import load_database_environment
from colorstack_ai.context.builder import ContextBuilder
from colorstack_ai.context.config import load_context_limits
from colorstack_ai.context.retrieval import RetrievalService
from colorstack_ai.db.session import Database


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build bounded organizational context packages.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    event = subparsers.add_parser("event")
    event.add_argument("event_id", type=UUID)
    task = subparsers.add_parser("task")
    task.add_argument("task_id", type=UUID)
    person = subparsers.add_parser("person")
    person.add_argument("person_id")
    subparsers.add_parser("org")
    query = subparsers.add_parser("query")
    query.add_argument("question")
    return parser.parse_args()


async def main(args: argparse.Namespace) -> None:
    environment = load_database_environment()
    database = Database(environment.database_url.get_secret_value())
    await database.check_connection()
    builder = ContextBuilder(
        RetrievalService(database),
        load_context_limits(),
    )
    try:
        if args.command == "event":
            package = await builder.event(args.event_id)
        elif args.command == "task":
            package = await builder.task(args.task_id)
        elif args.command == "person":
            package = await builder.person(args.person_id)
        elif args.command == "org":
            package = await builder.organization()
        else:
            package = await builder.query(args.question)
    finally:
        await database.close()
    print(package.model_dump_json(indent=2))


def run() -> None:
    args = parse_args()
    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        pass
    except Exception as error:
        raise SystemExit(f"Context build failed: {error}") from None
