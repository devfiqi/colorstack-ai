# VP Phase 2 — Interactive workspace

The first Phase 2 slice replaces the disabled Ask page with an advisory-only VP
workspace.

## Implemented

- Ask organization-, event-, task-, and person-scoped questions through the
  existing bounded reasoning boundary.
- Submit pasted conversations, meeting notes, emails, transcripts, document
  text, and general notes to a local inbox.
- Process pending sources with the configured local Ollama model as part of the
  continuous pipeline.
- Review each extracted fact with explicit approve and reject controls.
- Include only approved facts in advisor context.
- Filter approved facts for entity-scoped questions and cap organization-wide
  intake context.
- Preserve sources, proposals, model output, review state, and timestamps in
  PostgreSQL.

## Safety boundary

Raw submitted content remains local. The cloud reasoning provider receives only
bounded Phase 6 context and relevant structured facts that the VP explicitly
approved. The advisor returns recommendations and questions; it cannot send
messages or take external actions.

## Deferred

- File parsing for PDF and DOCX.
- Native Google Docs and other connectors.
- Temporary, non-retained context.
- Multi-turn chat history.
- Generalized provenance that can reconcile approved non-Discord facts into the
  authoritative current-state projection.
