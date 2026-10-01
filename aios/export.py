"""export: gera o painel como um único HTML estático (snapshot + arquivos embutidos).

Serve para ver o painel sem servidor (abrir no celular, mandar para alguém, publicar como
artefato). É uma foto: não atualiza sozinho e os botões só simulam a fila.

    python -m aios export saida.html            # documento completo
    python -m aios export saida.html --fragment # sem <!doctype>/<html> (para artefatos)
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import status
from .config import ROOT
from .serve import READABLE_PREFIXES

SCREEN = "screen"


def embedded_files(root: Path) -> dict[str, str]:
    files = {}
    for prefix in READABLE_PREFIXES:
        base = root / prefix
        paths = [base] if base.is_file() else sorted(base.rglob("*")) if base.is_dir() else []
        for p in paths:
            if p.is_file() and p.suffix in (".md", ".toml"):
                files[p.relative_to(root).as_posix()] = p.read_text(encoding="utf-8")
    return files


def _script_json(obj) -> str:
    # impede que um "</script>" dentro de uma nota feche a tag
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def render(root: Path = ROOT, label: str = "estático", fragment: bool = False) -> str:
    html = (root / SCREEN / "index.html").read_text(encoding="utf-8")
    css = (root / SCREEN / "style.css").read_text(encoding="utf-8")
    js = (root / SCREEN / "app.js").read_text(encoding="utf-8")
    data = {"label": label, "snapshot": status.snapshot(root), "files": embedded_files(root)}

    html = html.replace('<link rel="stylesheet" href="style.css">', f"<style>\n{css}</style>")
    html = html.replace('<script src="app.js"></script>', f"<script>\n{js}</script>")
    html = html.replace("<!--DATA-->", f"<script>window.AIOS_STATIC = {_script_json(data)};</script>")
    if fragment:
        head = re.search(r"<!--HEAD-->(.*?)<!--/HEAD-->", html, re.S).group(1)
        body = re.search(r"<body>(.*)</body>", html, re.S).group(1)
        return head.strip() + "\n" + body.strip() + "\n"
    return html
