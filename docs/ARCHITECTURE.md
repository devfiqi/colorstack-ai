# Architecture

ColorStack AI converts Discord activity into durable organizational context.
Ingestion, the local PostgreSQL archive, local fact extraction, and
organizational state reconciliation are implemented. Phase 5 adds event
playbooks and evidence-based readiness evaluation. Phase 6 adds bounded,
question-aware retrieval and structured context assembly. Phase 7 adds tracked
reasoning, Phase 8 adds scheduled executive briefs, and Phase 10 exposes the
existing services through a local read-only dashboard API.

## System flow

```text
Discord
  ↓
Ingestion                         implemented
  ↓
Raw PostgreSQL archive           implemented locally
  ↓
Relevance filter                 implemented
  ↓
Local LLM fact extraction        implemented
  ↓
Structured organizational state implemented
  ↓
Event playbooks and readiness    implemented
  ↓
Retrieval and context assembly  implemented
  ↓
Reasoning model                  implemented
  ↓
Daily executive brief            implemented
  ↓
FastAPI dashboard API            implemented locally
  ↓
React dashboard                  implemented locally
```

## Implemented components

- `config.py` loads `.env` and validates the Discord token.
- `discord/client.py` owns the Discord connection and ingestion lifecycle.
- `discord/channels.py` discovers readable channels and accessible threads.
- `discord/backfill.py` reads complete available history and reports progress.
- `discord/listeners.py` handles live creates, edits, and deletions.
- `ingestion/normalize.py` converts Discord objects into internal models.
- `ingestion/models.py` defines the normalized Pydantic records.
- `ingestion/store.py` defines the persistence boundary.
- `ingestion/postgres_store.py` implements transactional PostgreSQL persistence.
- `db/models.py` defines the SQLAlchemy archive schema.
- `db/session.py` owns the async engine and session factory.
- `alembic/` contains the versioned database migrations.
- `extraction/relevance.py` performs conservative deterministic filtering.
- `extraction/context.py` builds bounded reply and nearby-message context.
- `extraction/ollama.py` validates and calls a local Ollama model.
- `extraction/prompt.py` contains the versioned extraction instructions.
- `extraction/processor.py` coordinates filtering, extraction, and progress.
- `extraction/repository.py` persists runs, states, and append-only facts.
- `extract/` provides backfill, new-message, and retry CLI modes.
- `state/resolution.py` conservatively resolves canonical events and tasks.
- `state/policy.py` contains deterministic precedence and lifecycle rules.
- `state/repository.py` persists current values, audit history, and unresolved
  facts transactionally.
- `state/processor.py` coordinates idempotent reconciliation and rebuilds.
- `state/ambiguity.py` validates optional local-model interpretations.
- `state/` provides reconcile-new, retry-unresolved, and rebuild CLI modes.
- `playbooks/loader.py` validates and composes versioned YAML definitions.
- `playbooks/detection.py` conservatively selects event types and overlays.
- `playbooks/evaluator.py` compares event state with explicit completion rules.
- `playbooks/scoring.py` computes explainable urgency and weighted readiness.
- `playbooks/repository.py` persists definitions, assignments, current
  requirement state, evidence, and evaluation history.
- `requirements/` provides event and all-active-event evaluation commands.
- `context/retrieval.py` centralizes entity resolution and structured SQL
  retrieval across archive, fact, state, and playbook tables.
- `context/query_parser.py` deterministically identifies supported query scopes
  and intents.
- `context/ranking.py` prioritizes urgency, blockers, deadlines, provenance,
  query matches, and recency.
- `context/*_context.py` assembles bounded event, task, person, and organization
  packages.
- `context/builder.py` provides the Phase 7-facing context boundary.
- `context/` exposes JSON-producing CLI commands.
- `reasoning/` runs bounded structured context through the configured provider
  and records latency, usage, and estimated cost.
- `briefing/` constructs, formats, schedules, records, and delivers daily
  executive briefs with duplicate prevention. Scheduled runs generate for
  review; Discord delivery is manual-only.
