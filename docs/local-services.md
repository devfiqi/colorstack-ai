# Always-on local services

ColorStack AI uses three macOS LaunchAgents so the local product remains
available after terminals close and restarts automatically after a crash:

- `com.colorstack-ai.api` serves the read-only dashboard API on port 8000.
- `com.colorstack-ai.dashboard` serves the built frontend on port 5173.
- `com.colorstack-ai.worker` ingests Discord and runs the local intelligence
  pipeline. It updates only ColorStack AI's internal database and never sends
  Discord messages or takes external action.

PostgreSQL remains managed by Homebrew. Ollama must also be running locally for
the worker's extraction stage. Logs are written under `.runtime/`, which is
ignored by Git.

After frontend changes, run `cd frontend && bun run build`, then kickstart the
dashboard agent. After backend changes, kickstart the API and worker agents.

The services run while the user is logged in. The Mac must remain awake for
`http://localhost:5173` to stay reachable. The URL is intentionally local and
is not exposed to the internet.
