import { useEffect, useState } from "react";
import { api } from "../api";
import type { Task, WeekDay } from "../types";

const DOW = ["Вс", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"];

export default function CalendarPage() {
  const [days, setDays] = useState<WeekDay[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [form, setForm] = useState({ title: "", date: "", start: "10:00", end: "11:00" });

  const load = async () => {
    const [w, t] = await Promise.all([api.week(), api.tasks()]);
    setDays(w.days);
    setTasks(t);
    setForm((f) => (f.date ? f : { ...f, date: w.days[0]?.date || "" }));
  };
  useEffect(() => { load(); }, []);

  const create = async () => {
    if (!form.title || !form.date) return;
    await api.createEvent({
      title: form.title,
      start_datetime: `${form.date}T${form.start}`,
      end_datetime: `${form.date}T${form.end}`,
      type: "meeting",
    });
    setForm((f) => ({ ...f, title: "" }));
    load();
  };
  const del = async (id: string) => { await api.deleteEvent(id); load(); };

  return (
    <div className="col">
      <div className="panel">
        <div className="row" style={{ flexWrap: "wrap" }}>
          <input placeholder="Название события" value={form.title}
                 onChange={(e) => setForm({ ...form, title: e.target.value })}
                 style={{ flex: 2, minWidth: 160 }} />
          <input type="date" value={form.date}
                 onChange={(e) => setForm({ ...form, date: e.target.value })} style={{ width: 150 }} />
          <input type="time" value={form.start}
                 onChange={(e) => setForm({ ...form, start: e.target.value })} style={{ width: 110 }} />
          <input type="time" value={form.end}
                 onChange={(e) => setForm({ ...form, end: e.target.value })} style={{ width: 110 }} />
          <button className="primary" onClick={create}>Создать</button>
          <button onClick={load}>Обновить</button>
        </div>
      </div>

      <div className="week">
        {days.map((d) => {
          const dow = DOW[new Date(d.date).getDay()];
          const deadlines = tasks.filter(
            (t) => t.deadline && t.deadline.slice(0, 10) === d.date
              && t.status !== "done" && t.status !== "archived"
          );
          const empty = d.events.length === 0 && deadlines.length === 0;
          return (
            <div className="day" key={d.date}>
              <h4>{dow} {d.date.slice(5)}</h4>
              {empty && <div className="muted" style={{ fontSize: 11 }}>—</div>}
              {d.events.map((e) => (
                <div className={"evt " + e.type} key={e.id} title={e.description}>
                  <span className="x" onClick={() => del(e.id)}>✕</span>
                  {e.start_datetime.slice(11, 16)} {e.title}
                </div>
              ))}
              {deadlines.map((t) => (
                <div className="evt" key={"dl-" + t.id}
                     title={"Дедлайн задачи: " + t.title}
                     style={{ background: "#fef3c7", color: "#92400e" }}>
                  ⏰ {t.deadline!.slice(11, 16)} {t.title}
                </div>
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}
