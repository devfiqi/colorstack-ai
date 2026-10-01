import { useNavigate } from "@tanstack/react-router";
import { ChevronRight } from "lucide-react";
import type { EventRecord } from "@/lib/api";
import { PriorityBadge, ReadinessBar } from "./badges";
import { EmptyState } from "./page-header";

export function EventTable({ data }: { data: EventRecord[] }) {
  const navigate = useNavigate();

  if (data.length === 0) {
    return (
      <EmptyState
        message="No events match these filters"
        hint="Try a different tab or clear the search."
      />
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[900px] text-left text-[12.5px]">
        <thead>
          <tr className="border-b border-border text-[11px] uppercase tracking-wide text-muted-foreground">
            <th className="px-3 py-2 font-medium">Event</th>
            <th className="px-3 py-2 font-medium">Date</th>
            <th className="px-3 py-2 font-medium">Type</th>
            <th className="px-3 py-2 font-medium">Readiness</th>
            <th className="px-3 py-2 font-medium">Urgency</th>
            <th className="px-3 py-2 font-medium">Owner</th>
            <th className="px-3 py-2 font-medium">Main Blocker</th>
            <th className="px-3 py-2 font-medium">Next Action</th>
            <th className="w-8 px-3 py-2" />
          </tr>
        </thead>
        <tbody>
          {data.map((event) => (
            <tr
              key={event.id}
              onClick={() => navigate({ to: "/events/$eventId", params: { eventId: event.id } })}
              className="row-hover cursor-pointer border-b border-border/70 last:border-0"
            >
              <td className="px-3 py-2 font-medium">{event.name}</td>
              <td className="px-3 py-2 text-muted-foreground">{event.date}</td>
              <td className="px-3 py-2 text-muted-foreground">{event.type}</td>
              <td className="px-3 py-2">
                <ReadinessBar value={event.readiness} />
              </td>
              <td className="px-3 py-2">
                <PriorityBadge priority={event.urgency} />
              </td>
              <td className="px-3 py-2 text-muted-foreground">{event.owner}</td>
              <td className="px-3 py-2 text-muted-foreground">{event.blocker}</td>
              <td className="px-3 py-2">{event.nextAction}</td>
              <td className="px-3 py-2 text-muted-foreground">
                <ChevronRight className="size-4" />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
