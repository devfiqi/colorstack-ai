import re
from datetime import UTC, datetime
from typing import TypeVar

from colorstack_ai.context.models import (
    MessageContextItem,
    RequirementContextItem,
    TaskContextItem,
)

URGENCY_WEIGHT = {"critical": 40, "high": 30, "medium": 20, "low": 10}
CRITICALITY_WEIGHT = {"critical": 12, "high": 8, "medium": 4, "low": 1}
STATUS_WEIGHT = {
    "blocked": 20,
    "missing": 15,
    "in_progress": 8,
    "unknown": 3,
    "complete": 0,
    "not_applicable": 0,
}
TOKEN_RE = re.compile(r"[a-z0-9]+")
T = TypeVar("T")


def query_tokens(query: str | None) -> set[str]:
    if not query:
        return set()
    return {
        token
        for token in TOKEN_RE.findall(query.casefold())
        if len(token) > 2
    }


def rank_requirements(
    requirements: list[RequirementContextItem],
    *,
    query: str | None,
    limit: int,
) -> list[RequirementContextItem]:
    tokens = query_tokens(query)

    def score(item: RequirementContextItem) -> tuple[int, datetime, str]:
        searchable = f"{item.name} {item.key} {item.rationale}".casefold()
        match = sum(6 for token in tokens if token in searchable)
        value = (
            URGENCY_WEIGHT.get(item.urgency, 0)
            + CRITICALITY_WEIGHT.get(item.criticality, 0)
            + STATUS_WEIGHT.get(item.status, 0)
            + match
        )
        return value, item.evaluated_at, item.name

    return sorted(requirements, key=score, reverse=True)[:limit]


def rank_tasks(
    tasks: list[TaskContextItem],
    *,
    query: str | None,
    limit: int,
) -> list[TaskContextItem]:
    tokens = query_tokens(query)

    def score(item: TaskContextItem) -> tuple[int, str]:
        searchable = (
            f"{item.title} {item.owner_name or ''} {item.status or ''}"
        ).casefold()
        value = sum(8 for token in tokens if token in searchable)
        if item.blocker is not None or item.status == "blocked":
            value += 30
        elif item.status == "in_progress":
            value += 15
        elif item.status == "open":
            value += 10
        if item.deadline is not None:
            value += 8
        return value, item.title

    return sorted(tasks, key=score, reverse=True)[:limit]


def message_score(
    *,
    content: str,
    created_at: datetime,
    query: str | None,
    entity_terms: set[str],
    provenance_match: bool,
    now: datetime | None = None,
) -> tuple[float, str]:
    current = now or datetime.now(UTC)
    age_hours = max(0.0, (current - created_at).total_seconds() / 3_600)
    score = max(0.0, 20.0 - min(age_hours / 12, 20.0))
    reasons = ["recency"]
    lowered = content.casefold()
    matched_query = [
        token for token in query_tokens(query) if token in lowered
    ]
    if matched_query:
        score += 8 * len(matched_query)
        reasons.append("query match")
    matched_entity = [term for term in entity_terms if term in lowered]
    if matched_entity:
        score += 12
        reasons.append("entity match")
    if provenance_match:
        score += 30
        reasons.append("source provenance")
    return round(score, 3), ", ".join(reasons)


def rank_messages(
    messages: list[MessageContextItem],
    limit: int,
) -> list[MessageContextItem]:
    return sorted(
        messages,
        key=lambda item: (item.relevance_score, item.created_at, item.message_id),
        reverse=True,
    )[:limit]
