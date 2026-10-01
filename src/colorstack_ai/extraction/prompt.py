import json

from colorstack_ai.extraction.models import ExtractionContext

PROMPT_VERSION = "v2"

SYSTEM_PROMPT = """You extract organizational facts from Discord conversations.

Return only facts supported by the source message and its bounded context.
Supported types are: event_mention, event_update, task, commitment,
ownership_change, deadline, decision, blocker, sponsor_request, funding_update,
location_change, status_change, cancellation, open_question, and dependency.

Rules:
- Return {"facts": []} when there is no organizational fact.
- Do not decide the current truth of the organization.
- Preserve changes as new facts; do not overwrite earlier context.
- Do not invent event names, owners, deadlines, locations, statuses, or IDs.
- Use null when a field is not supported by the text.
- For task, commitment, and ownership_change facts, set task to the concrete
  action phrase stated in the source message.
- Do not emit a separate event_mention when an event name only provides context
  for a more specific fact in the same sentence.
- Mark evidence_kind as explicit when directly stated and inferred only when
  local context makes the interpretation reasonably clear.
- Lower confidence when wording is ambiguous.
- "speaker" means the source message author. If the speaker owns a task, use
  the provided source author name and Discord ID.
- Resolve relative dates only when the message timestamp provides enough
  information. Otherwise preserve deadline_text and leave normalized_deadline
  null.
- A reply may depend on its parent message. Nearby messages are context, not
  automatically facts belonging to the source message.
- Never include commentary outside the structured response.
"""


def build_user_prompt(context: ExtractionContext) -> str:
    payload = context.model_dump(mode="json")
    return (
        "Extract facts attributable to source_message_id from this bounded "
        "conversation context:\n"
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    )
