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

Status: accepted for Phase 1.

Use JSONL upserts and deletion tombstones. This preserves edit history, supports
simple inspection, and avoids pretending the verification file is a database.
It is not intended for concurrent writers or complex queries.

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

Raw records stay in the Git-ignored `data/` directory. No application component
uploads messages to GitHub, an AI provider, or an external database. Any future
external processing requires a deliberate security and privacy decision.
