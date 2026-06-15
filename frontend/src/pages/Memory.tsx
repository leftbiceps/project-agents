import { useEffect, useState } from "react";
import { api } from "../api";
import type { MemoryItem, MemoryType } from "../types";

const TYPES: MemoryType[] = [
  "user_preference", "recurring_routine", "personal_context",
  "project_context", "contact", "rule", "constraint",
];

export default function Memory() {
  const [items, setItems] = useState<MemoryItem[]>([]);
  const [q, setQ] = useState("");
  const [form, setForm] = useState<{ content: string; type: MemoryType }>({
    content: "", type: "personal_context",
  });

  const load = async () => setItems(await api.memory());
  useEffect(() => { load(); }, []);

  const add = async () => {
    if (!form.content.trim()) return;
    await api.createMemory(form);
    setForm({ content: "", type: form.type });
    load();
  };
  const del = async (id: string) => { await api.deleteMemory(id); load(); };

  const shown = items.filter(
    (m) => !q || (m.content + m.type).toLowerCase().includes(q.toLowerCase()));

  return (
    <div className="col">
      <div className="panel col">
        <div className="row">
          <input placeholder="Новый факт о пользователе…" value={form.content}
                 onChange={(e) => setForm({ ...form, content: e.target.value })}
                 onKeyDown={(e) => e.key === "Enter" && add()} />
          <select value={form.type} style={{ width: 200 }}
                  onChange={(e) => setForm({ ...form, type: e.target.value as MemoryType })}>
            {TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <button className="primary" onClick={add}>Сохранить</button>
        </div>
        <input placeholder="Поиск по памяти…" value={q}
               onChange={(e) => setQ(e.target.value)} />
      </div>

      <div className="panel">
        {shown.length === 0 && <div className="muted">Память пуста.</div>}
        {shown.map((m) => (
          <div className="list-item row" key={m.id}>
            <span className="badge">{m.type}</span>
            <span style={{ flex: 1 }}>{m.content}</span>
            <button onClick={() => del(m.id)}>✕</button>
          </div>
        ))}
      </div>
    </div>
  );
}
