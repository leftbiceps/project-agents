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

// --- Потоковый чат (SSE) ---
export interface StreamHandlers {
  onRouted?: (d: { agent: string; rationale: string }) => void;
  onToolStart?: (d: { tool: string }) => void;
  onTool?: (d: { tool: string; ok: boolean }) => void;
  onToken?: (text: string) => void;
  onDone?: (msg: AgentMessage) => void;
}

export async function chatStream(
  message: string,
  history: { role: string; content: string }[],
  h: StreamHandlers
): Promise<void> {
  const res = await fetch(BASE + "/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history }),
  });
  if (!res.ok || !res.body) throw new Error("stream " + res.status);

  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let idx: number;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const block = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      const line = block.split("\n").find((l) => l.startsWith("data:"));
      if (!line) continue;
      let obj: any;
      try { obj = JSON.parse(line.slice(5).trim()); } catch { continue; }
      switch (obj.event) {
        case "routed": h.onRouted?.(obj); break;
        case "tool_start": h.onToolStart?.(obj); break;
        case "tool": h.onTool?.(obj); break;
        case "token": h.onToken?.(obj.text); break;
        case "done": h.onDone?.(obj.message as AgentMessage); break;
        case "error": throw new Error(obj.detail || "stream error");
      }
    }
  }
}
