# ColorStack AI

ColorStack AI is an internal AI chief-of-staff system for the University of
Minnesota ColorStack Discord server. It turns conversations into structured
organizational context and proactive executive updates.

## Architecture

```text
Discord
  ↓
Ingestion
  ↓
Raw message storage
  ↓
Local LLM extraction
  ↓
Structured organizational state
  ↓
Reasoning model
  ↓
Daily executive brief / on-demand answers
```

### Local LLM extraction

A local model will handle repetitive parsing. For example:

```text
"I'll handle food for Adobe by Friday."
```

becomes:

```json
{
  "event": "Adobe Ideathon",
  "task": "Handle food",
  "owner": "speaker",
  "deadline": "Friday"
}
```

The extraction layer will identify:

- tasks
- owners
- deadlines
- decisions
- blockers
- event updates

### Organizational memory

The system will maintain the current state of each event while preserving the
original Discord messages as source context.

### Reasoning

A stronger reasoning model will use the structured context to answer questions
and generate proactive daily status reports for executive leadership.

## Current status

Phase 1 Discord ingestion is implemented. The service discovers accessible
channels and threads, backfills message history, normalizes message metadata,
and records live creates, edits, and deletions in local storage.

Local LLM extraction, organizational memory, reasoning, and executive reports
are planned but not implemented yet.
