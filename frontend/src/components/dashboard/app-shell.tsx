import { useState, type ReactNode } from "react";
import { Menu, Search, X } from "lucide-react";
import { AppSidebar } from "./app-sidebar";

export function AppShell({ children }: { children: ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex min-h-screen w-full bg-background text-foreground">
      <aside className="sticky top-0 hidden h-screen shrink-0 lg:block">
        <AppSidebar />
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            aria-label="Close navigation"
            onClick={() => setMobileOpen(false)}
            className="absolute inset-0 bg-foreground/25"
          />
          <div className="absolute left-0 top-0 h-full">
            <AppSidebar onNavigate={() => setMobileOpen(false)} />
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-11 items-center gap-3 border-b border-border bg-panel/90 px-3 backdrop-blur lg:px-5">
          <button
            type="button"
            onClick={() => setMobileOpen((open) => !open)}
            className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground lg:hidden"
            aria-label="Toggle navigation"
          >
            {mobileOpen ? <X className="size-4" /> : <Menu className="size-4" />}
          </button>
          <div className="relative w-full max-w-sm">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
            <input
              placeholder="Search events, tasks, people…"
              className="h-7 w-full rounded-md border border-border bg-surface pl-8 pr-2 text-[12.5px] outline-none placeholder:text-muted-foreground focus:border-border-strong"
            />
          </div>
          <div className="ml-auto flex items-center gap-2 text-[11.5px] text-muted-foreground">
            <span className="hidden sm:inline">Oct 1, 2026</span>
            <span className="flex size-6 items-center justify-center rounded-full bg-primary text-[10px] font-semibold text-primary-foreground">
              SA
            </span>
          </div>
        </header>

        <main className="min-w-0 flex-1 space-y-4 p-3 lg:p-5">{children}</main>
      </div>
    </div>
  );
}
