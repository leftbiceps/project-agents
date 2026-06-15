"""Eval-скрипт: прогоняет сценарии, считает метрики и проверяет quality gate.

Запуск (из папки backend):
    python evals/eval.py                 # печать метрик
    python evals/eval.py --enforce-gate  # + exit code 1, если gate не пройден
    python evals/eval.py --json out.json # сохранить метрики в файл

Работает в любом режиме LLM (none / openai / local_openai / anthropic).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# чтобы `import app` работал при запуске как `python evals/eval.py`
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents import get_orchestrator  # noqa: E402
from app.agents.reflection import reflect  # noqa: E402
from app.models import ToolCall  # noqa: E402
from app.seed import seed_demo  # noqa: E402
from app.storage import storage  # noqa: E402

# Сценарий: (имя, сообщение, ожидаемый агент, ожидаемый инструмент|None, проверка)
SCENARIOS = [
    ("Создание задачи", "Создай задачу купить билеты на поезд", "task",
     "create_task",
     lambda st, m: any("билет" in t.title.lower() for t in st.tasks.all())),
    ("Разбивка на чеклист", "Разбей на чеклист: подготовка доклада", "task",
     "create_checklist", lambda st, m: st.checklists.count() > 0),
    ("Планирование недели",
     "Спланируй неделю: презентация, статья, письмо преподавателю", "planning",
     "schedule_tasks_to_free_slots", lambda st, m: st.events.count() > 0),
    ("Что делать дальше", "Что мне сейчас делать дальше?", "prioritization",
     None, lambda st, m: len(m.content) > 20),
    ("Сохранение памяти", "Запомни, что я лучше работаю по утрам", "memory",
     "save_memory",
     lambda st, m: any("утр" in x.content.lower() for x in st.memory.all())),
    ("Утренний дайджест", "Сделай утренний дайджест", "digest",
     "generate_morning_digest",
     lambda st, m: any(d.kind == "morning" for d in st.digests.all())),
    ("Режим сна", "Закрой день и переведи меня в режим сна", "sleep_fairy",
     "generate_evening_digest",
     lambda st, m: any(d.kind == "evening" for d in st.digests.all())),
    ("Создание события", "Создай событие созвон с командой завтра в 16:00",
     "calendar", "create_event", lambda st, m: st.events.count() > 0),
]

# Пороги quality gate: метрика -> (направление, порог, тип)
# направление: "ge" — чем больше тем лучше; "le" — чем меньше тем лучше.
THRESHOLDS = {
    "Task Success Rate":            ("ge", 0.90, "hard"),
    "Tool Call Accuracy":           ("ge", 0.90, "hard"),
    "Verification Pass Rate":       ("ge", 0.95, "hard"),
    "Human Confirmation Precision": ("ge", 0.90, "hard"),
    "Routing Accuracy":             ("ge", 0.85, "soft"),
    "Autonomy Rate":                ("ge", 0.80, "soft"),
    "Digest Usefulness":            ("ge", 0.70, "soft"),
    "Calendar Conflict Rate":       ("le", 0.34, "hard"),
}
SOFT_PASS_RATE_MIN = 0.75


def digest_usefulness(content: str, kind: str = "morning") -> float:
    # Полнота САМОГО дайджеста (сохранённого), маркеры под тип (утро/вечер).
    markers = (["задач", "событ", "рекоменд", "план"] if kind == "morning"
               else ["выполн", "перенес", "план", "завтра"])
    c = (content or "").lower()
    hits = sum(1 for w in markers if w in c)
    return round(hits / len(markers), 2)


def compute_metrics() -> tuple[dict, list]:
    orch = get_orchestrator()
    seed_demo()
    rows = []
    routing_ok = tool_ok = success = autonomy = 0
    verif_total = verif_pass = 0
    digest_scores = []
    conflicts_total = 0

    for name, msg, exp_agent, exp_tool, check in SCENARIOS:
        res = orch.handle(msg)
        tools = [tc.tool for tc in res.tool_calls]
        r_ok = res.agent == exp_agent
        t_ok = (exp_tool is None) or (exp_tool in tools and
                                      all(tc.ok for tc in res.tool_calls))
        try:
            s_ok = bool(check(storage, res))
        except Exception:
            s_ok = False
        a_ok = bool(res.content) and not res.content.startswith("Ошибка")

        routing_ok += r_ok
        if exp_tool is not None:
            tool_ok += t_ok
        success += s_ok
        autonomy += a_ok
        if res.verification and res.verification.checks:
            verif_total += 1
            verif_pass += res.verification.passed
        if exp_agent in ("digest", "sleep_fairy"):
            kind = "evening" if exp_agent == "sleep_fairy" else "morning"
            digs = [d for d in storage.digests.all() if d.kind == kind]
            content = digs[-1].content if digs else res.content
            digest_scores.append(digest_usefulness(content, kind))
        for tc in res.tool_calls:
            if tc.tool == "create_event" and isinstance(tc.output, dict):
                conflicts_total += len(tc.output.get("conflicts", []))

        rows.append((name, exp_agent, res.agent, r_ok, t_ok, s_ok,
                     bool(res.verification and res.verification.passed)))

    # Human Confirmation Precision: прямая проверка Reflection
    del_tc = ToolCall(agent="task", tool="delete_task", input={"id": "x"},
                      output={"deleted": True, "id": "x"}, ok=True)
    crt_tc = ToolCall(agent="task", tool="create_task", input={},
                      output={"id": "task_1"}, ok=True)
    conf_del = reflect("удали задачу", "task", [del_tc], "").requires_user_confirmation
    conf_crt = reflect("создай задачу", "task", [crt_tc], "").requires_user_confirmation
    confirmation_precision = round(((1 if conf_del else 0) +
                                    (1 if not conf_crt else 0)) / 2, 2)

    n = len(SCENARIOS)
    tool_n = sum(1 for s in SCENARIOS if s[3] is not None)
    metrics = {
        "Routing Accuracy": round(routing_ok / n, 2),
        "Tool Call Accuracy": round(tool_ok / tool_n, 2) if tool_n else 1.0,
        "Task Success Rate": round(success / n, 2),
        "Autonomy Rate": round(autonomy / n, 2),
        "Verification Pass Rate": round(verif_pass / verif_total, 2) if verif_total else 1.0,
        "Human Confirmation Precision": confirmation_precision,
        "Digest Usefulness": round(sum(digest_scores) / len(digest_scores), 2) if digest_scores else 0.0,
        "Calendar Conflict Rate": round(conflicts_total / n, 2),
    }
    return metrics, rows


def check_gate(metrics: dict) -> tuple[bool, list[str]]:
    """Вернуть (passed, отчёт по метрикам)."""
    report = []
    hard_ok = True
    soft_total = soft_pass = 0
    for name, value in metrics.items():
        direction, thr, kind = THRESHOLDS.get(name, ("ge", 0.0, "soft"))
        ok = value >= thr if direction == "ge" else value <= thr
        sign = "≥" if direction == "ge" else "≤"
        report.append(f"  [{kind:4}] {name:<30} {value:<6} ({sign}{thr}) "
                      f"{'✓' if ok else '✗'}")
        if kind == "hard" and not ok:
            hard_ok = False
        if kind == "soft":
            soft_total += 1
            soft_pass += int(ok)
    soft_rate = (soft_pass / soft_total) if soft_total else 1.0
    gate = hard_ok and soft_rate >= SOFT_PASS_RATE_MIN
    report.append(f"\n  hard all pass: {hard_ok} | "
                  f"soft pass rate: {round(soft_rate, 2)} (мин {SOFT_PASS_RATE_MIN})")
    return gate, report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--enforce-gate", action="store_true",
                    help="вернуть exit code 1, если quality gate не пройден")
    ap.add_argument("--json", metavar="PATH", help="сохранить метрики в JSON")
    args = ap.parse_args()

    orch = get_orchestrator()
    metrics, rows = compute_metrics()

    print(f"\nРежим LLM: {orch.mode}\n")
    print(f"{'Сценарий':<24}{'ожид.агент':<16}{'факт':<16}{'rt':<4}{'tool':<6}{'task':<6}{'ver':<4}")
    print("-" * 86)
    for r in rows:
        print(f"{r[0]:<24}{r[1]:<16}{r[2]:<16}"
              f"{'✓' if r[3] else '✗':<4}{'✓' if r[4] else '✗':<6}"
              f"{'✓' if r[5] else '✗':<6}{'✓' if r[6] else '—':<4}")

    print("\n=== Метрики и quality gate ===")
    gate, report = check_gate(metrics)
    print("\n".join(report))
    print(f"\nQUALITY GATE: {'PASSED ✅' if gate else 'FAILED ❌'}")

    if args.json:
        Path(args.json).write_text(
            json.dumps({"mode": orch.mode, "metrics": metrics, "gate": gate},
                       ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nМетрики сохранены в {args.json}")

    if args.enforce_gate and not gate:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
