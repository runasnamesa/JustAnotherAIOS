"""Leitura da memória (o "vault"): notas Markdown, roteadores CLAUDE.md, links e saltos.

Convenções:
- `CLAUDE.md` na raiz é o roteador mestre. Cada pasta em `areas/` tem o seu `CLAUDE.md`
  (arquivo-placa / signpost) dizendo o que existe ali e quando abrir cada coisa.
- Nota = qualquer outro `.md` dentro de `areas/`. Frontmatter opcional entre `---`
  com `summary:` (uma linha) e `tags:`.
- Links: `[[caminho/da-nota]]` (relativo à raiz, sem `.md`) ou `[texto](caminho.md)`.
"""
from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

ROOT_ROUTER = "CLAUDE.md"
AREAS_DIR = "areas"

_WIKI = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
_MDLINK = re.compile(r"\[[^\]]*\]\(([^)#\s]+\.md)(?:#[^)]*)?\)")
_HEADING = re.compile(r"^#\s+(.+)$", re.M)


@dataclass
class Note:
    path: str  # relativo à raiz, com "/"
    title: str
    summary: str
    area: str
    is_router: bool
    tags: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)  # alvos resolvidos (existentes)
    broken: list[str] = field(default_factory=list)  # alvos que não existem


def _split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    meta = {}
    for line in text[4:end].splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip('"').strip("'")
    return meta, text[end + 4:].lstrip("\n")


def _first_paragraph(body: str) -> str:
    for block in re.split(r"\n\s*\n", body):
        line = " ".join(block.split())
        if line and not line.startswith(("#", "|", "-", "*", ">", "```", "<!--")):
            return line[:160]
    return ""


def _resolve(target: str, src: Path, root: Path) -> Path:
    target = target.strip()
    if not target.endswith(".md"):
        target += ".md"
    # wikilinks são relativos à raiz; links markdown relativos ao arquivo
    candidate = (src.parent / target) if target.startswith(".") else (root / target)
    if not candidate.exists() and not target.startswith("."):
        candidate = src.parent / target
    return candidate.resolve()


def area_of(rel: str) -> str:
    parts = rel.split("/")
    return parts[1] if len(parts) > 2 and parts[0] == AREAS_DIR else "root"


def load(root: Path) -> dict[str, Note]:
    root = root.resolve()
    files = [root / ROOT_ROUTER] if (root / ROOT_ROUTER).exists() else []
    if (root / AREAS_DIR).is_dir():
        files += sorted((root / AREAS_DIR).rglob("*.md"))
    notes: dict[str, Note] = {}
    for f in files:
        rel = f.relative_to(root).as_posix()
        meta, body = _split_frontmatter(f.read_text(encoding="utf-8"))
        m = _HEADING.search(body)
        title = meta.get("title") or (m.group(1).strip() if m else f.stem)
        summary = meta.get("summary") or _first_paragraph(body[m.end():] if m else body)
        tags = [t.strip() for t in meta.get("tags", "").strip("[]").split(",") if t.strip()]
        note = Note(rel, title, summary, area_of(rel), f.name == "CLAUDE.md", tags)
        for target in _WIKI.findall(body) + _MDLINK.findall(body):
            resolved = _resolve(target, f, root)
            try:
                r = resolved.relative_to(root).as_posix()
            except ValueError:
                note.broken.append(target)
                continue
            if resolved.exists():
                if r not in note.links and r != rel:
                    note.links.append(r)
            else:
                note.broken.append(target)
        notes[rel] = note
    return notes


def hops_from_root(notes: dict[str, Note]) -> dict[str, int]:
    """Distância (em arquivos abertos) do roteador mestre até cada nota, seguindo links."""
    if ROOT_ROUTER not in notes:
        return {}
    dist = {ROOT_ROUTER: 0}
    queue = deque([ROOT_ROUTER])
    while queue:
        cur = queue.popleft()
        for nxt in notes[cur].links:
            if nxt in notes and nxt not in dist:
                dist[nxt] = dist[cur] + 1
                queue.append(nxt)
    return dist
