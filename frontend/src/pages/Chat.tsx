import React, { useEffect, useRef, useState } from "react";
import { api, chatStream } from "../api";
import type { AgentMessage } from "../types";

interface Entry {
  role: "user" | "assistant";
  content: string;
  msg?: AgentMessage;
  streaming?: boolean;
  status?: string;
}

const STORAGE_KEY = "assistant_chat_history_v1";

function loadHistory(): Entry[] {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]"); }
  catch { return []; }
}

const short = (o: any) => {
  const s = JSON.stringify(o);
  return s && s.length > 400 ? s.slice(0, 400) + "…" : s;
};

function MsgMeta({ msg }: { msg: AgentMessage }) {
  return (
    <div className="meta-line">
      <span className="badge">агент: {msg.routed_to}</span>{" "}
      <span className="muted">{msg.rationale}</span>

      {msg.tool_calls.length > 0 && (
        <details>
          <summary>{msg.tool_calls.length} вызов(ов) инструментов</summary>
          {msg.tool_calls.map((tc) => (
            <div className="toolcall" key={tc.id}>
              <span className={"dot " + (tc.ok ? "ok" : "err")} />
              <b>{tc.tool}</b>
              <pre>вход: {JSON.stringify(tc.input)}</pre>
              {tc.ok ? <pre>выход: {short(tc.output)}</pre>
                     : <pre className="err-text">ошибка: {tc.error}</pre>}
            </div>
          ))}
        </details>
      )}

      {msg.reflection && (
        <div className="toolcall">
          <b>Reflection:</b>{" "}
          {msg.reflection.passed ? "✅ пройдено" : "⚠️ есть замечания"}
          {msg.reflection.requires_user_confirmation && <span> · нужно подтверждение</span>}
          {msg.reflection.issues.length > 0 &&
            <pre>{msg.reflection.issues.map((x) => "• " + x).join("\n")}</pre>}
        </div>
      )}

      {msg.verification && (
        <div className="toolcall">
          <b>Verifier:</b> {msg.verification.passed ? "✅" : "❌"} {msg.verification.summary}
          {msg.verification.checks.length > 0 &&
            <pre>{msg.verification.checks.map((c) => (c.ok ? "✓ " : "✗ ") + c.detail).join("\n")}</pre>}
        </div>
      )}
    </div>
  );
}

export default function Chat() {
  const [entries, setEntries] = useState<Entry[]>(loadHistory);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);

  // Персистентная история чата: сохраняем переписку в localStorage,
  // чтобы она не пропадала при перезагрузке страницы / перезапуске.
  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(entries)); } catch { /* quota */ }
  }, [entries]);

  const clearHistory = () => {
    setEntries([]);
    try { localStorage.removeItem(STORAGE_KEY); } catch { /* ignore */ }
  };

  const scroll = () =>
    setTimeout(() => logRef.current?.scrollTo(0, logRef.current.scrollHeight), 50);

  const send = async () => {
    const text = input.trim();
    if (!text || busy) return;
    const history = entries.map((e) => ({ role: e.role, content: e.content }));
    setEntries((p) => [
      ...p,
      { role: "user", content: text },
      { role: "assistant", content: "", streaming: true, status: "…" },
    ]);
    setInput(""); setBusy(true); scroll();

    // обновить последнюю (ассистентскую) запись
    const upd = (fn: (e: Entry) => Entry) =>
      setEntries((prev) => {
        const c = [...prev];
        for (let i = c.length - 1; i >= 0; i--) {
          if (c[i].role === "assistant") { c[i] = fn(c[i]); break; }
        }
        return c;
      });

    let gotAny = false;
    try {
      await chatStream(text, history, {
        onRouted: (d) => upd((e) => ({ ...e, status: `маршрут → ${d.agent}` })),
        onToolStart: (d) => { gotAny = true; upd((e) => ({ ...e, status: `⚙ ${d.tool}…` })); },
        onTool: () => { gotAny = true; },
        onToken: (t) => { gotAny = true; upd((e) => ({ ...e, status: undefined, content: e.content + t })); scroll(); },
        onDone: (m) => { gotAny = true; upd((e) => ({ ...e, streaming: false, status: undefined, content: m.content || e.content, msg: m })); },
      });
      upd((e) => (e.streaming ? { ...e, streaming: false, status: undefined } : e));
    } catch (err: any) {
      if (!gotAny) {
        // стрим недоступен (старый backend / сеть) — обычный запрос
        try {
          const m = await api.chat(text, history);
          upd((e) => ({ ...e, streaming: false, status: undefined, content: m.content, msg: m }));
        } catch (e2: any) {
          upd((e) => ({ ...e, streaming: false, status: undefined, content: "Ошибка: " + e2.message }));
        }
      } else {
        upd((e) => ({ ...e, streaming: false, status: undefined, content: e.content || ("Ошибка: " + err.message) }));
      }
    } finally { setBusy(false); scroll(); }
  };

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  };

  return (
    <div className="chat-wrap">
      <div className="chat-log" ref={logRef}>
        {entries.length === 0 && (
          <div className="muted">
            Примеры: «Создай задачу купить молоко к завтрашнему вечеру»,
            «Что мне сейчас делать дальше?», «Спланируй неделю: презентация,
            статья, письмо», «Запомни, что я лучше работаю утром»,
            «Сделай утренний дайджест», «Переведи меня в режим сна».
          </div>
        )}
        {entries.map((e, i) => (
          <div key={i} className={"msg " + e.role}>
            {e.content && <div>{e.content}</div>}
            {e.streaming && e.status && (
              <div className="muted" style={{ fontSize: 12 }}>{e.status}</div>
            )}
            {e.streaming && !e.content && !e.status && (
              <div className="muted">…</div>
            )}
            {e.msg && <MsgMeta msg={e.msg} />}
          </div>
        ))}
      </div>
      <div className="chat-input">
        <textarea rows={2} value={input} placeholder="Напишите сообщение…"
                  onChange={(e) => setInput(e.target.value)} onKeyDown={onKey} />
        <button className="primary" onClick={send} disabled={busy}>Отправить</button>
        <button onClick={clearHistory} disabled={busy} title="Очистить историю чата">Очистить</button>
      </div>
    </div>
  );
}
