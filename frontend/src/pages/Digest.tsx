import { useEffect, useState } from "react";
import { api } from "../api";
import type { Digest } from "../types";

export default function DigestPage() {
  const [list, setList] = useState<Digest[]>([]);
  const [current, setCurrent] = useState<Digest | null>(null);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    const d = await api.digests();
    setList(d);
    setCurrent((cur) => cur || d[0] || null);
  };
  useEffect(() => { load(); }, []);

  const gen = async (kind: "morning" | "evening") => {
    setBusy(true);
    try {
      const d = kind === "morning" ? await api.morning() : await api.evening();
      setCurrent(d);
      await load();
    } finally { setBusy(false); }
  };

  return (
    <div className="grid2">
      <div className="col">
        <div className="panel row">
          <button className="primary" onClick={() => gen("morning")} disabled={busy}>
            🌅 Утренний
          </button>
          <button className="primary" onClick={() => gen("evening")} disabled={busy}>
            🌙 Вечерний
          </button>
        </div>
        <div className="panel">
          {current ? <pre className="digest">{current.content}</pre>
                   : <div className="muted">Сгенерируйте дайджест.</div>}
        </div>
      </div>

      <div className="panel">
        <h3 style={{ marginTop: 0 }}>История</h3>
        {list.length === 0 && <div className="muted">Пока нет дайджестов.</div>}
        {list.map((d) => (
          <div className="list-item" key={d.id} style={{ cursor: "pointer" }}
               onClick={() => setCurrent(d)}>
            <b>{d.kind === "morning" ? "🌅 Утренний" : "🌙 Вечерний"}</b> · {d.date}
            <div className="muted" style={{ fontSize: 11 }}>
              {d.created_at.slice(0, 16).replace("T", " ")}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
