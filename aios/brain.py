"""brain-build: gera o mapa (nível 3 da memória) e o grafo que o painel desenha.

Saídas (ambas geradas, nunca editadas à mão):
- map/MAP.md     — índice compacto: área → nota → resumo de uma linha. O Claude lê
                   CLAUDE.md → MAP.md → nota certa (2 saltos) em vez de abrir 20 arquivos.
- map/graph.json — nós (roteadores, notas, rotinas, skills) e arestas (links, "rotina usa",
                   "skill toca") para o painel.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from . import vault
from .config import ROOT
from .pulse import load_routines

MAP_FILE = "map/MAP.md"
GRAPH_FILE = "map/graph.json"
_PATH_REF = re.compile(r"\b(areas/[\w./-]+\.md)\b")


def _skills(root: Path) -> list[dict]:
    out = []
    for f in sorted((root / ".claude" / "commands").glob("*.md")):
        text = f.read_text(encoding="utf-8")
        meta, body = vault._split_frontmatter(text)
        out.append({"name": f.stem, "path": f.relative_to(root).as_posix(),
                    "summary": meta.get("description", "") or vault._first_paragraph(body),
                    "model": meta.get("model", ""), "host": meta.get("host", ""),
                    "refs": sorted(set(_PATH_REF.findall(text)))})
    return out


def render_map(notes: dict[str, vault.Note]) -> str:
    by_area: dict[str, list[vault.Note]] = defaultdict(list)
    for n in notes.values():
        if n.path != vault.ROOT_ROUTER:
            by_area[n.area].append(n)
    lines = ["# MAP — índice gerado da memória", "",
             "> Gerado por `python -m aios brain`. Não edite à mão: edite as notas e rode de novo.",
             "> Uso: ache a linha certa aqui e abra só aquele arquivo.", ""]
    for area in sorted(by_area):
        lines.append(f"## {area}")
        for n in sorted(by_area[area], key=lambda n: (not n.is_router, n.path)):
            mark = "↳ roteador" if n.is_router else n.title
            summary = f" — {n.summary}" if n.summary else ""
            lines.append(f"- `{n.path}` · {mark}{summary}")
        lines.append("")
    return "\n".join(lines)


def build_graph(root: Path, notes: dict[str, vault.Note]) -> dict:
    hops = vault.hops_from_root(notes)
    nodes, links = [], []
    for n in notes.values():
        kind = "root" if n.path == vault.ROOT_ROUTER else ("router" if n.is_router else "note")
        nodes.append({"id": n.path, "kind": kind, "title": n.title, "area": n.area,
                      "summary": n.summary, "tags": n.tags, "hops": hops.get(n.path)})
        links += [{"source": n.path, "target": t, "kind": "link"} for t in n.links]
    for r in load_routines(root):
        rid = f"routine:{r.name}"
        nodes.append({"id": rid, "kind": "routine", "title": r.name, "area": "sistema",
                      "summary": r.purpose, "host": r.host, "schedule": r.schedule})
        refs = set()
        if r.kind == "claude":
            refs |= set(_PATH_REF.findall((root / r.prompt).read_text(encoding="utf-8")))
        if r.kind == "skill":
            links.append({"source": rid, "target": f"skill:{r.skill}", "kind": "runs"})
        links += [{"source": rid, "target": p, "kind": "uses"} for p in sorted(refs) if p in notes]
    for s in _skills(root):
        sid = f"skill:{s['name']}"
        nodes.append({"id": sid, "kind": "skill", "title": f"/{s['name']}", "area": "sistema",
                      "summary": s["summary"], "model": s["model"], "host": s["host"]})
        links += [{"source": sid, "target": p, "kind": "uses"} for p in s["refs"] if p in notes]
    # a área de rotinas/skills passa a ser a da nota que mais tocam (o painel colore por área)
    by_id = {n["id"]: n for n in nodes}
    for n in nodes:
        if n["kind"] in ("routine", "skill"):
            areas = [by_id[l["target"]]["area"] for l in links
                     if l["source"] == n["id"] and l["target"] in notes]
            if areas:
                n["area"] = max(set(areas), key=areas.count)
    return {"generated_at": datetime.now().replace(microsecond=0).isoformat(),
            "nodes": nodes, "links": links}


def build(root: Path = ROOT) -> dict:
    notes = vault.load(root)
    (root / "map").mkdir(exist_ok=True)
    (root / MAP_FILE).write_text(render_map(notes) + "\n", encoding="utf-8")
    graph = build_graph(root, notes)
    (root / GRAPH_FILE).write_text(json.dumps(graph, indent=1, ensure_ascii=False) + "\n",
                                   encoding="utf-8")
    return {"notes": len(notes), "nodes": len(graph["nodes"]), "links": len(graph["links"])}
