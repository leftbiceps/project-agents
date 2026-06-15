export type TaskStatus =
  | "backlog" | "todo" | "in_progress" | "blocked" | "done" | "archived";
export type Priority = "low" | "medium" | "high" | "urgent";
export type MemoryType =
  | "user_preference" | "recurring_routine" | "personal_context"
  | "project_context" | "contact" | "rule" | "constraint";

export interface Task {
  id: string;
  title: string;
  description: string;
  status: TaskStatus;
  priority: Priority;
  deadline: string | null;
  tags: string[];
  project: string | null;
  checklist_ids: string[];
  estimated_minutes: number | null;
  actual_minutes: number | null;
  source: string;
  created_at: string;
  updated_at: string;
}

export interface ChecklistItem {
  id: string;
  text: string;
  done: boolean;
}
export interface Checklist {
  id: string;
  task_id: string | null;
  title: string;
  items: ChecklistItem[];
  total: number;
  completed: number;
  progress: number;
}

export interface CalendarEvent {
  id: string;
  title: string;
  description: string;
  start_datetime: string;
  end_datetime: string;
  type: string;
  linked_task_id: string | null;
}

export interface MemoryItem {
  id: string;
  type: MemoryType;
  content: string;
  key: string | null;
  tags: string[];
  source: string;
  created_at: string;
}

export interface Digest {
  id: string;
  kind: string;
  date: string;
  content: string;
  data: Record<string, any>;
  created_at: string;
}

export interface ToolCall {
  id: string;
  agent: string;
  tool: string;
  input: Record<string, any>;
  output: any;
  ok: boolean;
  error: string | null;
  ts: string;
}

export interface ReflectionResult {
  passed: boolean;
  issues: string[];
  suggested_fixes: string[];
  requires_user_confirmation: boolean;
  notes: string;
}

export interface VerificationCheck { name: string; ok: boolean; detail: string; }
export interface VerificationResult {
  passed: boolean;
  checks: VerificationCheck[];
  summary: string;
}

export interface AgentMessage {
  role: string;
  agent: string | null;
  content: string;
  tool_calls: ToolCall[];
  reflection: ReflectionResult | null;
  verification: VerificationResult | null;
  routed_to: string | null;
  rationale: string | null;
  created_at: string;
}

export interface WeekDay { date: string; events: CalendarEvent[]; }
