import os

from colorstack_ai.context.models import ContextLimits


def load_context_limits() -> ContextLimits:
    names = {
        "messages": "CONTEXT_MESSAGES_LIMIT",
        "changes": "CONTEXT_CHANGES_LIMIT",
        "tasks": "CONTEXT_TASKS_LIMIT",
        "requirements": "CONTEXT_REQUIREMENTS_LIMIT",
        "facts": "CONTEXT_FACTS_LIMIT",
        "events": "CONTEXT_EVENTS_LIMIT",
        "recent_hours": "CONTEXT_RECENT_HOURS",
    }
    values: dict[str, int] = {}
    for field, environment_name in names.items():
        raw = os.getenv(environment_name)
        if raw is None or not raw.strip():
            continue
        try:
            values[field] = int(raw)
        except ValueError as error:
            raise RuntimeError(f"{environment_name} must be an integer.") from error
    return ContextLimits.model_validate(values)
