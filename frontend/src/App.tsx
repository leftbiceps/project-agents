import { useEffect, useState } from "react";
import { api } from "./api";
import Chat from "./pages/Chat";
import Tasks from "./pages/Tasks";
import CalendarPage from "./pages/Calendar";
import Memory from "./pages/Memory";
import DigestPage from "./pages/Digest";

const TABS = [
  ["chat", "Чат"], ["tasks", "Задачи"], ["calendar", "Календарь"],
  ["memory", "Память"], ["digest", "Дайджест"],
] as const;

export default function App() {
  const [tab, setTab] = useState<string>("chat");
  const [mode, setMode] = useState("…");
  const [busy, setBusy] = useState(false);

  const refreshHealth = () =>
    api.health().then((h) => setMode(h.mode)).catch(() => setMode("offline"));

  useEffect(() => { refreshHealth(); }, []);

  const seed = async () => {
    setBusy(true);
    try { await api.seed(); alert("Демо-данные загружены"); }
    catch (e: any) { alert("Ошибка: " + e.message); }
    finally { setBusy(false); refreshHealth(); }
  };
  const reset = async () => {
    if (!confirm("Очистить все данные?")) return;
    setBusy(true);
    try { await api.reset(); } finally { setBusy(false); refreshHealth(); }
  };

  return (
    <div className="app">
      <div className="topbar">
        <h1>🤖 Локальный ассистент</h1>
        <span className="mode-pill">LLM-режим: <b>{mode}</b></span>
        <div className="spacer" />
        <button onClick={seed} disabled={busy}>Загрузить демо</button>
        <button onClick={reset} disabled={busy}>Сброс</button>
      </div>
      <div className="tabs" style={{ marginBottom: 16 }}>
        {TABS.map(([k, label]) => (
          <button key={k} className={"tab" + (tab === k ? " active" : "")}
                  onClick={() => setTab(k)}>{label}</button>
        ))}
      </div>
      {tab === "chat" && <Chat />}
      {tab === "tasks" && <Tasks />}
      {tab === "calendar" && <CalendarPage />}
      {tab === "memory" && <Memory />}
      {tab === "digest" && <DigestPage />}
    </div>
  );
}
