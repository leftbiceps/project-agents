import { useEffect, useState } from "react";
import { api } from "../api";
import type { Checklist, Task, TaskStatus } from "../types";

const COLUMNS: { key: TaskStatus; label: string }[] = [
  { key: "backlog", label: "Backlog" },
  { key: "todo", label: "To Do" },
  { key: "in_progress", label: "In Progress" },
  { key: "blocked", label: "Blocked" },
  { key: "done", label: "Done" },
];
const STATUSES: TaskStatus[] =
  ["backlog", "todo", "in_progress", "blocked", "done", "archived"];

export default function Tasks() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [cls, setCls] = useState<Checklist[]>([]);
  const [title, setTitle] = useState("");

  const load = async () => {
    const [t, c] = await Promise.all([api.tasks(), api.checklists()]);
    setTasks(t); setCls(c);
  };
  useEffect(() => { load(); }, []);

  const add = async () => {
    if (!title.trim()) return;
    await api.createTask({ title: title.trim(), status: "todo" });
    setTitle(""); load();
  };
  const setStatus = async (id: string, status: TaskStatus) => {
    await api.patchTask(id, { status }); load();
  };
  const del = async (id: string) => { await api.deleteTask(id); load(); };
  const toggle = async (clId: string, itemId: string, done: boolean) => {
    await api.toggleItem(clId, itemId, done); load();
  };

  const clOf = (t: Task) => cls.filter((c) => t.checklist_ids.includes(c.id));
  const prog = (t: Task) => {
    const cs = clOf(t);
    const tot = cs.reduce((a, c) => a + c.total, 0);
    const dn = cs.reduce((a, c) => a + c.completed, 0);
    return tot ? Math.round((dn / tot) * 100) : 0;
  };

  return (
    <div className="col">
      <div className="panel row">
        <input placeholder="Новая задача…" value={title}
               onChange={(e) => setTitle(e.target.value)}
               onKeyDown={(e) => e.key === "Enter" && add()} />
        <button className="primary" onClick={add}>Добавить</button>
        <button onClick={load}>Обновить</button>
      </div>

      <div className="board">
        {COLUMNS.map((col) => {
          const colTasks = tasks.filter((t) => t.status === col.key);
          return (
            <div className="column" key={col.key}>
              <h3>{col.label} ({colTasks.length})</h3>
              {colTasks.map((t) => (
                <div className="card" key={t.id}>
                  <div className="title">{t.title}</div>
                  <div>
                    <span className={"pill p-" + t.priority}>{t.priority}</span>
                    {t.deadline && (
                      <span className="muted" style={{ fontSize: 11 }}>
                        ⏰ {t.deadline.slice(0, 16).replace("T", " ")}
                      </span>
                    )}
                  </div>
                  {t.tags.length > 0 && (
                    <div style={{ marginTop: 4 }}>
                      {t.tags.map((tg) => <span className="tag" key={tg}>#{tg}</span>)}
                    </div>
                  )}
                  {clOf(t).length > 0 && (
                    <>
                      <div className="progress"><div style={{ width: prog(t) + "%" }} /></div>
                      {clOf(t).flatMap((c) =>
                        c.items.map((it) => (
                          <label className={"checkitem" + (it.done ? " done" : "")} key={it.id}>
                            <input type="checkbox" style={{ width: "auto" }}
                                   checked={it.done}
                                   onChange={(e) => toggle(c.id, it.id, e.target.checked)} />
                            {it.text}
                          </label>
                        ))
                      )}
                    </>
                  )}
                  <div className="row" style={{ marginTop: 6 }}>
                    <select value={t.status}
                            onChange={(e) => setStatus(t.id, e.target.value as TaskStatus)}>
                      {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                    </select>
                    <button onClick={() => del(t.id)}>✕</button>
                  </div>
                </div>
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}
