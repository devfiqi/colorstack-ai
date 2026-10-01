export type Urgency = "critical" | "high" | "medium" | "low";
export type ReqStatus =
  "complete" | "in_progress" | "missing" | "blocked" | "unknown" | "not_applicable";
export type TaskStatus = "open" | "in_progress" | "waiting" | "complete";

export interface Requirement {
  id: string;
  label: string;
  group: string;
  status: ReqStatus;
  owner: string;
  urgency: Urgency;
  source: string;
  detail: string;
}

export interface EventRecord {
  id: string;
  name: string;
  date: string;
  type: string;
  phase: "upcoming" | "completed";
  readiness: number;
  urgency: Urgency;
  owner: string;
  blocker: string;
  nextAction: string;
  sponsor?: string | null;
  assessment?: string;
  requirements?: Requirement[];
  owners?: Array<{ name: string; scope: string }>;
  keyDates?: Array<{ label: string; date: string }>;
  blockers?: string[];
  recentChanges?: Array<{ id: string; field: string; message: string; time: string }>;
}

export interface TaskRecord {
  id: string;
  task: string;
  eventId: string | null;
  event: string;
  owner: string;
  ownerGroup: "mine" | "execs";
  status: TaskStatus;
  priority: Urgency;
  deadline: string;
  source: string;
}

export interface ActivityRecord {
  id: string;
  time: string;
  day: string;
  event: string;
  kind: "change" | "detection" | "assignment";
  message: string;
}

export interface Person {
  id: string;
  name: string;
  role: string;
  activeTasks: number;
  ownedEvents: string[];
  unresolved: string[];
  tasks: TaskRecord[];
}

export interface Playbook {
  id: string;
  name: string;
  required: string[];
  optional: string[];
  leadTime: string;
}

export interface Priority {
  id: string;
  title: string;
  owner: string;
  due: string;
  priority: Urgency;
  context: string;
}

export interface Overview {
  generatedAt: string;
  activeEvents: number;
  highPriority: number;
  openTasks: number;
  deadlinesThisWeek: number;
  priorities: Priority[];
  events: EventRecord[];
  attention: Array<{ event: string; issue: string; tone: string }>;
  changes: Array<{ change: string; event: string; time: string }>;
}

export interface BriefView {
  generated: string;
  critical: string[];
  topThree: string[];
  waiting: string[];
  missing: string[];
  sections: Array<{
    event: string;
    changed: string[];
    unresolved: string[];
    nextSteps: string[];
  }>;
}

export interface SystemStatus {
  database: string;
  discord: string;
  extraction: string;
  reasoning: string;
  dailyBriefEnabled: boolean;
  dailyBriefSchedule: string;
}

const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { headers: { Accept: "application/json" } });
  if (!response.ok) {
    throw new Error(`API request failed (${response.status}): ${path}`);
  }
  return response.json() as Promise<T>;
}

export const fetchOverview = () => request<Overview>("/api/overview");
export const fetchEvents = () => request<EventRecord[]>("/api/events");
export const fetchEvent = (id: string) => request<EventRecord>(`/api/events/${id}`);
export const fetchTasks = () => request<TaskRecord[]>("/api/tasks");
export const fetchPeople = () => request<Person[]>("/api/people");
export const fetchActivity = () => request<ActivityRecord[]>("/api/activity");
export const fetchPlaybooks = () => request<Playbook[]>("/api/playbooks");
export const fetchSystem = () => request<SystemStatus>("/api/system");

interface BriefApiResponse {
  generated: string;
  brief: {
    critical_events: Array<{
      event_name: string;
      updates: string[];
      unresolved: string[];
      next_actions: Array<{ title: string }>;
    }>;
    high_events: Array<{
      event_name: string;
      updates: string[];
      unresolved: string[];
      next_actions: Array<{ title: string }>;
    }>;
    top_priorities: Array<{ title: string }>;
    blockers: string[];
  };
}

export async function fetchLatestBrief(): Promise<BriefView | null> {
  const apiResponse = await fetch(`${API_URL}/api/briefs/latest`, {
    headers: { Accept: "application/json" },
  });
  if (apiResponse.status === 404) return null;
  if (!apiResponse.ok) {
    throw new Error(`API request failed (${apiResponse.status}): /api/briefs/latest`);
  }
  const response = (await apiResponse.json()) as BriefApiResponse;
  const sections = [...response.brief.critical_events, ...response.brief.high_events];
  return {
    generated: new Date(response.generated).toLocaleString(),
    critical: response.brief.critical_events.flatMap((item) => item.unresolved),
    topThree: response.brief.top_priorities.map((item) => item.title),
    waiting: response.brief.blockers,
    missing: sections.flatMap((item) => item.unresolved),
    sections: sections.map((item) => ({
      event: item.event_name,
      changed: item.updates,
      unresolved: item.unresolved,
      nextSteps: item.next_actions.map((action) => action.title),
    })),
  };
}
