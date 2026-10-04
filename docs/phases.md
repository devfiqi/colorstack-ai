# Project phases

This page combines the implementation notes for the completed ColorStack AI
phases. It explains how information moves from Discord into the local dashboard
and where each part of the system begins and ends.

## Phase 1: Discord ingestion

Phase 1 creates the local Discord archive. It discovers the servers, channels,
and threads the bot can read, imports their history, and stays connected for new
messages, edits, and deletions.

Key behavior:

- Validates the Discord token before connecting
- Reads text channels, announcement channels, and accessible threads
- Preserves messages, attachments, reactions, replies, and author snapshots
- Handles live creates, edits, single deletions, and bulk deletions
- Skips inaccessible channels without stopping the full import
- Avoids duplicate historical records across restarts

The bot requires the Guilds, Guild Messages, Message Content, and Server Members
gateway intents. Discord permissions remain the final authority on what it can
read. See [Bot communication policy](BOT_PERMISSIONS.md) for outbound limits.

## Phase 2: PostgreSQL persistence

Phase 2 stores the archive in local PostgreSQL instead of the temporary JSONL
verification store.

It adds:

- Async SQLAlchemy sessions using `psycopg`
- Alembic-managed database migrations
- Idempotent inserts keyed by Discord message ID
- In-place snapshots for edits, attachments, and reactions
- Soft deletion with timestamps
- Database and schema checks before Discord login

The main tables are `messages`, `attachments`, and `reactions`. See the
[data model](data-model.md) for field-level details.

## Phase 3: Local fact extraction

Phase 3 turns relevant Discord messages into structured, source-linked facts
using a local Ollama model.

```text
PostgreSQL messages
  -> relevance filter
  -> bounded conversation context
  -> local Ollama extraction
  -> validated facts in PostgreSQL
```

Facts can describe events, tasks, decisions, commitments, deadlines, blockers,
owners, and status changes. Every fact keeps a link to its source message and
the extractor version that produced it. Extraction never deletes or modifies
the raw message archive.

The relevance filter limits model calls, and the context builder includes only
a small surrounding conversation window. Failed or invalid extractions are
recorded so they can be reviewed or retried.

## Phase 4: Organizational state

Phase 4 reconciles immutable extracted facts into a current view of active
events and tasks.

```text
extracted fact
  -> conservative entity matching
  -> field mapping
  -> precedence rules
  -> current state
  -> audit trail
```

Entity matching uses exact normalized names, stored aliases, distinctive words,
and limited reply or channel context. Ambiguous facts are placed in
`unresolved_facts` rather than guessed into the wrong event or task.

Every accepted state change retains its source. Newer, more explicit evidence
can replace older values, while the `state_changes` log keeps the history.

## Phase 5: Event playbooks

Phase 5 compares each event with a versioned checklist for running that kind of
event. Supported base playbooks include ideathons, panels, workshops, networking
events, general meetings, and social events. A company-sponsored overlay can be
applied alongside any base playbook.

Each requirement is evaluated as complete, missing, blocked, not applicable, or
unknown. The evaluator also considers dependencies and deadlines to calculate
urgency and overall readiness. Results always point back to the supporting
evidence.

Playbook evaluation is advisory. It identifies gaps and recommends next steps;
it does not update external tools or contact people.

## Phase 6: Retrieval and context

Phase 6 builds small, source-linked context packages for the reasoning model.
Context can be scoped to an event, task, person, the organization, or a specific
question.

Supported question types include:

- Event status and missing requirements
- Blockers and owners
- Task lookups and deadlines
- Recent changes and priorities

Retrieval starts with structured current state, adds relevant requirements and
recent changes, and includes only the bounded source material needed for the
request. The full Discord archive is never sent to the reasoning provider.

## Phases 7 and 8: Reasoning and daily briefs

The reasoning layer uses the bounded Phase 6 context to produce grounded advice
and executive updates. Daily briefs summarize priorities, risks, missing work,
and recent changes for review.

Brief generation does not send anything. Delivery requires a person to run the
explicit `send` command. This keeps the assistant advisory and prevents
unreviewed outbound communication.

## Phase 10: Local operations dashboard

Phase 10 presents the system through a private local dashboard backed by a
FastAPI API and a React frontend.

The dashboard includes:

- An overview of priorities and recent activity
- Event status and requirement details
- Task filtering and manual task overrides
- People and ownership views
- Daily briefs and playbook status
- System health information
- The VP Advisor and approval-gated inbox

PostgreSQL remains the source of truth. Manual task completion and reopening are
stored as append-only local overrides, so the dashboard can respect a person's
decision without changing Discord or another external system. Tasks use one
shared record across the overview, task, and event views, including their linked
event, chapter division, event phase, expected result, rationale, recommendation
status, clarification markers, and available source evidence.

## Privacy and system boundaries

- Discord archives, credentials, PostgreSQL data, and Ollama processing stay
  local.
- Raw pasted notes are not sent to the reasoning provider.
- Inbox facts require approval before they enter advisor context.
- Only bounded, relevant context may be sent to the configured reasoning model.
- The assistant cannot take external action on its own.

For implementation details, see [Architecture](ARCHITECTURE.md),
[Security](SECURITY.md), and [Getting started](getting-started.md).
