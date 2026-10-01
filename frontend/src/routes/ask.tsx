import { createFileRoute } from "@tanstack/react-router";
import { PageHeader, Panel } from "@/components/dashboard/page-header";

export const Route = createFileRoute("/ask")({
  head: () => ({ meta: [{ title: "Ask AI — Not Enabled" }] }),
  component: AskPage,
});

function AskPage() {
  return (
    <>
      <PageHeader
        title="Ask AI — Not Enabled"
        subtitle="Interactive Discord and dashboard Q&A are intentionally deferred"
      />
      <Panel title="Phase 9 remains skipped">
        <p className="text-[13px] text-muted-foreground">
          This dashboard is read-only. Use the overview, events, tasks, people, activity, and daily
          brief pages to inspect current organizational state.
        </p>
      </Panel>
    </>
  );
}
