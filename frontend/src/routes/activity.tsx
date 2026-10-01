import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { fetchActivity } from "@/lib/api";
import { FilterTabs, PageHeader, Panel } from "@/components/dashboard/page-header";
import { ActivityFeed } from "@/components/dashboard/activity-feed";

export const Route = createFileRoute("/activity")({
  head: () => ({
    meta: [
      { title: "Activity — ColorStack AI" },
      {
        name: "description",
        content:
          "Chronological feed of detected changes, missing requirements, and owner assignments.",
      },
      { property: "og:title", content: "Activity — ColorStack AI" },
      {
        property: "og:description",
        content:
          "Chronological feed of detected changes, missing requirements, and owner assignments.",
      },
    ],
  }),
  component: ActivityPage,
});

const filters = [
  { label: "All", value: "all" },
  { label: "Changes", value: "change" },
  { label: "Detections", value: "detection" },
  { label: "Assignments", value: "assignment" },
] as const;

type Filter = (typeof filters)[number]["value"];

function ActivityPage() {
  const [filter, setFilter] = useState<Filter>("all");
  const {
    data: activity = [],
    isPending,
    error,
  } = useQuery({ queryKey: ["activity"], queryFn: fetchActivity });
  const data = useMemo(
    () => (filter === "all" ? activity : activity.filter((item) => item.kind === filter)),
    [activity, filter],
  );
  if (isPending) return <p className="text-sm text-muted-foreground">Loading activity…</p>;
  if (error) throw error;

  return (
    <>
      <PageHeader
        title="Activity"
        subtitle={`${data.length} entries · last 48 hours`}
        actions={<FilterTabs options={filters} value={filter} onChange={setFilter} />}
      />
      <Panel bodyClassName="">
        <ActivityFeed data={data} />
      </Panel>
    </>
  );
}
