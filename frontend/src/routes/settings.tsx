import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { fetchSystem } from "@/lib/api";
import { PageHeader, Panel } from "@/components/dashboard/page-header";
import { Chip } from "@/components/dashboard/badges";

export const Route = createFileRoute("/settings")({
  head: () => ({ meta: [{ title: "Settings — ColorStack AI" }] }),
  component: SettingsPage,
});

function SettingsPage() {
  const { data, isPending, error } = useQuery({ queryKey: ["system"], queryFn: fetchSystem });
  if (isPending) return <p className="text-sm text-muted-foreground">Checking system…</p>;
  if (error) throw error;
  const rows = [
    { label: "Chapter", value: "University of Minnesota" },
    { label: "Workspace", value: "ColorStack Exec Ops" },
    { label: "Brief delivery", value: data.dailyBriefSchedule },
    { label: "Automatic brief", value: data.dailyBriefEnabled ? "Enabled" : "Disabled" },
  ];
  const integrations = [
    { name: "Discord", detail: "Ingestion and configured brief delivery", status: data.discord },
    { name: "Local AI", detail: "Local extraction through Ollama", status: data.extraction },
    { name: "Database", detail: "PostgreSQL organizational state", status: data.database },
    { name: "Reasoning", detail: "Bounded context reasoning provider", status: data.reasoning },
  ];
  return (
    <>
      <PageHeader title="Settings" subtitle="Read-only local runtime status" />
      <div className="grid gap-3 lg:grid-cols-2">
        <Panel title="Workspace" bodyClassName="">
          <dl>
            {rows.map((row) => (
              <div
                key={row.label}
                className="flex items-center justify-between border-b border-border/70 px-3 py-2 text-[12.5px] last:border-0"
              >
                <dt className="text-muted-foreground">{row.label}</dt>
                <dd className="font-medium">{row.value}</dd>
              </div>
            ))}
          </dl>
        </Panel>
        <Panel title="Integrations" bodyClassName="">
          <ul>
            {integrations.map((integration) => (
              <li
                key={integration.name}
                className="flex items-center justify-between gap-3 border-b border-border/70 px-3 py-2 last:border-0"
              >
                <div className="min-w-0">
                  <p className="text-[12.5px] font-medium">{integration.name}</p>
                  <p className="text-[11.5px] text-muted-foreground">{integration.detail}</p>
                </div>
                <Chip
                  variant={
                    integration.status === "Connected" || integration.status === "Configured"
                      ? "success"
                      : "info"
                  }
                >
                  {integration.status}
                </Chip>
              </li>
            ))}
          </ul>
        </Panel>
      </div>
    </>
  );
}
