import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, Download } from "lucide-react";
import { fetchLatestBrief } from "@/lib/api";
import { PageHeader, Panel } from "@/components/dashboard/page-header";

export const Route = createFileRoute("/brief")({
  head: () => ({
    meta: [
      { title: "Daily Brief — ColorStack AI" },
      {
        name: "description",
        content:
          "Executive daily brief: critical attention, event updates, blockers, and today's top 3.",
      },
      { property: "og:title", content: "Daily Brief — ColorStack AI" },
      {
        property: "og:description",
        content:
          "Executive daily brief: critical attention, event updates, blockers, and today's top 3.",
      },
    ],
  }),
  component: BriefPage,
});

function List({ items, tone }: { items: string[]; tone?: "critical" | "warning" | "info" }) {
  const dot =
    tone === "critical"
      ? "bg-critical"
      : tone === "warning"
        ? "bg-warning"
        : tone === "info"
          ? "bg-info"
          : "bg-muted-foreground";
  return (
    <ul className="space-y-1.5">
      {items.map((item) => (
        <li key={item} className="flex items-start gap-2 text-[12.5px] leading-snug">
          <span className={`mt-1.5 size-1.5 shrink-0 rounded-full ${dot}`} />
          {item}
        </li>
      ))}
    </ul>
  );
}

function BriefPage() {
  const [collapsed, setCollapsed] = useState<string[]>([]);
  const {
    data: brief,
    isPending,
    error,
  } = useQuery({ queryKey: ["brief"], queryFn: fetchLatestBrief });
  const toggle = (name: string) =>
    setCollapsed((prev) =>
      prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name],
    );

  if (isPending) return <p className="text-sm text-muted-foreground">Loading latest brief…</p>;
  if (error) throw error;

  return (
    <>
      <PageHeader
        title="Daily Brief"
        subtitle={`Generated ${brief.generated} · covers 4 active events`}
        actions={
          <button className="flex h-7 items-center gap-1.5 rounded-md border border-border bg-panel px-2.5 text-[12px] font-medium transition-colors hover:bg-accent">
            <Download className="size-3.5" /> Export
          </button>
        }
      />

      <div className="grid gap-3 lg:grid-cols-2">
        <Panel title="Critical Attention">
          <List items={brief.critical} tone="critical" />
        </Panel>
        <Panel title="Today's Top 3">
          <ol className="space-y-1.5">
            {brief.topThree.map((item, i) => (
              <li key={item} className="flex items-start gap-2 text-[12.5px] leading-snug">
                <span className="w-3 shrink-0 font-semibold tabular-nums text-muted-foreground">
                  {i + 1}
                </span>
                {item}
              </li>
            ))}
          </ol>
        </Panel>
        <Panel title="Waiting on Others">
          <List items={brief.waiting} tone="warning" />
        </Panel>
        <Panel title="Missing Requirements">
          <List items={brief.missing} tone="info" />
        </Panel>
      </div>

      <Panel
        title="Event Updates"
        description="Collapse sections you have already reviewed"
        bodyClassName=""
      >
        {brief.sections.map((section) => {
          const isCollapsed = collapsed.includes(section.event);
          return (
            <div key={section.event} className="border-b border-border last:border-0">
              <button
                type="button"
                onClick={() => toggle(section.event)}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-[13px] font-semibold transition-colors hover:bg-accent"
              >
                {isCollapsed ? (
                  <ChevronRight className="size-3.5" />
                ) : (
                  <ChevronDown className="size-3.5" />
                )}
                {section.event}
                <span className="ml-auto text-[11.5px] font-normal text-muted-foreground">
                  {section.unresolved.length} unresolved
                </span>
              </button>
              {!isCollapsed && (
                <div className="grid gap-4 bg-surface px-9 py-3 md:grid-cols-3">
                  <div>
                    <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                      What changed
                    </p>
                    <List items={section.changed} tone="info" />
                  </div>
                  <div>
                    <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                      Unresolved
                    </p>
                    <List items={section.unresolved} tone="critical" />
                  </div>
                  <div>
                    <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                      Next steps
                    </p>
                    <ol className="space-y-1.5">
                      {section.nextSteps.map((step, i) => (
                        <li
                          key={step}
                          className="flex items-start gap-2 text-[12.5px] leading-snug"
                        >
                          <span className="w-3 shrink-0 tabular-nums text-muted-foreground">
                            {i + 1}
                          </span>
                          {step}
                        </li>
                      ))}
                    </ol>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </Panel>
    </>
  );
}
