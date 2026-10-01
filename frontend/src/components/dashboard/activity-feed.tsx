import { AlertTriangle, ArrowRightLeft, UserPlus } from "lucide-react";
import type { ActivityRecord } from "@/lib/api";
import { EmptyState } from "./page-header";

const icons = {
  change: ArrowRightLeft,
  detection: AlertTriangle,
  assignment: UserPlus,
} as const;

const iconTone = {
  change: "text-info",
  detection: "text-critical",
  assignment: "text-success",
} as const;

export function ActivityFeed({ data }: { data: ActivityRecord[] }) {
  if (data.length === 0) {
    return (
      <EmptyState
        message="No activity recorded"
        hint="Changes will appear here as they are detected."
      />
    );
  }

  const days = Array.from(new Set(data.map((item) => item.day)));

  return (
    <div>
      {days.map((day) => (
        <div key={day}>
          <p className="border-b border-border bg-surface px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
            {day}
          </p>
          <ul>
            {data
              .filter((item) => item.day === day)
              .map((item) => {
                const Icon = icons[item.kind];
                return (
                  <li
                    key={item.id}
                    className="row-hover flex items-start gap-3 border-b border-border/70 px-3 py-2 last:border-0"
                  >
                    <span className="w-16 shrink-0 pt-0.5 text-[11.5px] tabular-nums text-muted-foreground">
                      {item.time}
                    </span>
                    <Icon className={`mt-0.5 size-3.5 shrink-0 ${iconTone[item.kind]}`} />
                    <div className="min-w-0">
                      <p className="text-[12.5px] leading-snug">{item.message}</p>
                      <p className="text-[11.5px] text-muted-foreground">{item.event}</p>
                    </div>
                  </li>
                );
              })}
          </ul>
        </div>
      ))}
    </div>
  );
}
