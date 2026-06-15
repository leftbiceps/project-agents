import type {
  AgentMessage, CalendarEvent, Checklist, Digest, MemoryItem, Task, WeekDay,
} from "./types";

const BASE = (import.meta as any).env?.VITE_API_BASE || "/api";

async function req<T>(path: string, method = "GET", body?: any): Promise<T> {
  const res = await fetch(BASE + path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail ?? detail; } catch { /* ignore */ }
    throw new Error(`${res.status}: ${detail}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  // meta
  health: () => req<any>("/health"),
  agents: () => req<any>("/meta/agents"),
  seed: () => req<any>("/demo/seed", "POST"),
  reset: () => req<any>("/demo/reset", "POST"),

  // chat & actions
  chat: (message: string, history: { role: string; content: string }[]) =>
    req<AgentMessage>("/chat", "POST", { message, history }),
  chatHistory: () => req<AgentMessage[]>("/chat/history"),
  clearChatHistory: () => req<any>("/chat/history", "DELETE"),
  plan: (text: string, horizon_days = 7) =>
    req<AgentMessage>("/plan", "POST", { text, horizon_days }),
  prioritize: (message?: string) =>
    req<AgentMessage>("/prioritize", "POST", { message }),
  sleepMode: () => req<AgentMessage>("/sleep-mode", "POST"),

  // tasks
  tasks: () => req<Task[]>("/tasks"),
  createTask: (t: Partial<Task>) => req<Task>("/tasks", "POST", t),
  patchTask: (id: string, t: Partial<Task>) => req<Task>(`/tasks/${id}`, "PATCH", t),
  deleteTask: (id: string) => req<any>(`/tasks/${id}`, "DELETE"),

  // checklists
  checklists: (taskId?: string) =>
    req<Checklist[]>("/checklists" + (taskId ? `?task_id=${taskId}` : "")),
  toggleItem: (clId: string, itemId: string, done: boolean) =>
    req<Checklist>(`/checklists/${clId}/items/${itemId}`, "PATCH", { done }),

  // calendar
  week: (startDate?: string) =>
    req<{ start_date: string; days: WeekDay[] }>(
      "/calendar/week" + (startDate ? `?start_date=${startDate}` : "")),
  createEvent: (e: Partial<CalendarEvent>) =>
    req<any>("/calendar/events", "POST", e),
  deleteEvent: (id: string) => req<any>(`/calendar/events/${id}`, "DELETE"),

  // memory
  memory: () => req<MemoryItem[]>("/memory"),
  createMemory: (m: Partial<MemoryItem>) => req<MemoryItem>("/memory", "POST", m),
  deleteMemory: (id: string) => req<any>(`/memory/${id}`, "DELETE"),

  // digest
  morning: () => req<Digest>("/digest/morning", "POST", {}),
  evening: () => req<Digest>("/digest/evening", "POST", {}),
  digests: () => req<Digest[]>("/digest"),
};
