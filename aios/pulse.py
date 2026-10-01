"""Pulse: rotinas agendadas + fila de execução.

Fluxo (o mesmo em cada máquina, chamado a cada 5 min por launchd/systemd):
  1. `tick`  — lê pulse/routines.toml e enfileira em runs/queue/ o que venceu para ESTE host.
  2. `drain` — executa os pedidos da fila destinados a este host (rotinas, skills
               disparadas pelo painel ou pelo Telegram) e move para runs/done/.

A fila é só arquivos JSON, então ela viaja entre Mac e VPS pelo mesmo git sync da memória:
o botão no painel do Mac grava um pedido com host="vps" e o runner da VPS executa.
"""
from __future__ import annotations

import json
import subprocess
import time
import tomllib
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from .config import ROOT, claude_bin, current_host, load_settings
from .cron import Cron

ROUTINES_FILE = "pulse/routines.toml"
KINDS = {"claude", "script", "skill"}


@dataclass
class Routine:
    name: str
    purpose: str
    schedule: str
    host: str
    kind: str  # claude | script | skill
    prompt: str = ""  # kind=claude: caminho de pulse/prompts/*.md
    run: str = ""  # kind=script: comando shell
    skill: str = ""  # kind=skill: nome em .claude/commands/
    enabled: bool = True
    timeout_min: int = 20

    @property
    def cron(self) -> Cron:
        return Cron.parse(self.schedule)


def load_routines(root: Path = ROOT) -> list[Routine]:
    data = tomllib.loads((root / ROUTINES_FILE).read_text(encoding="utf-8"))
    routines = [Routine(**r) for r in data.get("routine", [])]
    errors = validate(routines, root)
    if errors:
        raise ValueError("routines.toml inválido:\n  " + "\n  ".join(errors))
    return routines


def validate(routines: list[Routine], root: Path) -> list[str]:
    errors, seen = [], set()
    for r in routines:
        where = f"[{r.name}]"
        if r.name in seen:
            errors.append(f"{where} nome duplicado")
        seen.add(r.name)
        if r.kind not in KINDS:
            errors.append(f"{where} kind deve ser um de {sorted(KINDS)}")
        try:
            r.cron
        except ValueError as e:
            errors.append(f"{where} schedule: {e}")
        if r.kind == "claude" and not (root / r.prompt).is_file():
            errors.append(f"{where} prompt não encontrado: {r.prompt!r}")
        if r.kind == "script" and not r.run:
            errors.append(f"{where} kind=script exige 'run'")
        if r.kind == "skill" and not (root / ".claude/commands" / f"{r.skill}.md").is_file():
            errors.append(f"{where} skill não encontrada: {r.skill!r}")
    return errors


# ---------------------------------------------------------------- estado por host

def _state_path(root: Path, host: str) -> Path:
    return root / "runs" / f"state-{host}.json"


def load_state(root: Path, host: str) -> dict:
    p = _state_path(root, host)
    return json.loads(p.read_text()) if p.exists() else {"routines": {}}


def _save_state(root: Path, host: str, state: dict) -> None:
    p = _state_path(root, host)
    p.parent.mkdir(parents=True, exist_ok=True)
    state["host"], state["updated_at"] = host, _iso(datetime.now())
    p.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")


def _iso(t: datetime) -> str:
    return t.replace(microsecond=0).isoformat()


# ---------------------------------------------------------------- fila

def enqueue(root: Path, *, kind: str, name: str, host: str, source: str,
            args: str = "") -> Path:
    q = root / "runs" / "queue"
    q.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    job = {"id": f"{now:%Y%m%d-%H%M%S-%f}-{uuid.uuid4().hex[:4]}", "kind": kind, "name": name,
           "host": host, "source": source, "args": args, "requested_at": _iso(now)}
    path = q / f"{job['id']}.json"
    path.write_text(json.dumps(job, indent=2, ensure_ascii=False) + "\n")
    return path


