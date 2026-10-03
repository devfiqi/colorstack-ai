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
  markers: string[];
  nextStep: string;
  manuallyUpdated: boolean;
}

export interface GuidanceMarker {
  id: string;
  category: "action" | "missing" | "improvement";
  title: string;
  reason: string;
  recommendation: string;
  question: string;
  urgency: Urgency;
  event: string | null;
  taskId: string | null;
}

export interface Guidance {
  generatedAt: string;
  doNow: GuidanceMarker[];
  missing: GuidanceMarker[];
  improve: GuidanceMarker[];
  coverage: {
    archivedMessages: number;
    reviewedMessages: number;
    reviewedPercent: number;
    structuredFacts: number;
  };
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
  taskId: string | null;
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
  pipelineEnabled: boolean;
  pipelineIntervalSeconds: number;
  pipelineStatus: string;
  pipelineLastRunAt: string | null;
  pipelineStages: Array<{ name?: string; succeeded?: boolean; error?: string | null }>;
  advisoryOnly: boolean;
  automaticActions: boolean;
}

export type IntakeSourceType =
  "conversation" | "meeting_notes" | "email" | "document" | "transcript" | "general_note";
export type IntakeStatus = "pending" | "processing" | "processed" | "failed";
export type ProposalStatus = "pending" | "approved" | "rejected";

export interface IntakeFact {
  type: string;
  event_name: string | null;
  task: string | null;
  owner_name: string | null;
  deadline_text: string | null;
  normalized_deadline: string | null;
  status: string | null;
  value: string | null;
  confidence: number;
  evidence_kind: string;
}

export interface IntakeProposal {
  id: string;
  ordinal: number;
  fact: IntakeFact;
  status: ProposalStatus;
  reviewer_note: string | null;
  reviewed_at: string | null;
}

export interface IntakeSourceSummary {
  id: string;
  title: string;
  source_type: IntakeSourceType;
  status: IntakeStatus;
  created_at: string;
  proposal_count: number;
  pending_count: number;
}

export interface IntakeSource extends IntakeSourceSummary {
  content: string;
  occurred_at: string | null;
  error: string | null;
  updated_at: string;
  proposals: IntakeProposal[];
}

export interface AdvisorAnswer {
  request_id: string | null;
  answer: {
    summary: string;
    priorities: Array<{
      title: string;
      reason: string;
      owner_name: string | null;
      urgency: Urgency;
      deadline: string | null;
    }>;
    risks: Array<{ title: string; reason: string; urgency: Urgency }>;
    blockers: string[];
    discussion_topics: string[];
    uncertainty: string[];
  } | null;
  warnings: string[];
  reviewed_intake_count: number;
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
export const fetchGuidance = () => request<Guidance>("/api/guidance");
export const updateTaskStatus = (id: string, status: TaskStatus) =>
  mutate<TaskRecord>(`/api/tasks/${id}`, "PATCH", { status });
export const fetchPeople = () => request<Person[]>("/api/people");
export const fetchActivity = () => request<ActivityRecord[]>("/api/activity");
export const fetchPlaybooks = () => request<Playbook[]>("/api/playbooks");
export const fetchSystem = () => request<SystemStatus>("/api/system");
export const fetchIntakeSources = () => request<IntakeSourceSummary[]>("/api/intake/sources");
export const fetchIntakeSource = (id: string) => request<IntakeSource>(`/api/intake/sources/${id}`);

async function mutate<T>(path: string, method: "POST" | "PATCH", body?: object): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    method,
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail || `API request failed (${response.status}): ${path}`);
  }
  return response.json() as Promise<T>;
}

export const createIntakeSource = (input: {
  title: string;
  source_type: IntakeSourceType;
  content: string;
}) => mutate<IntakeSource>("/api/intake/sources", "POST", input);
export const retryIntakeSource = (id: string) =>
  mutate<IntakeSource>(`/api/intake/sources/${id}/retry`, "POST");
export const reviewIntakeProposal = (id: string, status: "approved" | "rejected") =>
  mutate<IntakeProposal>(`/api/intake/proposals/${id}`, "PATCH", { status });
export const askAdvisor = (question: string) =>
  mutate<AdvisorAnswer>("/api/advisor/questions", "POST", { question });

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
