import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import { fetchOverview } from "@/lib/api";
import { PriorityBadge } from "@/components/dashboard/badges";
import { GuidancePanel } from "@/components/dashboard/guidance-panel";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Overview — ColorStack AI" },
      {
        name: "description",
        content: "What ColorStack execs need to know and do today.",
      },
      { property: "og:title", content: "Overview — ColorStack AI" },
      { property: "og:description", content: "What ColorStack execs need to know and do today." },
    ],
  }),
  component: Overview,
});

function SectionTitle({
  children,
  to,
}: {
  children: string;
  to?: "/tasks" | "/events" | "/activity";
}) {
  return (
    <div className="mb-2 flex items-baseline justify-between">
      <h2 className="text-[13px] font-semibold">{children}</h2>
      {to && (
        <Link
          to={to}
          className="flex items-center gap-1 text-[12px] text-muted-foreground hover:text-foreground"
        >
          View all <ArrowRight className="size-3" />
        </Link>
      )}
    </div>
  );
}

function readinessTone(v: number) {
  return v >= 80
    ? "text-success-foreground"
    : v >= 65
      ? "text-info-foreground"
      : "text-warning-foreground";
}

function Overview() {
  const { data, isPending, error } = useQuery({ queryKey: ["overview"], queryFn: fetchOverview });
  if (isPending)
    return <p className="text-sm text-muted-foreground">Loading operational context…</p>;
  if (error) throw error;
  const active = data.events.filter((event) => event.phase === "upcoming");
  const date = new Date(data.generatedAt).toLocaleDateString(undefined, {
    weekday: "long",
    month: "short",
    day: "numeric",
  });

  return (
    <div className="mx-auto max-w-5xl space-y-9 py-2">
      <div>
        <h1 className="text-[17px] font-semibold tracking-[-0.01em]">Today</h1>
        <p className="text-[12.5px] text-muted-foreground">
          {date} · what execs need to know and do
        </p>
      </div>

      <section>
        <SectionTitle to="/tasks">Today's Priorities</SectionTitle>
        <ol className="panel-shell divide-y divide-border">
          {data.priorities.map((p, i) => (
            <li key={p.id} className="flex items-center gap-4 px-4 py-3">
              <span className="w-3 text-[12px] font-semibold tabular-nums text-muted-foreground">
                {i + 1}
              </span>
              <span className="min-w-0 flex-1 text-[13.5px] font-medium">{p.title}</span>
              <span className="hidden w-32 text-[12px] text-muted-foreground sm:block">
                {p.owner}
              </span>
              <span className="w-20 text-[12px] text-muted-foreground">{p.due}</span>
              <PriorityBadge priority={p.priority} />
            </li>
          ))}
        </ol>
      </section>

      <GuidancePanel compact />

      <div className="grid gap-9 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <section>
          <SectionTitle to="/events">Active Events</SectionTitle>
          <ul className="divide-y divide-border">
            {active.map((e) => (
              <li key={e.id}>
                <Link
                  to="/events/$eventId"
                  params={{ eventId: e.id }}
                  className="row-hover -mx-2 block rounded-md px-2 py-3"
                >
                  <div className="flex items-baseline justify-between gap-3">
                    <span className="text-[13.5px] font-medium">{e.name}</span>
                    <span className="text-[12px] text-muted-foreground">
                      <span className={cn("font-medium", readinessTone(e.readiness))}>
                        {e.readiness}% ready
                      </span>
                      {" · "}
                      {e.urgency.charAt(0).toUpperCase() + e.urgency.slice(1)}
                    </span>
                  </div>
                  <p className="mt-1 text-[12.5px] text-muted-foreground">
                    Blocker: <span className="text-foreground">{e.blocker}</span>
                  </p>
                  <p className="text-[12.5px] text-muted-foreground">
                    Next: <span className="text-foreground">{e.nextAction}</span>
                  </p>
                </Link>
              </li>
            ))}
          </ul>
        </section>

        <div className="space-y-9">
          <section>
            <SectionTitle>Needs Attention</SectionTitle>
            <ul className="space-y-2.5">
              {data.attention.map((a) => (
                <li key={a.issue} className="flex gap-2.5">
                  <span
                    className={cn(
                      "mt-1.5 size-1.5 shrink-0 rounded-full",
                      a.tone === "critical" ? "bg-critical" : "bg-warning",
                    )}
                  />
                  <div>
                    <p className="text-[12.5px] font-medium leading-tight">{a.issue}</p>
                    <p className="text-[11.5px] text-muted-foreground">{a.event}</p>
                  </div>
                </li>
              ))}
            </ul>
          </section>

          <section>
            <SectionTitle to="/activity">Recent Changes</SectionTitle>
            <ul className="space-y-1.5">
              {data.changes.map((c) => (
                <li
                  key={c.change}
                  className="flex items-baseline justify-between gap-3 text-[12.5px]"
                >
                  <span>
                    {c.change} <span className="text-muted-foreground">— {c.event}</span>
                  </span>
                  <span className="shrink-0 text-[11px] text-muted-foreground">{c.time}</span>
                </li>
              ))}
            </ul>
          </section>
        </div>
      </div>
    </div>
  );
}
