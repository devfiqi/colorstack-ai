import { Link, useRouterState } from "@tanstack/react-router";
import {
  Activity,
  CalendarDays,
  Database,
  Cpu,
  LayoutDashboard,
  ListChecks,
  MessageSquareText,
  Settings,
  FileText,
  Users,
} from "lucide-react";
import { cn } from "@/lib/utils";

const primary = [
  { label: "Overview", to: "/", icon: LayoutDashboard },
  { label: "Events", to: "/events", icon: CalendarDays },
  { label: "Tasks", to: "/tasks", icon: ListChecks },
  { label: "Ask AI", to: "/ask", icon: MessageSquareText },
  { label: "Brief", to: "/brief", icon: FileText },
  { label: "Activity", to: "/activity", icon: Activity },
] as const;

const secondary = [
  { label: "People", to: "/people", icon: Users },
  { label: "Settings", to: "/settings", icon: Settings },
] as const;

const statuses = [
  { label: "System", value: "Operational", icon: Activity, tone: "bg-success" },
  { label: "Local AI", value: "Ready · llama3", icon: Cpu, tone: "bg-success" },
  { label: "Database", value: "PostgreSQL", icon: Database, tone: "bg-success" },
];

export function AppSidebar({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  const isActive = (to: string) => (to === "/" ? pathname === "/" : pathname.startsWith(to));

  const item = (entry: { label: string; to: string; icon: typeof Activity }) => {
    const active = isActive(entry.to);
    return (
      <Link
        key={entry.to}
        to={entry.to}
        onClick={onNavigate}
        className={cn(
          "flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm transition-colors",
          active
            ? "bg-primary text-primary-foreground font-medium"
            : "text-muted-foreground hover:bg-accent hover:text-foreground",
        )}
      >
        <entry.icon className="size-4 shrink-0" />
        <span className="truncate">{entry.label}</span>
      </Link>
    );
  };

  return (
    <div className="flex h-full w-60 flex-col border-r border-border bg-sidebar">
      <div className="flex items-center gap-2.5 px-4 py-3.5">
        <div className="flex size-7 items-center justify-center rounded bg-primary text-[11px] font-bold text-primary-foreground">
          CS
        </div>
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold leading-tight">ColorStack AI</p>
          <p className="truncate text-[11px] text-muted-foreground">UMN Chapter · Exec Ops</p>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto px-2 pb-2">
        <div className="space-y-0.5">{primary.map(item)}</div>
        <p className="px-2.5 pb-1 pt-4 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          More
        </p>
        <div className="space-y-0.5">{secondary.map(item)}</div>
      </nav>

      <div className="space-y-1 px-4 py-3 opacity-70">
        {statuses.map((s) => (
          <div key={s.label} className="flex items-center justify-between text-[10.5px]">
            <span className="flex items-center gap-1.5 text-muted-foreground">
              <span className={cn("size-1 rounded-full", s.tone)} />
              {s.label}
            </span>
            <span className="text-muted-foreground">{s.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
