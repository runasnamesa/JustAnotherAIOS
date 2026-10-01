"""Mede o efeito do mapa: a mesma pergunta numa cópia COM mapa e numa cópia SEM mapa.

"Sem mapa" = nível 1 (pilha de pastas): remove todos os CLAUDE.md e a pasta map/.
Usa `claude -p --output-format json`, que devolve duração, turnos, tokens e custo.

    python -m aios.measure "Quais palavras não posso usar em posts?" \
        --expect areas/conteudo/guia-de-estilo.md --runs 2

Uma execução não prova nada: rode >= 2 por lado e olhe a variação. O `--expect` checa se a
resposta cita o arquivo certo — economia sem acerto não conta.
"""
from __future__ import annotations

import argparse
import json
import shutil
import statistics
import subprocess
import tempfile
from pathlib import Path

from .config import ROOT, claude_bin

IGNORE = shutil.ignore_patterns(".git", "runs", "__pycache__", "drafts")


def make_copies(root: Path, base: Path) -> dict[str, Path]:
    with_map, without = base / "com-mapa", base / "sem-mapa"
    shutil.copytree(root, with_map, ignore=IGNORE)
    shutil.copytree(root, without, ignore=IGNORE)
    for f in without.rglob("CLAUDE.md"):
        f.unlink()
    shutil.rmtree(without / "map", ignore_errors=True)
    return {"com mapa": with_map, "sem mapa": without}


def run_once(cwd: Path, question: str) -> dict:
    proc = subprocess.run([claude_bin(), "-p", question, "--output-format", "json"], cwd=cwd,
                          capture_output=True, text=True, timeout=900)
    if proc.returncode != 0:
        raise RuntimeError(f"claude falhou em {cwd.name}: {proc.stderr[-400:]}")
    data = json.loads(proc.stdout)
    u = data.get("usage", {})
    tokens = sum(u.get(k, 0) for k in ("input_tokens", "output_tokens",
                                       "cache_read_input_tokens", "cache_creation_input_tokens"))
    return {"seconds": data.get("duration_ms", 0) / 1000, "turns": data.get("num_turns", 0),
            "tokens": tokens, "cost": data.get("total_cost_usd", 0.0),
            "answer": data.get("result", "")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--expect", help="caminho que a resposta certa deve citar")
    ap.add_argument("--runs", type=int, default=2)
    a = ap.parse_args(argv)

    rows = {}
    with tempfile.TemporaryDirectory() as tmp:
        for label, cwd in make_copies(ROOT, Path(tmp)).items():
            results = [run_once(cwd, a.question) for _ in range(a.runs)]
            hits = sum(1 for r in results if not a.expect or Path(a.expect).name in r["answer"])
            rows[label] = {k: [r[k] for r in results] for k in ("seconds", "turns", "tokens", "cost")}
            rows[label]["acertos"] = f"{hits}/{a.runs}"

    print(f"Pergunta: {a.question}\n")
    print(f"{'':10} {'tempo (s)':>16} {'turnos':>10} {'tokens':>20} {'custo US$':>14} {'acertos':>8}")
    for label, r in rows.items():
        def fmt(xs, f="{:.0f}"):
            return f.format(statistics.mean(xs)) + (f" ±{statistics.pstdev(xs):.0f}" if len(xs) > 1 else "")
        print(f"{label:10} {fmt(r['seconds']):>16} {fmt(r['turns']):>10} {fmt(r['tokens']):>20} "
              f"{statistics.mean(r['cost']):>14.4f} {r['acertos']:>8}")
    base, m = rows["sem mapa"], rows["com mapa"]
    if statistics.mean(base["tokens"]):
        delta = 1 - statistics.mean(m["tokens"]) / statistics.mean(base["tokens"])
        print(f"\nTokens com mapa: {delta:+.0%} de economia vs. sem mapa (média de {a.runs} execuções).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
