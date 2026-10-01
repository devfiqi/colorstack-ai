import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { fetchPeople } from "@/lib/api";
import { PageHeader, Panel } from "@/components/dashboard/page-header";
import { TaskTable } from "@/components/dashboard/task-table";
import { Chip } from "@/components/dashboard/badges";

export const Route = createFileRoute("/people")({
  head: () => ({
    meta: [
      { title: "People — ColorStack AI" },
      {
        name: "description",
        content:
          "Execs and board members with active tasks, owned events, and unresolved commitments.",
      },
      { property: "og:title", content: "People — ColorStack AI" },
      {
        property: "og:description",
        content:
          "Execs and board members with active tasks, owned events, and unresolved commitments.",
      },
    ],
  }),
  component: PeoplePage,
});

function PeoplePage() {
  const [selected, setSelected] = useState<string | null>(null);
  const {
    data: people = [],
    isPending,
    error,
  } = useQuery({ queryKey: ["people"], queryFn: fetchPeople });
  if (isPending) return <p className="text-sm text-muted-foreground">Loading people…</p>;
  if (error) throw error;
  const person = people.find((p) => p.id === selected);

  if (person) {
    const theirTasks = person.tasks;
    return (
      <>
        <button
          type="button"
          onClick={() => setSelected(null)}
          className="inline-flex items-center gap-1.5 text-[12px] text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-3.5" /> People
        </button>
        <PageHeader
          title={person.name}
          subtitle={`${person.role} · ${person.activeTasks} active tasks`}
        />
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_290px]">
          <Panel title="Assigned Tasks" bodyClassName="">
            <TaskTable data={theirTasks} compact />
          </Panel>
          <div className="space-y-4">
            <Panel title="Owned Events" bodyClassName="p-3">
              <div className="flex flex-wrap gap-1.5">
                {person.ownedEvents.length === 0 ? (
                  <p className="text-[12.5px] text-muted-foreground">No owned events.</p>
                ) : (
                  person.ownedEvents.map((event) => <Chip key={event}>{event}</Chip>)
                )}
              </div>
            </Panel>
            <Panel title="Unresolved Commitments" bodyClassName="">
              <ul>
                {person.unresolved.map((item) => (
                  <li
                    key={item}
                    className="flex items-start gap-2 border-b border-border/70 px-3 py-2 text-[12.5px] last:border-0"
                  >
                    <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-warning" />
                    {item}
                  </li>
                ))}
              </ul>
            </Panel>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <PageHeader title="People" subtitle={`${people.length} execs and board members`} />
      <Panel bodyClassName="">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-[12.5px]">
            <thead>
              <tr className="border-b border-border text-[11px] uppercase tracking-wide text-muted-foreground">
                <th className="px-3 py-2 font-medium">Name</th>
                <th className="px-3 py-2 font-medium">Role</th>
                <th className="px-3 py-2 font-medium">Active Tasks</th>
                <th className="px-3 py-2 font-medium">Owned Events</th>
                <th className="px-3 py-2 font-medium">Unresolved</th>
              </tr>
            </thead>
            <tbody>
              {people.map((p) => (
                <tr
                  key={p.id}
                  onClick={() => setSelected(p.id)}
                  className="row-hover cursor-pointer border-b border-border/70 last:border-0"
                >
                  <td className="px-3 py-2 font-medium">{p.name}</td>
                  <td className="px-3 py-2 text-muted-foreground">{p.role}</td>
                  <td className="px-3 py-2 tabular-nums">{p.activeTasks}</td>
                  <td className="px-3 py-2 text-muted-foreground">
                    {p.ownedEvents.join(", ") || "—"}
                  </td>
                  <td className="px-3 py-2 text-muted-foreground">{p.unresolved.length}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </>
  );
}
