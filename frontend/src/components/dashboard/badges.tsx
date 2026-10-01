import { cn } from "@/lib/utils";
import type { ReqStatus, TaskStatus, Urgency } from "@/lib/api";

const tone = {
  critical: "bg-critical-muted text-critical-foreground border-critical/25",
  warning: "bg-warning-muted text-warning-foreground border-warning/30",
  success: "bg-success-muted text-success-foreground border-success/25",
  info: "bg-info-muted text-info-foreground border-info/25",
  neutral: "bg-muted text-muted-foreground border-border",
} as const;

type Tone = keyof typeof tone;

export function Chip({
  children,
  variant = "neutral",
  className,
  dot = false,
}: {
  children: React.ReactNode;
  variant?: Tone;
  className?: string;
  dot?: boolean;
}) {
  const dotTone: Record<Tone, string> = {
    critical: "bg-critical",
    warning: "bg-warning",
    success: "bg-success",
    info: "bg-info",
    neutral: "bg-muted-foreground",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded border px-1.5 py-0.5 text-[11px] font-medium leading-4 whitespace-nowrap",
        tone[variant],
        className,
      )}
    >
      {dot && <span className={cn("size-1.5 rounded-full", dotTone[variant])} />}
      {children}
    </span>
  );
}

const urgencyTone: Record<Urgency, Tone> = {
  critical: "critical",
  high: "warning",
  medium: "info",
  low: "neutral",
};

const urgencyLabel: Record<Urgency, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
};

export function PriorityBadge({ priority }: { priority: Urgency }) {
  return (
    <Chip variant={urgencyTone[priority]} dot>
      {urgencyLabel[priority]}
    </Chip>
  );
}

const reqTone: Record<ReqStatus, Tone> = {
  complete: "success",
  in_progress: "info",
  missing: "critical",
  blocked: "critical",
  unknown: "neutral",
  not_applicable: "neutral",
};

const reqLabel: Record<ReqStatus, string> = {
  complete: "Complete",
  in_progress: "In Progress",
  missing: "Missing",
  blocked: "Blocked",
  unknown: "Unknown",
  not_applicable: "Not Applicable",
};

export function StatusBadge({ status }: { status: ReqStatus }) {
  return <Chip variant={reqTone[status]}>{reqLabel[status]}</Chip>;
}

const taskTone: Record<TaskStatus, Tone> = {
  open: "neutral",
  in_progress: "info",
  waiting: "warning",
  complete: "success",
};

const taskLabel: Record<TaskStatus, string> = {
  open: "Open",
  in_progress: "In Progress",
  waiting: "Waiting",
  complete: "Complete",
};

export function TaskStatusBadge({ status }: { status: TaskStatus }) {
  return <Chip variant={taskTone[status]}>{taskLabel[status]}</Chip>;
}

export function ReadinessBar({ value, className }: { value: number; className?: string }) {
  const barTone =
    value >= 80
      ? "bg-success"
      : value >= 65
        ? "bg-info"
        : value >= 50
          ? "bg-warning"
          : "bg-critical";
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-border">
        <div className={cn("h-full rounded-full", barTone)} style={{ width: `${value}%` }} />
      </div>
      <span className="w-8 text-xs font-medium tabular-nums text-muted-foreground">{value}%</span>
    </div>
  );
}
