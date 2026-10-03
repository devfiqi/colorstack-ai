import asyncio

from colorstack_ai.config import load_database_environment
from colorstack_ai.db.session import Database
from colorstack_ai.operations.seed import AuthoritativeEventSeeder


async def main() -> None:
    environment = load_database_environment()
    database = Database(environment.database_url.get_secret_value())
    try:
        print(await AuthoritativeEventSeeder(database).seed())
    finally:
        await database.close()


if __name__ == "__main__":
    asyncio.run(main())
