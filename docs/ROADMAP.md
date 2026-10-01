# Roadmap

## Phase 1 — Discord ingestion

Status: implemented.

- Connect with validated credentials and required intents.
- Discover readable guild channels and accessible threads.
- Backfill complete available message history.
- Normalize messages, replies, attachments, and reactions.
- Deduplicate historical records across restarts.
- Record live creates, edits, individual deletions, and bulk deletions.
- Keep persistence behind a replaceable store interface.

## Phase 2 — Durable structured storage

Status: implemented and manually verified.

- PostgreSQL is the durable, queryable raw archive.
- SQLAlchemy models and Alembic migrations define the schema.
- Backfills are resumable and idempotent by Discord message ID.
- Edits update existing rows; deletes preserve content through soft deletion.
- Attachments and reaction snapshots use related tables.
- Integration tests cover duplicates, edits, related records, and deletions.
- Discord content remains local.

Deferred operational work:

- Define backup and restore procedures.
- Define retention and relevance rules before discarding any raw data.
- Evaluate batching only if message volume makes per-message transactions slow.

## Phase 3 — Local extraction

Status: implemented and manually verified.

- Conservative deterministic relevance filtering limits local-model calls.
- Bounded context includes replies and nearby channel or thread messages.
- Ollama produces Pydantic-validated organizational facts.
- Every fact records confidence, evidence kind, source message, and version.
- Processing state supports unprocessed, skipped, successful, and failed cases.
- CLI modes support historical backfill, new messages, and failed retries.
- New extraction versions preserve earlier facts rather than overwriting them.
- Local-model and persistence behavior is covered with mocked and integration
  tests.

Deferred improvements:

- Evaluate extraction quality over a larger labeled sample.
- Add a human correction workflow.
- Optimize inference latency and batching if required.

## Phase 4 — Organizational memory

Status: implemented and manually verified.

- Canonical guild-scoped events, aliases, and tasks anchor current state.
- Deterministic rules reconcile facts into extensible current values.
- Explicit evidence, date precision, lifecycle, and confidence control
  precedence.
- Every applied transition links to its fact and Discord source message.
- Ambiguous facts are deferred; optional Ollama output is validated as a
  proposal before policy evaluation.
- Incremental, retry, and deterministic rebuild modes are idempotent.
- Integration tests cover corrections, ownership, completion, cancellation,
  conflicts, aliases, unresolved facts, and rebuilds.

Deferred improvements:

- Add a human review and correction workflow for unresolved facts.
- Improve cross-message and cross-version semantic deduplication.
- Add dedicated query services when Phase 5 consumers require them.

## Phase 5 — Event playbooks

Status: implemented and manually verified.

- Seven versioned YAML definitions cover six base event types and the
  company-sponsored overlay.
- Pydantic validates requirements, lead times, dependencies, completion
  criteria, evidence rules, and extensions.
- Conservative detection supports one base type plus applicable overlays.
- Evaluation distinguishes complete, in-progress, missing, blocked, unknown,
  and not-applicable work using source-linked current state.
- Deterministic urgency considers criticality, event proximity, lead time,
  downstream dependencies, status, and sponsorship.
- Weighted readiness prioritizes required and critical requirements.
- Current requirement state and append-only evaluation history are persisted.

Deferred improvements:

- Add reviewed ColorStack-specific playbook extensions.
- Add a human applicability and completion override workflow.
- Calibrate completion rules with more real event data.

## Phase 6 — Retrieval and context assembly

Status: implemented and manually verified.

- Typed event, task, person, organization, and question-aware packages expose
  compact source-linked context.
- SQL retrieval uses entity relationships, current state, playbook results,
  recency, reply chains, and text matches without embeddings.
- Deterministic query parsing supports status, missing requirements, blockers,
  owners, tasks, deadlines, changes, priorities, responsibilities, organization
  status, and unresolved items.
- Ranking prioritizes urgency, criticality, blockers, deadlines, provenance,
  explicit query matches, event or owner matches, and recency.
- Configurable limits prevent full-history context dumps.
- Organization context combines the latest 24 hours with older unresolved
  carryover.
- Ambiguous entity matches fail closed and return candidate warnings.

Deferred improvements:

- Add PostgreSQL text-search indexes if archive size makes filtered scans slow.
- Add semantic retrieval behind the existing interface only if deterministic
  retrieval proves insufficient.
- Add a first-class people and role directory.

## Phase 7 — Reasoning

Status: implemented.

- Consume structured context packages without direct unrestricted database
  access.
- Answer leadership questions with source-linked claims.
- Preserve uncertainty and distinguish facts from inferred gaps.
- Add evaluation and approval controls before producing operational advice.

## Phase 8 — Daily executive brief

Status: implemented; production channel verification remains operational.

- Build 24-hour organization context with unresolved carryover.
- Reuse tracked Phase 7 reasoning and cost accounting.
- Format concise Discord-safe executive briefs.
- Prevent duplicate scheduled delivery with a database constraint.
- Support preview, manual send, and timezone-aware scheduling.

## Phase 9 — Interactive AI

Status: intentionally skipped.

No `/ask`, bot mentions, or dashboard Q&A is enabled.

## Phase 10 — Local operations dashboard

Status: implemented and automatically verified.

- Import the existing React dashboard without redesigning it.
- Replace centralized mock data with typed FastAPI queries.
- Expose read-only overview, event, task, person, activity, brief, playbook,
  and system endpoints.
- Run the API and frontend locally on ports 8000 and 5173.
- Preserve Phase 1–8 service and persistence boundaries.

## Later — Reporting and learning

- Answer leadership questions from structured, source-linked context.
- Generate daily executive briefs.
- Surface stale tasks, unresolved blockers, and approaching deadlines.
- Add approval and delivery controls before reports reach Discord users.
- Learn reviewed lead times and recurring failure patterns from past events.

## Not included yet

Interactive AI, historical learning, embeddings, vector search, dashboard
writes, and hosted deployment remain outside the current implementation.
