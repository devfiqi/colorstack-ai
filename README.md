# ColorStack AI

ColorStack AI is an internal AI chief-of-staff system for the University of
Minnesota ColorStack Discord server. Its long-term purpose is to understand the
organization's activity and context so it can support leadership with useful
reports and operational insights.

The current Phase 1 implementation is a Python Discord ingestion service. It
discovers accessible channels and threads, backfills message history, normalizes
message metadata, and records live message creates, edits, and deletions in a
replaceable local store. It does not yet include AI analysis, summarization, or
production database storage.
