# Agent instructions

These rules apply to automated coding work in this repository.

## Scope

- Preserve the existing Discord ingestion, PostgreSQL archive, and local Ollama
  extraction behavior.
- Do not begin Phase 4 unless explicitly requested.
- Keep raw Discord messages as the local source of truth.
- Keep persistence and model boundaries replaceable.

## Privacy and security

- Never commit `.env`, tokens, credentials, Discord data, database dumps, or
  copied private conversations.
- Keep Discord data, PostgreSQL, and Ollama processing local.
- Do not send Discord content to external APIs.
- Follow [SECURITY.md](SECURITY.md) and
  [BOT_PERMISSIONS.md](BOT_PERMISSIONS.md).

## Discord communication

- The bot must remain read-only everywhere except `#it-dept`.
- Any future outbound feature must allow only the configured `#it-dept` channel
  ID and must reject DMs and threads.
- Discord server permissions are the authoritative enforcement layer.

## Development

- Use Python 3.12+, Pydantic, SQLAlchemy 2.x, Alembic, PostgreSQL, and local
  Ollama according to the current architecture.
- Add migrations for schema changes; do not alter the database schema manually.
- Keep changes focused and update relevant documentation and tests.
- Run Pyright and the test suite before committing substantive changes.

```bash
.venv/bin/pyright
TEST_DATABASE_URL=postgresql+psycopg://localhost/colorstack_ai_test \
  .venv/bin/python -m unittest discover -s tests -v
```

## Git

- Review diffs and check for secrets before every commit.
- Use small commits with short, plain messages.
- Push each meaningful commit.
- Do not add co-author, AI attribution, generated-by tags, or emojis.
