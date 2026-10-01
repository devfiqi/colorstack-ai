# ColorStack AI

ColorStack AI is an internal AI chief-of-staff system for the University of
Minnesota ColorStack Discord server. It turns conversations into structured
organizational context and proactive executive updates.

## Current status

Phase 1 Discord ingestion is implemented. The Python service discovers
accessible channels and threads, backfills message history, normalizes message
metadata, and records live creates, edits, and deletions in local storage.

AI extraction, organizational memory, reasoning, and executive reports are
planned but not implemented.

## System direction

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

## Documentation

- [Architecture](ARCHITECTURE.md)
- [Roadmap](ROADMAP.md)
- [Security](SECURITY.md)
- [Phase 1 ingestion](docs/phase-1.md)
- [Data model](docs/data-model.md)
- [Technical decisions](docs/decisions.md)

Discord content and credentials remain local. They are excluded from Git and
are not sent to an AI provider or external database.
