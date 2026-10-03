import { useMemo, useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, LoaderCircle, RotateCcw, Search } from "lucide-react";
import { fetchTasks, updateTaskStatus, type TaskRecord, type TaskStatus } from "@/lib/api";
import { Chip, PriorityBadge } from "@/components/dashboard/badges";
import { FilterTabs, PageHeader } from "@/components/dashboard/page-header";
import { GuidancePanel } from "@/components/dashboard/guidance-panel";

export const Route = createFileRoute("/tasks")({
  head: () => ({
    meta: [
      { title: "VP Task Board — ColorStack AI" },
      {
        name: "description",
        content: "A Jira-style advisory board for ColorStack VP priorities and gaps.",
      },
    ],
  }),
  component: TasksPage,
});

const filters = [
  { label: "Mine", value: "mine" },
  { label: "All", value: "all" },
  { label: "High Priority", value: "high" },
  { label: "Waiting", value: "waiting" },
] as const;

const columns: Array<{ status: TaskStatus; label: string; hint: string }> = [
  { status: "open", label: "To do", hint: "Ready to pick up" },
  { status: "in_progress", label: "In progress", hint: "Work underway" },
  { status: "waiting", label: "Waiting", hint: "Needs an unblock" },
  { status: "complete", label: "Done", hint: "Recorded complete" },
];

type Filter = (typeof filters)[number]["value"];

function markerTone(marker: string): "critical" | "warning" | "info" | "neutral" {
  if (marker === "Overdue" || marker === "Blocked") return "critical";
  if (marker === "No owner" || marker === "No deadline") return "warning";
  if (marker === "Due soon") return "info";
  return "neutral";
}

function TaskCard({
  task,
  busy,
  onToggleComplete,
}: {
  task: TaskRecord;
  busy: boolean;
  onToggleComplete: (task: TaskRecord) => void;
}) {
  const complete = task.status === "complete";
  return (
    <article className="rounded-md border border-border bg-panel p-3 shadow-[0_1px_1px_oklch(0.21_0.008_264.7/3%)]">
      <div className="flex items-start justify-between gap-2">
        <p className="text-[13px] font-semibold leading-snug">{task.task}</p>
        <PriorityBadge priority={task.priority} />
      </div>
      {task.eventId ? (
        <Link
          to="/events/$eventId"
          params={{ eventId: task.eventId }}
          className="mt-1 block truncate text-[11.5px] text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
        >
          {task.event}
        </Link>
      ) : (
        <p className="mt-1 text-[11.5px] text-muted-foreground">No linked event</p>
      )}
      <dl className="mt-3 grid grid-cols-2 gap-2 border-t border-border pt-2 text-[11.5px]">
        <div>
          <dt className="text-muted-foreground">Owner</dt>
          <dd className="truncate font-medium">{task.owner}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Due</dt>
          <dd className="font-medium">{task.deadline}</dd>
        </div>
      </dl>
      {task.markers.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {task.markers.map((marker) => (
            <Chip key={marker} variant={markerTone(marker)}>
              {marker}
            </Chip>
          ))}
        </div>
      )}
      <p className="mt-2 rounded bg-surface px-2 py-1.5 text-[11.5px] leading-relaxed">
        <span className="font-medium">Next:</span> {task.nextStep}
      </p>
      <button
        type="button"
        onClick={() => onToggleComplete(task)}
        disabled={busy}
        className="mt-2 flex w-full items-center justify-center gap-1.5 rounded-md border border-border px-2 py-1.5 text-[11.5px] font-medium transition-colors hover:bg-accent disabled:cursor-wait disabled:opacity-60"
      >
        {busy ? (
          <LoaderCircle className="size-3.5 animate-spin" />
        ) : complete ? (
          <RotateCcw className="size-3.5" />
        ) : (
          <Check className="size-3.5" />
        )}
        {complete ? "Reopen task" : "Mark complete"}
      </button>
      {task.manuallyUpdated && (
        <p className="mt-1.5 text-center text-[10.5px] text-muted-foreground">
          Status set manually in this workspace
        </p>
      )}
    </article>
  );
}

function TasksPage() {
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<Filter>("mine");
  const [query, setQuery] = useState("");
  const {
    data: tasks = [],
    isPending,
    error,
  } = useQuery({
    queryKey: ["tasks"],
    queryFn: fetchTasks,
    refetchInterval: 30_000,
  });
  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: TaskStatus }) =>
      updateTaskStatus(id, status),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["tasks"] }),
        queryClient.invalidateQueries({ queryKey: ["guidance"] }),
        queryClient.invalidateQueries({ queryKey: ["overview"] }),
      ]);
    },
  });

  const toggleComplete = (task: TaskRecord) => {
    statusMutation.mutate({
      id: task.id,
      status: task.status === "complete" ? "open" : "complete",
    });
  };

  const data = useMemo(
    () =>
      tasks.filter((task) => {
        const matchesFilter =
          filter === "mine"
            ? task.ownerGroup === "mine"
            : filter === "high"
              ? task.priority === "high" || task.priority === "critical"
              : filter === "waiting"
                ? task.status === "waiting"
                : true;
        const q = query.trim().toLowerCase();
        return (
          matchesFilter &&
          (q === "" ||
            [task.task, task.event, task.owner, task.source, ...task.markers]
              .join(" ")
              .toLowerCase()
              .includes(q))
        );
      }),
    [tasks, filter, query],
  );

  if (isPending) return <p className="text-sm text-muted-foreground">Loading task board…</p>;
  if (error) throw error;

  return (
    <div className="space-y-6">
      <PageHeader
        title="VP Task Board"
        subtitle={`${data.filter((task) => task.status !== "complete").length} open · advisory only`}
        actions={
          <>
            <div className="relative">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search tasks or markers"
                className="h-7 w-48 rounded-md border border-border bg-panel pl-8 pr-2 text-[12.5px] outline-none placeholder:text-muted-foreground focus:border-border-strong"
              />
            </div>
            <FilterTabs options={filters} value={filter} onChange={setFilter} />
          </>
        }
      />

      <GuidancePanel compact />

      {statusMutation.error && (
        <p className="rounded-md border border-critical/25 bg-critical-muted px-3 py-2 text-[12px] text-critical-foreground">
          Could not update the task: {statusMutation.error.message}
        </p>
      )}

      <section className="overflow-x-auto pb-2">
        <div className="grid min-w-[1040px] grid-cols-4 gap-3">
          {columns.map((column) => {
            const columnTasks = data.filter((task) => task.status === column.status);
            return (
              <div key={column.status} className="rounded-lg bg-surface p-2">
                <div className="mb-2 flex items-start justify-between px-1 py-1">
                  <div>
                    <h2 className="text-[12px] font-semibold">{column.label}</h2>
                    <p className="text-[10.5px] text-muted-foreground">{column.hint}</p>
                  </div>
                  <span className="rounded-full bg-muted px-2 py-0.5 text-[11px] tabular-nums text-muted-foreground">
                    {columnTasks.length}
                  </span>
                </div>
                <div className="space-y-2">
                  {columnTasks.map((task) => (
                    <TaskCard
                      key={task.id}
                      task={task}
                      busy={statusMutation.isPending && statusMutation.variables?.id === task.id}
                      onToggleComplete={toggleComplete}
                    />
                  ))}
                  {columnTasks.length === 0 && (
                    <p className="rounded-md border border-dashed border-border px-3 py-8 text-center text-[11.5px] text-muted-foreground">
                      No tasks
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
