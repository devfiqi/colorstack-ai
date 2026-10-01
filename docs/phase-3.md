# Phase 3: Local fact extraction

Phase 3 turns individually relevant Discord messages into structured,
source-linked organizational facts. It does not decide the current truth of an
event or organization; reconciliation belongs to Phase 4.

## Flow

```text
Raw PostgreSQL messages
  ↓
Deterministic relevance filter
  ↓
Bounded conversation context
  ↓
Local Ollama extraction
  ↓
Validated, versioned facts in PostgreSQL
```

Raw messages are never deleted or modified by extraction.

## Ollama setup

Install or start Ollama and choose a locally installed model:

```bash
brew install --cask ollama
ollama serve
ollama list
ollama pull <model>
```

Configure `.env`:

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=<installed-model>
EXTRACTION_VERSION=v2
```

The CLI validates the local server and exact model name before processing.
`OLLAMA_BASE_URL` is restricted to localhost.

## Extraction categories

- event mention or update
- task or commitment
- ownership change
- deadline
- decision
- blocker or dependency
- sponsor request or funding update
- location change
- status change or cancellation
- open question

Facts may include event, task, owner, deadline, status, value, confidence, and
explicit/inferred evidence fields. Missing information remains null.

## Relevance filtering

The deterministic filter looks for conservative signals including dates,
commitments, ownership, task verbs, events, sponsors, logistics, funding,
status, blockers, and replies to messages already marked relevant.

Low-value messages are marked `skipped_low_relevance`; they remain untouched in
the raw archive. Prefer changing the version when filter or prompt behavior
changes so earlier decisions remain inspectable.

## Context

Each extraction receives:

- source content, author ID/name, channel, and timestamp
- referenced parent message when available
- up to three preceding messages
- up to two following messages
- messages from the same channel or thread within 24 hours

Context content is bounded, and full conversation text is not logged.

## Commands

Process unprocessed history from oldest to newest:

```bash
python -m colorstack_ai.extract backfill
python -m colorstack_ai.extract backfill --limit 100
```

Process up to 100 newest unprocessed messages:

```bash
python -m colorstack_ai.extract new
```

Retry failed or interrupted messages:

```bash
python -m colorstack_ai.extract retry-failed
```

Process the same raw messages under a new non-destructive version:

```bash
python -m colorstack_ai.extract backfill --version v3
```

## Database tables

- `extraction_runs`: model/configuration, status, timestamps, and counts.
- `message_processing_state`: relevance and processing status per message and
  extraction version.
- `extracted_facts`: structured facts linked to raw source messages and runs.

See [data-model.md](data-model.md) for field-level details.

## Verification

```sql
SELECT status, COUNT(*)
FROM message_processing_state
GROUP BY status;

SELECT fact_type, COUNT(*)
FROM extracted_facts
WHERE active
GROUP BY fact_type
ORDER BY COUNT(*) DESC;

SELECT source_message_id, fact_type, event_name, task, owner_name,
       deadline_text, confidence
FROM extracted_facts
ORDER BY created_at DESC
LIMIT 20;
```

Run tests without a live model:

```bash
TEST_DATABASE_URL=postgresql+psycopg://localhost/colorstack_ai_test \
  python -m unittest discover -s tests -v
```

## Limitations

- Extraction quality depends on the configured local model.
- The current processor is sequential and can be slow for large backfills.
- Filtering is heuristic and will produce false positives and false negatives.
- Raw model output is retained locally for debugging.
- A successfully processed message is not automatically reprocessed after a
  later Discord edit; use a new extraction version when needed.
- Phase 3 preserves conflicting facts and does not build current state.
- The bot does not post extraction results to Discord.
