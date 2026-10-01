# Phase 10 — Local operations dashboard

Phase 10 combines the imported Lovable mock frontend with the existing Python
system as a local, read-only operations dashboard.

## Stack

- FastAPI and Uvicorn on `127.0.0.1:8000`
- React 19, TypeScript, Vite, TanStack Router, React Query, and Tailwind 4
- Bun for frontend dependency management
- PostgreSQL and the existing Phase 1–8 services as the source of truth

The Lovable runtime wrapper was removed, but the supplied page structure,
responsive shell, styles, components, navigation, and visual design remain.

## API

```text
GET /api/overview
GET /api/events
GET /api/events/{event_id}
GET /api/tasks?status=&owner=&event=&urgency=
GET /api/people
GET /api/people/{person_id}
GET /api/activity?hours=48
GET /api/briefs/latest
GET /api/playbooks
GET /api/system
GET /api/health
```

Routes call the retrieval/context layer and read existing persistence models.
They do not reimplement reconciliation or requirement evaluation.

## Run locally

```bash
alembic upgrade head
python -m pip install -e '.[dev]'
colorstack-api
```

In another terminal:

```bash
cd frontend
bun install
bun run dev
```

Set `VITE_API_URL` only when the API is not at `http://localhost:8000`.

## Privacy and scope

The API binds to loopback and permits only configured dashboard origins. It
returns compact derived state, not the complete Discord archive. The UI has no
write endpoints. The old `/ask` mock is disabled and removed from navigation;
interactive AI remains deferred with Phase 9.

## Verification

```bash
.venv/bin/pyright
TEST_DATABASE_URL=postgresql+psycopg://localhost/colorstack_ai_test \
  .venv/bin/python -m unittest discover -s tests -v
cd frontend && bun run build && bun run lint
```

The frontend lint baseline contains six shadcn fast-refresh warnings and no
errors.
