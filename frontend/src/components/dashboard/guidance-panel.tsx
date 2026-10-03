import { useQuery } from "@tanstack/react-query";
import { AlertCircle, ArrowRight, CircleHelp, Lightbulb } from "lucide-react";
import { fetchGuidance, type GuidanceMarker } from "@/lib/api";
import { PriorityBadge } from "./badges";

const sections = [
  { key: "doNow", label: "Do now", icon: ArrowRight },
  { key: "missing", label: "Missing", icon: AlertCircle },
  { key: "improve", label: "Improve", icon: Lightbulb },
] as const;

function MarkerCard({ marker }: { marker: GuidanceMarker }) {
  return (
    <article className="rounded-md border border-border bg-panel p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[13px] font-semibold leading-snug">{marker.title}</p>
          {marker.event && (
            <p className="mt-0.5 truncate text-[11px] text-muted-foreground">{marker.event}</p>
          )}
        </div>
        <PriorityBadge priority={marker.urgency} />
      </div>
      <p className="mt-2 text-[12px] leading-relaxed text-muted-foreground">{marker.reason}</p>
      <p className="mt-2 text-[12px] leading-relaxed">
        <span className="font-medium">Your next move:</span> {marker.recommendation}
      </p>
      <p className="mt-2 flex gap-1.5 border-t border-border pt-2 text-[11.5px] text-info-foreground">
        <CircleHelp className="mt-0.5 size-3 shrink-0" />
        <span>{marker.question}</span>
      </p>
    </article>
  );
}

export function GuidancePanel({ compact = false }: { compact?: boolean }) {
  const { data, isPending, error } = useQuery({
    queryKey: ["guidance"],
    queryFn: fetchGuidance,
    refetchInterval: 30_000,
  });

  if (isPending) {
    return <p className="text-sm text-muted-foreground">Checking priorities and gaps…</p>;
  }
  if (error) throw error;
  const coverageLabel = `Knowledge coverage: ${data.coverage.reviewedPercent}% · ${data.coverage.structuredFacts} facts`;

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="text-[14px] font-semibold">VP guidance</h2>
          <p className="text-[11.5px] text-muted-foreground">
            Recommended decisions only · nothing is changed automatically
          </p>
        </div>
        <p className="text-[11.5px] text-muted-foreground">{coverageLabel}</p>
      </div>
      <div className="grid gap-3 lg:grid-cols-3">
        {sections.map(({ key, label, icon: Icon }) => {
          const items = data[key];
          return (
            <div key={key} className="rounded-lg bg-surface p-2">
              <div className="mb-2 flex items-center justify-between px-1">
                <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                  <Icon className="size-3.5" /> {label}
                </p>
                <span className="text-[11px] tabular-nums text-muted-foreground">
                  {items.length}
                </span>
              </div>
              <div className="space-y-2">
                {items.slice(0, compact ? 2 : 5).map((item) => (
                  <MarkerCard key={item.id} marker={item} />
                ))}
                {items.length === 0 && (
                  <p className="rounded-md border border-dashed border-border px-3 py-5 text-center text-[12px] text-muted-foreground">
                    Nothing detected
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
