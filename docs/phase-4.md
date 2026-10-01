# Phase 4 — Organizational state

Phase 4 reconciles immutable extracted facts into a mutable, source-linked view
of active events and tasks. It does not add playbooks, reporting, or outbound
Discord behavior.

## Flow

```text
extracted fact
  → conservative entity resolution
  → deterministic field mapping
  → precedence policy
  → current_state_values
  → state_changes audit trail
```

Unsafe facts go to `unresolved_facts`; raw messages and extracted facts are never
modified or deleted.

## Entity resolution

Resolution is scoped to the Discord guild and tries:

1. exact normalized event or task names
2. stored event aliases
3. one exact distinctive-token event match
4. one event resolved from a reply or recent channel context

Explicit names create deterministic event or task IDs. Generic or conflicting
names remain unresolved.

## Reconciliation policy

- Newer facts may update older values.
- Explicit evidence beats inferred evidence.
- Lower-confidence inference cannot replace stronger inferred state.
- Exact timestamps beat vague date text.
- Ownership facts replace the current owner.
- Completion and cancellation update lifecycle state.
- Terminal work becomes active again only after an explicit reopen statement.
- Older, conflicting, or unsafe facts are recorded without changing state.

Current fields are extensible JSON values. Supported domains include event time,
location, sponsors, funding, status, owners, deadlines, blockers, decisions,
registration, food, judges or speakers, marketing, volunteers, open questions,
and dependencies.

## Commands

Apply up to 100 facts that have no reconciliation state:

```bash
python -m colorstack_ai.state reconcile-new
```

Retry up to 100 unresolved or failed facts:

```bash
python -m colorstack_ai.state retry-unresolved
```

Recreate all Phase 4 derived tables from active facts:

```bash
python -m colorstack_ai.state rebuild
```

Use `--limit N` with incremental or retry mode. Add `--resolve-ambiguous` to
allow the configured localhost Ollama model to propose a field interpretation.
The proposal is Pydantic-validated and still passes deterministic policy.

## Migrations

```bash
alembic upgrade head
alembic current
alembic check
```

Phase 4 migration head is `20261001_0003`.

## Verification

```sql
SELECT COUNT(*) FROM events;
SELECT COUNT(*) FROM tasks;
SELECT COUNT(*) FROM current_state_values;
SELECT COUNT(*) FROM state_changes;
SELECT COUNT(*) FROM unresolved_facts WHERE status = 'unresolved';

SELECT entity_type, entity_id, field, value, source_fact_id, source_message_id
FROM current_state_values
ORDER BY entity_type, entity_id, field;

SELECT field, previous_value, new_value, reason, source_message_id
FROM state_changes
ORDER BY effective_at;
```

To verify rebuilds, capture current values and change counts, run `rebuild`, and
compare them again. Entity IDs and semantic state are deterministic.

## Tests

```bash
TEST_DATABASE_URL=postgresql+psycopg://localhost/colorstack_ai_test \
  python -m unittest discover -s tests -v

.venv/bin/pyright
```

Normal tests mock Ollama. They do not require a live model.

## Current limitations

- Resolution intentionally avoids fuzzy or aggressive entity merging.
- Phase 3 does not automatically re-extract successfully processed Discord
  messages after an edit.
- Multiple extraction versions can contain semantically duplicate observations.
- List-like domains such as blockers and open questions expose the latest
  current value; the full sequence remains in `state_changes`.
- There is no human review UI or dedicated state query API yet.
