import argparse
import asyncio
from uuid import UUID

from colorstack_ai.config import load_database_environment
from colorstack_ai.db.session import Database
from colorstack_ai.playbooks.evaluator import EventEvaluator
from colorstack_ai.playbooks.loader import PlaybookLoader
from colorstack_ai.playbooks.models import ReadinessSummary
from colorstack_ai.playbooks.repository import PlaybookRepository


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate active events against event playbooks.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("evaluate-all")
    event_parser = subparsers.add_parser("evaluate-event")
    event_parser.add_argument("event_id", type=UUID)
    return parser.parse_args()


def _print_summary(summary: ReadinessSummary) -> None:
    event_types = " + ".join(item.value for item in summary.event_types)
    print(f"{summary.event_name} ({event_types})")
    print(f"Readiness: {summary.readiness_score:.1f}%")
    print(
        f"Complete: {summary.complete} | In progress: "
        f"{summary.in_progress} | Missing: {summary.missing} | "
        f"Blocked: {summary.blocked} | Critical gaps: "
        f"{summary.critical_gaps}"
    )
    actionable = [
        result
        for result in summary.requirements
        if result.recommendation is not None
    ]
    for result in sorted(
        actionable,
        key=lambda item: (
            ["critical", "high", "medium", "low"].index(
                item.urgency.value
            ),
            item.requirement_name,
        ),
    ):
        print(
            f"- [{result.urgency.value}] {result.requirement_name}: "
            f"{result.status.value}. {result.recommendation}"
        )


async def main(args: argparse.Namespace) -> None:
    environment = load_database_environment()
    database = Database(environment.database_url.get_secret_value())
    await database.check_connection()
    evaluator = EventEvaluator(
        repository=PlaybookRepository(database),
        loader=PlaybookLoader(),
    )
    try:
        if args.command == "evaluate-event":
            summaries = [await evaluator.evaluate_event(args.event_id)]
        else:
            summaries = await evaluator.evaluate_all()
    finally:
        await database.close()
    for summary in summaries:
        _print_summary(summary)
    if not summaries:
        print("No active events found")


def run() -> None:
    args = parse_args()
    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        pass
    except Exception as error:
        raise SystemExit(f"Requirement evaluation failed: {error}") from None
