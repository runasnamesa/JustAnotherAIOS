"""Monta o snapshot que o painel mostra — lido dos arquivos a cada requisição.

O painel não tem banco de dados nem estado próprio: tudo vem daqui, e daqui vem tudo
de arquivos do vault, do pulse e de runs/. Se o arquivo mudar, o painel muda.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from .config import ROOT, current_host
from .pulse import load_routines

NEEDS_FILE = "areas/sistema/precisa-de-voce.md"
AGENDA_FILE = "areas/sistema/agenda.md"
BRIEF_FILE = "areas/sistema/resumo-do-dia.md"

_NEED = re.compile(r"^- \[ \] \*\*(.+?)\*\*\s*(?:[—-]\s*(.*))?$")
_AGENDA = re.compile(r"^- (\d{4}-\d{2}-\d{2})(?:\s+(\d{2}:\d{2}))?\s*[:—-]\s*(.+)$")


def _read(root: Path, rel: str) -> str:
    p = root / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


def needs_you(root: Path) -> list[dict]:
    """Única lista que espera um humano. Só itens `- [ ]`; o Claude nunca marca `[x]`."""
    out = []
    for line in _read(root, NEEDS_FILE).splitlines():
        m = _NEED.match(line.strip())
        if m:
            out.append({"title": m.group(1), "detail": m.group(2) or ""})
    return out


def agenda(root: Path, today: date, days: int = 14) -> list[dict]:
    out = []
    for line in _read(root, AGENDA_FILE).splitlines():
        m = _AGENDA.match(line.strip())
        if not m:
            continue
        d = date.fromisoformat(m.group(1))
        if today <= d <= today + timedelta(days=days):
            out.append({"date": m.group(1), "time": m.group(2) or "", "text": m.group(3)})
    return sorted(out, key=lambda e: (e["date"], e["time"]))


def routines_board(root: Path, now: datetime) -> list[dict]:
    today = now.date()
    states = {}
    for p in (root / "runs").glob("state-*.json"):
        s = json.loads(p.read_text())
        states[s.get("host", p.stem[6:])] = s
    board = []
    for r in load_routines(root):
        st = states.get(r.host, {}).get("routines", {}).get(r.name, {})
        last = st.get("last_run", "")
        ran_today = last[:10] == today.isoformat()
        start = datetime.combine(today, datetime.min.time())
        slots = [start + timedelta(minutes=m) for m in range(24 * 60) if r.cron.matches(start + timedelta(minutes=m))]
        due_today = bool(slots)
        due_passed = bool(slots) and slots[0] <= now
        board.append({"name": r.name, "purpose": r.purpose, "host": r.host, "schedule": r.schedule,
                      "enabled": r.enabled, "last_run": last, "status": st.get("status", ""),
                      "ran_today": ran_today, "due_today": due_today, "due_passed": due_passed})
    return board


def snapshot(root: Path = ROOT, now: datetime | None = None) -> dict:
    now = now or datetime.now()
    graph_path = root / "map" / "graph.json"
    queue = [json.loads(p.read_text()) for p in sorted((root / "runs" / "queue").glob("*.json"))]
    done_all = sorted((root / "runs" / "done").glob("*.json"))
    done = done_all[-15:]
    since = (now.date() - timedelta(days=13)).isoformat()
    history = []
    for p in done_all:
        r = json.loads(p.read_text())
        if r.get("finished_at", "")[:10] >= since:
            history.append({"name": r["name"], "kind": r.get("kind", ""), "status": r.get("status", ""),
                            "at": r.get("finished_at", ""), "host": r.get("ran_on", "")})
    return {
        "now": now.replace(microsecond=0).isoformat(),
        "host": current_host(root),
        "needs_you": needs_you(root),
        "agenda": agenda(root, now.date()),
        "brief": _read(root, BRIEF_FILE),
        "routines": routines_board(root, now),
        "queue": queue,
        "recent_runs": [json.loads(p.read_text()) for p in reversed(done)],
        "runs_total": len(done_all),
        "run_history": history,
        "graph": json.loads(graph_path.read_text()) if graph_path.exists() else {"nodes": [], "links": []},
    }
