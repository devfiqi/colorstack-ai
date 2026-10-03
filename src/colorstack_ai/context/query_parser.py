import re

from colorstack_ai.context.models import (
    ContextScope,
    QueryIntent,
    QueryInterpretation,
)

TRIM_WORDS = {
    "what",
    "are",
    "is",
    "we",
    "for",
    "the",
    "with",
    "about",
    "today",
    "recently",
    "event",
    "status",
    "missing",
    "changed",
    "change",
    "deadline",
    "deadlines",
    "blocker",
    "blockers",
    "task",
    "tasks",
    "who",
    "owns",
    "owner",
    "responsible",
    "working",
    "assigned",
    "on",
    "of",
    "show",
    "me",
}


def _entity_phrase(query: str) -> str | None:
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'_-]*", query)
    remaining = [word for word in words if word.casefold() not in TRIM_WORDS]
    return " ".join(remaining).strip() or None


def parse_query(query: str) -> QueryInterpretation:
    normalized = " ".join(query.strip().split())
    lowered = normalized.casefold()
    if not normalized:
        return QueryInterpretation(
            query=query,
            scope=ContextScope.UNKNOWN,
            intent=QueryIntent.UNKNOWN,
            confidence=0,
            ambiguous=True,
            reason="query is empty",
        )

    if any(
        phrase in lowered
        for phrase in (
            "next board meeting",
            "organization status",
            "overall status",
            "what should we discuss",
            "what should we focus",
            "what should i do",
            "what needs my attention",
            "what am i missing",
            "what do i need to do",
        )
    ):
        return QueryInterpretation(
            query=normalized,
            scope=ContextScope.ORGANIZATION,
            intent=QueryIntent.ORGANIZATION_STATUS,
            confidence=0.95,
            reason="matched organization-wide planning language",
        )

    intent = QueryIntent.UNKNOWN
    if any(word in lowered for word in ("missing", "still need", "left to do")):
        intent = QueryIntent.MISSING_REQUIREMENTS
    elif any(word in lowered for word in ("blocker", "blocked", "blocking")):
        intent = QueryIntent.BLOCKERS
    elif any(phrase in lowered for phrase in ("who owns", "owner of", "owned by")):
        intent = QueryIntent.OWNER_LOOKUP
    elif any(word in lowered for word in ("deadline", "due", "when is")):
        intent = QueryIntent.DEADLINES
    elif any(word in lowered for word in ("changed", "changes", "recent", "today")):
        intent = QueryIntent.RECENT_CHANGES
    elif any(word in lowered for word in ("priority", "priorities", "focus")):
        intent = QueryIntent.PRIORITIES
    elif any(
        phrase in lowered
        for phrase in ("responsible for", "assigned to", "working on")
    ):
        intent = QueryIntent.PERSON_RESPONSIBILITIES
    elif any(word in lowered for word in ("unresolved", "open items", "open work")):
        intent = QueryIntent.UNRESOLVED_ITEMS
    elif "task" in lowered:
        intent = QueryIntent.TASK_LOOKUP
    elif any(word in lowered for word in ("status", "how is", "how are")):
        intent = QueryIntent.EVENT_STATUS

    entity_text = _entity_phrase(normalized)
    if intent == QueryIntent.PERSON_RESPONSIBILITIES:
        scope = ContextScope.PERSON
    elif intent in {QueryIntent.OWNER_LOOKUP, QueryIntent.TASK_LOOKUP}:
        scope = ContextScope.TASK
    elif intent in {
        QueryIntent.MISSING_REQUIREMENTS,
        QueryIntent.BLOCKERS,
        QueryIntent.DEADLINES,
        QueryIntent.RECENT_CHANGES,
        QueryIntent.EVENT_STATUS,
    }:
        scope = ContextScope.EVENT
    elif intent in {
        QueryIntent.PRIORITIES,
        QueryIntent.ORGANIZATION_STATUS,
        QueryIntent.UNRESOLVED_ITEMS,
    } and entity_text is None:
        scope = ContextScope.ORGANIZATION
    elif intent == QueryIntent.PRIORITIES:
        scope = ContextScope.EVENT
    else:
        scope = ContextScope.UNKNOWN

    ambiguous = scope == ContextScope.UNKNOWN or (
        scope != ContextScope.ORGANIZATION and entity_text is None
    )
    return QueryInterpretation(
        query=normalized,
        scope=scope,
        intent=intent,
        entity_text=entity_text,
        confidence=0.9 if not ambiguous else 0.35,
        ambiguous=ambiguous,
        reason=(
            f"deterministic {scope.value} / {intent.value} match"
            if not ambiguous
            else "query did not identify a safe scope and entity"
        ),
    )
