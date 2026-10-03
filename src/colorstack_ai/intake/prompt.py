import json
from datetime import datetime

PROMPT_VERSION = "intake-v1"

SYSTEM_PROMPT = """You extract proposed organizational facts from material a
ColorStack vice president has submitted for review.

Supported fact types are: event_mention, event_update, task, commitment,
ownership_change, deadline, decision, blocker, sponsor_request, funding_update,
location_change, status_change, cancellation, open_question, and dependency.

Rules:
- Return {"facts": []} when the source contains no organizational fact.
- Extract only claims supported directly by the submitted source.
- Do not decide which claims are currently authoritative.
- Do not invent owners, dates, events, decisions, statuses, or identifiers.
- Use null for unsupported fields.
- Preserve questions as open_question facts rather than answering them.
- Mark evidence_kind explicit for direct statements and inferred only when the
  submitted context makes the interpretation reasonably clear.
- Lower confidence for ambiguous wording.
- Never include commentary outside the structured response.
"""


def build_user_prompt(
    *,
    source_id: str,
    source_type: str,
    title: str,
    content: str,
    occurred_at: datetime | None,
) -> str:
    return json.dumps(
        {
            "source_id": source_id,
            "source_type": source_type,
            "title": title,
            "occurred_at": occurred_at.isoformat() if occurred_at else None,
            "content": content,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
