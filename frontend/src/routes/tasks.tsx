import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { fetchTasks } from "@/lib/api";
import { FilterTabs, PageHeader, Panel } from "@/components/dashboard/page-header";
import { TaskTable } from "@/components/dashboard/task-table";

export const Route = createFileRoute("/tasks")({
  head: () => ({
    meta: [
      { title: "Tasks — ColorStack AI" },
      {
        name: "description",
        content: "Dense task table for ColorStack execs: owners, status, priority, and deadlines.",
      },
      { property: "og:title", content: "Tasks — ColorStack AI" },
      {
        property: "og:description",
        content: "Dense task table for ColorStack execs: owners, status, priority, and deadlines.",
      },
    ],
  }),
  component: TasksPage,
});

const filters = [
  { label: "Mine", value: "mine" },
  { label: "Execs", value: "execs" },
  { label: "High Priority", value: "high" },
  { label: "Waiting", value: "waiting" },
  { label: "Completed", value: "completed" },
] as const;

type Filter = (typeof filters)[number]["value"];

function TasksPage() {
  const [filter, setFilter] = useState<Filter>("mine");
  const [query, setQuery] = useState("");
  const {
    data: tasks = [],
    isPending,
    error,
  } = useQuery({ queryKey: ["tasks"], queryFn: fetchTasks });

  const data = useMemo(
    () =>
      tasks.filter((task) => {
        const matchesFilter =
          filter === "mine"
            ? task.ownerGroup === "mine"
            : filter === "execs"
              ? task.ownerGroup === "execs"
              : filter === "high"
                ? task.priority === "high" || task.priority === "critical"
                : filter === "waiting"
                  ? task.status === "waiting"
                  : task.status === "complete";

        const q = query.trim().toLowerCase();
        const matchesQuery =
          q === "" ||
          [task.task, task.event, task.owner, task.source].join(" ").toLowerCase().includes(q);

        return matchesFilter && matchesQuery;
      }),
    [tasks, filter, query],
  );

  if (isPending) return <p className="text-sm text-muted-foreground">Loading tasks…</p>;
  if (error) throw error;

  return (
    <>
      <PageHeader
        title="Tasks"
        subtitle={`${data.length} shown · ${tasks.filter((t) => t.status !== "complete").length} open overall`}
        actions={
          <>
            <div className="relative">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search tasks"
                className="h-7 w-44 rounded-md border border-border bg-panel pl-8 pr-2 text-[12.5px] outline-none placeholder:text-muted-foreground focus:border-border-strong"
              />
            </div>
            <FilterTabs options={filters} value={filter} onChange={setFilter} />
          </>
        }
      />

      <Panel bodyClassName="">
        <TaskTable data={data} />
      </Panel>
    </>
  );
}
