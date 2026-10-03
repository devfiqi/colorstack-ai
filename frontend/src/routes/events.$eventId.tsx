import { useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ChevronDown, ChevronRight, FileSearch } from "lucide-react";
import { fetchEvent, fetchTasks, type Requirement } from "@/lib/api";
import { PageHeader, Panel } from "@/components/dashboard/page-header";
import { Chip, PriorityBadge, ReadinessBar, StatusBadge } from "@/components/dashboard/badges";
import { TaskTable } from "@/components/dashboard/task-table";

export const Route = createFileRoute("/events/$eventId")({
  loader: async ({ params }) => ({ event: await fetchEvent(params.eventId) }),
  head: ({ loaderData }) => {
    if (!loaderData) {
      return {
        meta: [
          { title: "Event not found — ColorStack AI" },
          { name: "robots", content: "noindex" },
        ],
      };
    }
    const title = `${loaderData.event.name} — ColorStack AI`;
    return {
      meta: [
        { title },
        { name: "description", content: loaderData.event.assessment ?? "Event operational detail" },
        { property: "og:title", content: title },
        {
          property: "og:description",
          content: loaderData.event.assessment ?? "Event operational detail",
        },
      ],
    };
  },
  component: EventDetail,
});

function RequirementRow({ requirement }: { requirement: Requirement }) {
  const [open, setOpen] = useState(false);
  return (
    <li className="border-b border-border/70 last:border-0">
      <div className="row-hover flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="text-muted-foreground transition-colors hover:text-foreground"
          aria-label={open ? "Collapse detail" : "Expand detail"}
        >
          {open ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
        </button>
        <span className="min-w-[8rem] flex-1 text-[12.5px] font-medium">{requirement.label}</span>
        <StatusBadge status={requirement.status} />
        <span className="w-28 text-[12px] text-muted-foreground">{requirement.owner}</span>
        <PriorityBadge priority={requirement.urgency} />
        <Chip className="gap-1">
          <FileSearch className="size-3" />
          {requirement.source}
        </Chip>
      </div>
      {open && (
        <p className="bg-surface px-10 py-2 text-[12px] text-muted-foreground">
          {requirement.detail}
        </p>
      )}
    </li>
  );
}

function EventDetail() {
  const { event } = Route.useLoaderData();
  const [collapsedGroups, setCollapsedGroups] = useState<string[]>([]);
  const { data: tasks = [] } = useQuery({ queryKey: ["tasks"], queryFn: fetchTasks });
  const requirements = event.requirements ?? [];
  const groups = Array.from(new Set(requirements.map((r) => r.group)));
  const eventTasks = tasks.filter((task) => task.eventId === event.id);

  const toggleGroup = (group: string) =>
    setCollapsedGroups((prev) =>
      prev.includes(group) ? prev.filter((g) => g !== group) : [...prev, group],
    );

  return (
    <>
      <Link
        to="/events"
        className="inline-flex items-center gap-1.5 text-[12px] text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-3.5" /> Events
      </Link>

      <PageHeader
        title={event.name}
        subtitle={`${event.date}, 2026`}
        actions={
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] text-muted-foreground">
            <span>
              Type <span className="text-foreground">{event.type}</span>
            </span>
            {event.sponsor && (
              <span>
                Sponsor <span className="text-foreground">{event.sponsor}</span>
              </span>
            )}
            <span className="flex items-center gap-1.5">
              Urgency <PriorityBadge priority={event.urgency} />
            </span>
            <span className="flex items-center gap-1.5">
              Readiness <ReadinessBar value={event.readiness} />
            </span>
          </div>
        }
      />

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_300px]">
        <div className="space-y-4">
          <Panel title="AI Assessment" description="Generated from the latest sync">
            <p className="text-[13px] leading-relaxed">
              {event.assessment ?? "No assessment available."}
            </p>
          </Panel>

          <Panel
            title="Requirements"
            description={`${requirements.filter((r) => r.status === "complete").length} of ${requirements.length} complete`}
            bodyClassName=""
          >
            {groups.map((group) => {
              const collapsed = collapsedGroups.includes(group);
              const items = requirements.filter((r) => r.group === group);
              return (
                <div key={group}>
                  <button
                    type="button"
                    onClick={() => toggleGroup(group)}
                    className="flex w-full items-center gap-2 border-b border-border bg-surface px-3 py-1.5 text-left text-[11px] font-semibold uppercase tracking-wide text-muted-foreground transition-colors hover:text-foreground"
                  >
                    {collapsed ? (
                      <ChevronRight className="size-3.5" />
                    ) : (
                      <ChevronDown className="size-3.5" />
                    )}
                    {group}
                    <span className="ml-auto font-normal normal-case tracking-normal">
                      {items.length} items
                    </span>
                  </button>
                  {!collapsed && (
                    <ul>
                      {items.map((requirement) => (
                        <RequirementRow key={requirement.id} requirement={requirement} />
                      ))}
                    </ul>
                  )}
                </div>
              );
            })}
          </Panel>

          <Panel title="Linked Tasks" description={`${eventTasks.length} tasks`} bodyClassName="">
            <TaskTable data={eventTasks} compact />
          </Panel>
        </div>

        <div className="space-y-4">
          <Panel title="Owners" bodyClassName="">
            <ul>
              {(event.owners ?? []).map((owner) => (
                <li
                  key={owner.name}
                  className="flex items-center justify-between border-b border-border/70 px-3 py-2 text-[12.5px] last:border-0"
                >
                  <span className="font-medium">{owner.name}</span>
                  <span className="text-muted-foreground">{owner.scope}</span>
                </li>
              ))}
            </ul>
          </Panel>

          <Panel title="Division readiness" bodyClassName="">
            {(event.divisionReadiness ?? []).map((item) => (
              <div
                key={item.division}
                className="border-b border-border/70 px-3 py-2 last:border-0"
              >
                <div className="flex items-center justify-between gap-2 text-[12px]">
                  <span className="font-medium">{item.division}</span>
                  <span className="text-muted-foreground">
                    {item.complete}/{item.total} done
                  </span>
                </div>
                <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-muted">
                  <div className="h-full bg-info" style={{ width: `${item.readiness}%` }} />
                </div>
                {item.needsClarification > 0 && (
                  <p className="mt-1 text-[10.5px] text-warning-foreground">
                    {item.needsClarification} need confirmation
                  </p>
                )}
              </div>
            ))}
          </Panel>

          <Panel title="Key Dates" bodyClassName="">
            <ul>
              {(event.keyDates ?? []).map((date) => (
                <li
                  key={date.label}
                  className="flex items-center justify-between border-b border-border/70 px-3 py-2 text-[12.5px] last:border-0"
                >
                  <span>{date.label}</span>
                  <span className="font-medium tabular-nums">{date.date}</span>
                </li>
              ))}
            </ul>
          </Panel>

          <Panel title="Current Blockers" bodyClassName="">
            {(event.blockers ?? []).length === 0 ? (
              <p className="px-3 py-3 text-[12.5px] text-muted-foreground">No blockers.</p>
            ) : (
              <ul>
                {(event.blockers ?? []).map((blocker) => (
                  <li
                    key={blocker}
                    className="flex items-start gap-2 border-b border-border/70 px-3 py-2 text-[12.5px] last:border-0"
                  >
                    <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-critical" />
                    {blocker}
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
      </div>
    </>
  );
}
