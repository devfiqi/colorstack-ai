import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { fetchEvents } from "@/lib/api";
import { FilterTabs, PageHeader, Panel } from "@/components/dashboard/page-header";
import { EventTable } from "@/components/dashboard/event-table";

export const Route = createFileRoute("/events/")({
  head: () => ({
    meta: [
      { title: "Events — ColorStack AI" },
      {
        name: "description",
        content:
          "Every ColorStack event with readiness, urgency, owners, blockers, and next actions.",
      },
      { property: "og:title", content: "Events — ColorStack AI" },
      {
        property: "og:description",
        content:
          "Every ColorStack event with readiness, urgency, owners, blockers, and next actions.",
      },
    ],
  }),
  component: EventsPage,
});

const filters = [
  { label: "All", value: "all" },
  { label: "High Priority", value: "high" },
  { label: "Upcoming", value: "upcoming" },
  { label: "Completed", value: "completed" },
] as const;

type Filter = (typeof filters)[number]["value"];

function EventsPage() {
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const {
    data: events = [],
    isPending,
    error,
  } = useQuery({ queryKey: ["events"], queryFn: fetchEvents });

  const data = useMemo(() => {
    return events.filter((event) => {
      const matchesFilter =
        filter === "all"
          ? true
          : filter === "high"
            ? event.urgency === "high" || event.urgency === "critical"
            : filter === "upcoming"
              ? event.phase === "upcoming"
              : event.phase === "completed";

      const q = query.trim().toLowerCase();
      const matchesQuery =
        q === "" ||
        [event.name, event.type, event.owner, event.blocker, event.nextAction]
          .join(" ")
          .toLowerCase()
          .includes(q);

      return matchesFilter && matchesQuery;
    });
  }, [events, filter, query]);

  if (isPending) return <p className="text-sm text-muted-foreground">Loading events…</p>;
  if (error) throw error;

  return (
    <>
      <PageHeader
        title="Events"
        subtitle={`${data.length} of ${events.length} events shown`}
        actions={
          <>
            <div className="relative">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search events"
                className="h-7 w-48 rounded-md border border-border bg-panel pl-8 pr-2 text-[12.5px] outline-none placeholder:text-muted-foreground focus:border-border-strong"
              />
            </div>
            <FilterTabs options={filters} value={filter} onChange={setFilter} />
          </>
        }
      />

      <Panel bodyClassName="">
        <EventTable data={data} />
      </Panel>
    </>
  );
}
