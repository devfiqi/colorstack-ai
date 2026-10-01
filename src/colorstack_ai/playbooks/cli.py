import argparse
import asyncio

from colorstack_ai.config import load_database_environment
from colorstack_ai.db.session import Database
from colorstack_ai.playbooks.loader import PlaybookLoader
from colorstack_ai.playbooks.repository import PlaybookRepository


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect and validate event playbooks.",
    )
    parser.add_argument("command", choices=("list", "validate", "sync"))
    return parser.parse_args()


async def main(args: argparse.Namespace) -> None:
    loader = PlaybookLoader()
    definitions = loader.load_all()
    if args.command == "list":
        for definition in definitions:
            kind = "overlay" if definition.overlay else "playbook"
            print(
                f"{definition.key} v{definition.version} "
                f"({kind}, {len(definition.requirements)} requirements)"
            )
        return
    if args.command == "validate":
        print(
            f"Validated {len(definitions)} playbooks with "
            f"{sum(len(item.requirements) for item in definitions)} "
            "requirements"
        )
        return

    environment = load_database_environment()
    database = Database(environment.database_url.get_secret_value())
    await database.check_connection()
    try:
        await PlaybookRepository(database).sync_definitions(definitions)
    finally:
        await database.close()
    print(f"Synchronized {len(definitions)} playbooks")


def run() -> None:
    args = parse_args()
    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        pass
    except Exception as error:
        raise SystemExit(f"Playbook command failed: {error}") from None
