import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { fetchPlaybooks } from "@/lib/api";
import { PageHeader, Panel } from "@/components/dashboard/page-header";
import { Chip } from "@/components/dashboard/badges";

export const Route = createFileRoute("/playbooks")({
  head: () => ({
    meta: [
      { title: "Playbooks — ColorStack AI" },
      {
        name: "description",
        content: "Event templates with required items, optional items, and default lead times.",
      },
      { property: "og:title", content: "Playbooks — ColorStack AI" },
      {
        property: "og:description",
        content: "Event templates with required items, optional items, and default lead times.",
      },
    ],
  }),
  component: PlaybooksPage,
});

function PlaybooksPage() {
  const {
    data: playbooks = [],
    isPending,
    error,
  } = useQuery({ queryKey: ["playbooks"], queryFn: fetchPlaybooks });
  if (isPending) return <p className="text-sm text-muted-foreground">Loading playbooks…</p>;
  if (error) throw error;
  return (
    <>
      <PageHeader
        title="Playbooks"
        subtitle="Requirement templates applied when a new event is created · informational"
      />
      <div className="grid gap-3 lg:grid-cols-2">
        {playbooks.map((playbook) => (
          <Panel
            key={playbook.id}
            title={playbook.name}
            description={`${playbook.required.length + playbook.optional.length} requirements · lead time ${playbook.leadTime}`}
            bodyClassName="p-3 space-y-3"
          >
            <div>
              <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                Required
              </p>
              <div className="flex flex-wrap gap-1.5">
                {playbook.required.map((item) => (
                  <Chip key={item} variant="info">
                    {item}
                  </Chip>
                ))}
              </div>
            </div>
            <div>
              <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                Optional
              </p>
              <div className="flex flex-wrap gap-1.5">
                {playbook.optional.map((item) => (
                  <Chip key={item}>{item}</Chip>
                ))}
              </div>
            </div>
          </Panel>
        ))}
      </div>
    </>
  );
}
