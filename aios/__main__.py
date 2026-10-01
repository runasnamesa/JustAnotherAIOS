"""CLI: python -m aios <comando>

  brain              gera map/MAP.md e map/graph.json (Memory nível 3)
  lint               checa placas, links, saltos e frescor do mapa (exit 1 se falhar)
  pulse              tick + drain: enfileira rotinas vencidas e executa a fila deste host
  tick | drain       as duas metades do pulse, separadas
  run KIND NAME      enfileira manualmente (KIND = routine | skill) [--host vps]
  reset NAME         destrava uma rotina pausada por falhas seguidas
  serve              sobe o painel (Screen) [--bind 127.0.0.1] [--port 8765]
  status             imprime o snapshot que o painel mostra (sem o grafo)
  telegram           bot do Telegram (VPS)
  notify [ARQUIVO]   manda o texto (arquivo ou stdin) para o Telegram
"""
from __future__ import annotations

import argparse
import json
import sys

from . import brain, lint, pulse, serve, status
from .config import ROOT, current_host


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="aios", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("brain", "lint", "pulse", "tick", "drain", "status", "telegram"):
        sub.add_parser(name)
    p = sub.add_parser("run")
    p.add_argument("kind", choices=["routine", "skill"])
    p.add_argument("name")
    p.add_argument("--host")
    p.add_argument("--args", default="")
    p = sub.add_parser("reset")
    p.add_argument("name")
    p.add_argument("--host")
    p = sub.add_parser("serve")
    p.add_argument("--bind", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    p = sub.add_parser("notify")
    p.add_argument("file", nargs="?")
    a = ap.parse_args(argv)

    if a.cmd == "brain":
        print("mapa gerado:", brain.build(ROOT))
    elif a.cmd == "lint":
        errors, warnings = lint.check(ROOT)
        for w in warnings:
            print("aviso:", w)
        for e in errors:
            print("ERRO:", e)
        print(f"{len(errors)} erro(s), {len(warnings)} aviso(s)")
        return 1 if errors else 0
    elif a.cmd in ("pulse", "tick"):
        print("enfileirado:", pulse.tick(ROOT) or "nada")
        if a.cmd == "pulse":
            for r in pulse.drain(ROOT):
                print(f"{r['name']}: {r['status']} ({r['seconds']}s)")
    elif a.cmd == "drain":
        for r in pulse.drain(ROOT):
            print(f"{r['name']}: {r['status']} ({r['seconds']}s)")
    elif a.cmd == "run":
        host = a.host
        if a.kind == "routine":
            host = next(r.host for r in pulse.load_routines(ROOT) if r.name == a.name)
        path = pulse.enqueue(ROOT, kind=a.kind, name=a.name, host=host or current_host(ROOT),
                             source="cli", args=a.args)
        print("na fila:", path.relative_to(ROOT))
    elif a.cmd == "reset":
        pulse.reset(ROOT, a.host or current_host(ROOT), a.name)
    elif a.cmd == "serve":
        serve.serve(ROOT, a.bind, a.port)
    elif a.cmd == "status":
        snap = status.snapshot(ROOT)
        snap["graph"] = f"{len(snap['graph']['nodes'])} nós"
        print(json.dumps(snap, indent=2, ensure_ascii=False))
    elif a.cmd == "telegram":
        from . import telegram
        telegram.poll(ROOT)
    elif a.cmd == "notify":
        from . import telegram
        text = open(a.file, encoding="utf-8").read() if a.file else sys.stdin.read()
        telegram.send_message(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