def tick(root: Path = ROOT, host: str | None = None, now: datetime | None = None) -> list[str]:
    """Enfileira as rotinas deste host que venceram desde o último tick."""
    host = host or current_host(root)
    now = now or datetime.now()
    state = load_state(root, host)
    last_tick = datetime.fromisoformat(state.get("last_tick", _iso(now - timedelta(minutes=5))))
    max_fails = load_settings(root).get("pulse", {}).get("max_consecutive_failures", 3)
    queued = []
    for r in load_routines(root):
        if not r.enabled or r.host != host:
            continue
        if state["routines"].get(r.name, {}).get("fails", 0) >= max_fails:
            continue  # trava: rotina que falha em série fica pausada até `aios reset <nome>`
        if r.cron.due_between(last_tick, now):
            enqueue(root, kind="routine", name=r.name, host=host, source="pulse")
            queued.append(r.name)
    state["last_tick"] = _iso(now)
    _save_state(root, host, state)
    return queued


def _command_for(job: dict, root: Path) -> tuple[list[str] | str, int]:
    claude = claude_bin()
    if job["kind"] == "skill":
        prompt = f"/{job['name']} {job.get('args', '')}".strip()
        return [claude, "-p", prompt], 20
    if job["kind"] == "ask":  # pergunta livre (ex.: Telegram)
        return [claude, "-p", job["args"]], 10
    routine = next((r for r in load_routines(root) if r.name == job["name"]), None)
    if routine is None:
        raise LookupError(f"rotina desconhecida: {job['name']}")
    if routine.kind == "script":
        return routine.run, routine.timeout_min
    if routine.kind == "skill":
        return [claude, "-p", f"/{routine.skill}"], routine.timeout_min
    prompt = (root / routine.prompt).read_text(encoding="utf-8")
    return [claude, "-p", prompt], routine.timeout_min


def runs_today(root: Path, host: str, today: str) -> int:
    count = 0
    for p in (root / "runs" / "done").glob("*.json"):
        r = json.loads(p.read_text())
        if r.get("ran_on") == host and r.get("finished_at", "")[:10] == today:
            count += 1
    return count


def run_job(path: Path, root: Path = ROOT, host: str | None = None) -> dict:
    host = host or current_host(root)
    job = json.loads(path.read_text())
    started = time.time()
    log_dir = root / "runs" / "log"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{job['id']}.log"
    try:
        cmd, timeout_min = _command_for(job, root)
        proc = subprocess.run(cmd, cwd=root, shell=isinstance(cmd, str), capture_output=True,
                              text=True, timeout=timeout_min * 60)
        status = "ok" if proc.returncode == 0 else f"exit {proc.returncode}"
        output = proc.stdout + ("\n--- stderr ---\n" + proc.stderr if proc.stderr else "")
    except subprocess.TimeoutExpired:
        status, output = "timeout", ""
    except Exception as e:  # registra e segue: um job ruim não pode travar a fila
        status, output = "error", f"{type(e).__name__}: {e}"
    log_file.write_text(output)
    result = {**job, "status": status, "ran_on": host, "seconds": round(time.time() - started, 1),
              "finished_at": _iso(datetime.now()), "output_tail": output.strip()[-600:]}
    done = root / "runs" / "done"
    done.mkdir(parents=True, exist_ok=True)
    (done / path.name).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    path.unlink()

    state = load_state(root, host)
    prev = state["routines"].get(job["name"], {})
    fails = 0 if status == "ok" else prev.get("fails", 0) + 1
    state["routines"][job["name"]] = {"last_run": result["finished_at"], "status": status,
                                     "kind": job["kind"], "fails": fails}
    _save_state(root, host, state)
    return result


def reset(root: Path, host: str, name: str) -> None:
    state = load_state(root, host)
    if name in state["routines"]:
        state["routines"][name]["fails"] = 0
        _save_state(root, host, state)


def drain(root: Path = ROOT, host: str | None = None) -> list[dict]:
    """Executa a fila deste host, respeitando o teto diário de execuções (proteção de custo)."""
    host = host or current_host(root)
    cap = load_settings(root).get("pulse", {}).get("max_runs_per_day", 40)
    today = datetime.now().date().isoformat()
    results = []
    for path in sorted((root / "runs" / "queue").glob("*.json")):
        if json.loads(path.read_text()).get("host") != host:
            continue
        if runs_today(root, host, today) >= cap:
            print(f"teto diário de {cap} execuções atingido em {host}; restante fica na fila")
            break
        results.append(run_job(path, root, host))
    return results
