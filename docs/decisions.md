# Technical decisions

This file records decisions that materially shape the project. Revisit a
decision when its assumptions change rather than silently working around it.

## 001 — Python and discord.py

Status: accepted.

Use Python 3.12+, `discord.py`, Pydantic, and `python-dotenv`. This stack keeps
the ingestion service small and aligns with planned local model work.

## 002 — Separate ingestion from persistence

Status: accepted.

Discord modules depend on the `MessageStore` interface, not a database or file
format. Phase 2 can introduce a durable store without rewriting Discord logic.

## 003 — Append-only local verification storage

Status: superseded as the runtime default after Phase 1.

Use JSONL upserts and deletion tombstones. This preserves edit history, supports
simple inspection, and avoids pretending the verification file is a database.
The implementation remains useful for lightweight tests but is not the durable
source of truth.

## 004 — Preserve bot messages

Status: accepted.

Do not filter messages based on author type. Bot posts can contain event,
workflow, and organizational context that later extraction may need.

## 005 — Prefer completeness before relevance filtering

Status: accepted for Phase 1.

Collect all accessible history before introducing allowlists, retention rules,
or relevance classification. Discord history discarded during ingestion may
not be recoverable later. Filtering belongs behind an explicit policy.

## 006 — Use raw edit and deletion events

Status: accepted.

Use raw gateway events for edits and deletions so handling does not depend on
the message being present in the client cache. Fetch the current message on edit
when Discord still permits access.

## 007 — Keep Discord content local

Status: accepted.

Raw records stay in local PostgreSQL. No application component uploads messages
to GitHub, an external AI provider, or a hosted database. Any future external
processing requires a deliberate security and privacy decision.

## 008 — PostgreSQL as the durable raw archive

Status: accepted for Phase 2.

Use local PostgreSQL with SQLAlchemy, `psycopg`, and Alembic. Message IDs are
stable primary keys, edits update existing rows, and deletes are soft. This
provides queryability and transactional persistence without changing Discord
ingestion.

## 009 — Store current related snapshots

Status: accepted for Phase 2.

Attachments and reactions use separate tables. Each message upsert synchronizes
the current sets only when they differ. Phase 2 does not preserve a revision row
for every historical attachment or reaction change.

## 010 — Deterministic filtering before local inference

Status: accepted for Phase 3.

Use conservative keyword and reply-context signals before calling Ollama.
False positives are preferable to missed organizational facts. Skipped messages
remain in the raw archive and retain their relevance decision.

## 011 — Facts are versioned observations

Status: accepted for Phase 3.

Store facts by source message and extraction version. Do not overwrite older
facts or reconcile conflicting statements. Organizational current truth belongs
to Phase 4.

## 012 — Local Ollama only

Status: accepted for Phase 3.

Extraction calls a configurable Ollama server restricted to localhost. Model
names are configuration, prompts are centralized and versioned, and normal tests
mock inference instead of requiring a live model.

## 013 — Discord-enforced outbound policy

Status: accepted.

The bot is read-only except for the explicitly authorized `#it-dept` channel.
Discord role and channel permissions are authoritative; any future outbound
code must additionally compare an explicit channel ID and fail closed.

## 014 — Current state is a rebuildable projection

Status: accepted for Phase 4.

Keep extracted facts immutable and store mutable truth in separate current-value
rows. State changes retain the fact and source-message path. A rebuild deletes
only Phase 4 derived records and deterministically replays active facts.

## 015 — Conservative deterministic reconciliation

Status: accepted for Phase 4.

Resolve entities by guild-scoped normalized names, aliases, and unambiguous
local context. Central policy controls evidence precedence, date precision,
ownership, completion, cancellation, and explicit reopen behavior. Defer rather
than merge or overwrite when certainty is insufficient.

## 016 — Models propose; application policy decides

Status: accepted for Phase 4.

Use Ollama only when deterministic fact-to-field mapping fails and the CLI
explicitly enables ambiguity resolution. Validate its structured proposal with
Pydantic, require it to target the already resolved entity type, and pass it
through the same deterministic policy. The model never writes database state.
