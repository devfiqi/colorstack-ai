import { Link } from "@tanstack/react-router";
import type { TaskRecord } from "@/lib/api";
import { Chip, PriorityBadge, TaskStatusBadge } from "./badges";
import { EmptyState } from "./page-header";

export function TaskTable({ data, compact = false }: { data: TaskRecord[]; compact?: boolean }) {
  if (data.length === 0) {
    return <EmptyState message="No tasks here" hint="Nothing is assigned under this filter." />;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[820px] text-left text-[12.5px]">
        <thead>
          <tr className="border-b border-border text-[11px] uppercase tracking-wide text-muted-foreground">
            <th className="px-3 py-2 font-medium">Task</th>
            <th className="px-3 py-2 font-medium">Event</th>
            <th className="px-3 py-2 font-medium">Owner</th>
            <th className="px-3 py-2 font-medium">Status</th>
            <th className="px-3 py-2 font-medium">Priority</th>
            <th className="px-3 py-2 font-medium">Deadline</th>
            {!compact && <th className="px-3 py-2 font-medium">Source</th>}
          </tr>
        </thead>
        <tbody>
          {data.map((task) => (
            <tr key={task.id} className="row-hover border-b border-border/70 last:border-0">
              <td className="px-3 py-2 font-medium">{task.task}</td>
              <td className="px-3 py-2 text-muted-foreground">
                {task.eventId ? (
                  <Link
                    to="/events/$eventId"
                    params={{ eventId: task.eventId }}
                    className="underline-offset-2 hover:text-foreground hover:underline"
                  >
                    {task.event}
                  </Link>
                ) : (
                  task.event
                )}
              </td>
              <td className="px-3 py-2 text-muted-foreground">{task.owner}</td>
              <td className="px-3 py-2">
                <TaskStatusBadge status={task.status} />
              </td>
              <td className="px-3 py-2">
                <PriorityBadge priority={task.priority} />
              </td>
              <td className="px-3 py-2 text-muted-foreground">{task.deadline}</td>
              {!compact && (
                <td className="px-3 py-2">
                  <Chip>{task.source}</Chip>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
