# Phase 6 — Retrieval and context assembly

Phase 6 builds compact, source-linked context for a future reasoning model. It
does not answer questions, summarize conversations, or generate reports.

## Context types

- Event: current state, readiness, requirements, tasks, blockers, owners,
  deadlines, recent changes, messages, facts, and unresolved facts
- Task: state, owner, event, dependencies, source facts, changes, and messages
- Person: assigned work, owned events, commitments, deadlines, unresolved
  responsibilities, and recent activity
- Organization: active and urgent events, critical gaps, blockers, upcoming
  deadlines, unresolved carryover, and recent changes

Question-aware context adds a deterministic interpretation containing scope,
intent, entity text, resolved identity, confidence, ambiguity, and reason.

## Supported intents

- event status
- missing requirements
- blockers
- owner lookup
- task lookup
- deadlines
- recent changes
- priorities
- person responsibilities
- organization status
- unresolved items

Unsupported or ambiguous questions return no context and include warnings.

## Retrieval order

The package prioritizes:

1. current state
2. critical and high-urgency playbook gaps
3. blockers
4. deadlines
5. owners
6. recent changes
7. unresolved tasks and commitments
8. provenance-linked or entity-matching messages
9. relevant historical facts

Messages are candidates only when they are source evidence, match the entity or
query, belong to the reply chain, or share a relevant thread. Ranking combines
provenance, explicit query matches, entity matches, and recency.

## Time behavior

The default recent window is 24 hours. Organization context combines that
window with older unresolved commitments and unresolved facts so unfinished
work is not lost from a future daily brief.

## Limits

Defaults:

```text
messages: 20
changes: 15
tasks: 25
requirements: 50
facts: 30
events: 20
recent window: 24 hours
```

Override them locally with:

```env
CONTEXT_MESSAGES_LIMIT=20
CONTEXT_CHANGES_LIMIT=15
CONTEXT_TASKS_LIMIT=25
CONTEXT_REQUIREMENTS_LIMIT=50
CONTEXT_FACTS_LIMIT=30
CONTEXT_EVENTS_LIMIT=20
CONTEXT_RECENT_HOURS=24
```

## Commands

```bash
python -m colorstack_ai.context event <event-id>
python -m colorstack_ai.context task <task-id>
python -m colorstack_ai.context person <discord-user-id>
python -m colorstack_ai.context org
python -m colorstack_ai.context query "What are we missing for Adobe?"
```

Commands print typed JSON suitable for Phase 7.

## Verification

The seeded Adobe Ideathon verification confirmed:

- an event query resolved to `missing_requirements`
- event context retained readiness, critical gaps, blocker, facts, and source
  messages
- task context retained Salman as owner and the blocking source fact
- person context returned assigned and unresolved work
- organization context included one active event, one critical requirement, one
  blocker, and older unresolved carryover
- collection limits and source-message provenance were preserved
- ambiguous questions returned no guessed context

## Current limitations

- People are inferred from Discord IDs, owners, facts, and message authors;
  there is no role directory yet.
- Text matching uses filtered SQL and deterministic token matching, not
  embeddings or pgvector.
- Task dependencies are inferred from current dependency text rather than a
  dedicated task graph.
- No natural-language answer is generated. Phase 7 will consume the package.
