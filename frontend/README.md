# ColorStack AI dashboard

This is the local React dashboard for the ColorStack AI backend. It preserves
the imported design while loading live, read-only data from FastAPI.

## Development

Start the API from the repository root:

```bash
colorstack-api
```

Then start the frontend:

```bash
cd frontend
bun install
bun run dev
```

Open `http://localhost:5173`. The default API URL is
`http://localhost:8000`; override it with `VITE_API_URL` when necessary.

## Checks

```bash
bun run build
bun run lint
```

The app uses React 19, TypeScript, Vite, TanStack Router, React Query, Tailwind
CSS, and the imported Radix/shadcn components. Interactive AI is intentionally
disabled because Phase 9 is deferred.