- `pipeline/` continuously runs local extraction, state reconciliation, and
  event-playbook evaluation after Discord backfill. Stage failures are isolated
  and every cycle records health for the dashboard.
- `api/` maps existing context and persistence services to read-only dashboard
  endpoints without duplicating state or playbook logic.
- `frontend/` contains the imported React/TanStack Router dashboard, now backed
  by FastAPI rather than mock data.

## Runtime flow

1. Validate configuration and open the message store.
2. Connect with guild, message, member, and message-content intents.
3. Discover readable text channels and active or archived threads.
4. Backfill each channel independently; a channel failure does not stop others.
5. Upsert messages and related snapshots by Discord message ID.
6. Start the local intelligence pipeline after backfill.
7. Continuously extract new messages, reconcile new facts, retry failed or
   unresolved work periodically, and reevaluate active-event playbooks.
8. Continue processing live creates, raw edits, and deletion events.

The event handlers are active during backfill, preventing a gap between history
collection and live ingestion.

## Advisory boundary

The runtime may ingest source material, update derived internal state, evaluate
requirements, and generate recommendations. It does not send messages, assign
work, edit calendars or documents, or take another external action
automatically. Scheduled daily briefs are stored for dashboard review. Discord
delivery remains an explicit CLI action initiated by a user.

Pipeline stages fail independently so an unavailable local model does not stop
reconciliation or playbook evaluation over already-persisted facts. Cycle
status and per-stage errors are stored in `pipeline_runs`; the system API marks
the pipeline stale when it has not completed within the configured freshness
window.

## Storage boundary

`MessageStore` isolates Discord ingestion from persistence. Phase 1 uses the
append-only JSONL verification store; Phase 2 makes `PostgresMessageStore` the
runtime default without changing discovery, normalization, or listeners.

PostgreSQL is the durable raw source of truth. Message IDs are primary keys,
edits update the existing row and related snapshots, and deletions set a flag
and timestamp rather than removing data. Attachments and reactions are separate
tables tied to messages with cascading foreign keys.

## Extraction boundary

Phase 3 records facts attributable to individual source messages and extraction
versions. It deliberately preserves competing facts and does not decide which is
currently true. Low-relevance messages remain in the raw archive and receive a
processing-state record rather than being deleted.

## State boundary

Phase 4 treats extracted facts as immutable evidence and current state as a
rebuildable projection. Every applied value points to a fact and source message;
each transition is recorded in `state_changes`. Ambiguous entity matches or
unsafe updates are retained in processing and unresolved records instead of
being guessed.

Entity resolution is guild-scoped and conservative. Mutable values use an
extensible field/value representation over canonical event and task identities.
Deterministic policy controls precedence; Ollama can only return a validated
proposal and never writes state directly.

## Playbook boundary

Phase 5 compares current event and task state with version-controlled
expectations. Missing requirements are inferred gaps, not extracted facts.
Completion requires source-linked evidence. Optional items without evidence
remain unknown rather than being silently treated as complete or applicable.

Event-type detection may select one base playbook plus the company-sponsored
overlay. Ambiguous base types remain unknown. Playbook files can extend generic
definitions for future ColorStack-specific customization.

## Context boundary

Phase 6 does not summarize or reason. It selects compact source-linked material
for a known entity or deterministic query interpretation. Current state and
urgent playbook gaps outrank historical facts and raw messages. Explicit limits
bound every high-volume collection.

Question parsing fails closed when an event, task, or person resolves to zero or
multiple candidates. The retrieval service uses relational links, normalized
names, SQL filters, provenance, and recency; its interface can accept a vector
search implementation later without changing context models.

## Dashboard boundary

Phase 10 is a read-only local projection. FastAPI binds to loopback by default,
allows only configured local development origins, and exposes overview, event,
task, person, activity, brief, playbook, and system-health data. It does not
write organizational state or implement interactive AI.
