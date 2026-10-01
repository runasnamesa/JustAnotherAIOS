"""lint-routers: a checagem noturna que impede o mapa de ficar velho.

Falha (exit 1) quando:
- uma pasta de `areas/` não tem seu CLAUDE.md (placa);
- o CLAUDE.md raiz não aponta para o roteador de alguma área;
- algum link aponta para arquivo que não existe (nota movida/renomeada);
- alguma nota está a mais de 2 saltos do CLAUDE.md raiz, ou inalcançável;
- map/MAP.md está desatualizado em relação às notas;
- o CLAUDE.md raiz passou do limite de linhas (ele guarda ponteiros, não fatos).
Avisa (sem falhar) quando uma nota não tem resumo — o mapa fica pobre sem ele.
"""
from __future__ import annotations

from pathlib import Path

from . import vault
from .brain import MAP_FILE, render_map
from .config import ROOT, load_settings

MAX_HOPS = 2


def check(root: Path = ROOT) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    notes = vault.load(root)
    if vault.ROOT_ROUTER not in notes:
        return [f"{vault.ROOT_ROUTER} raiz não existe"], []

    max_lines = load_settings(root).get("memory", {}).get("root_max_lines", 60)
    n_lines = len((root / vault.ROOT_ROUTER).read_text(encoding="utf-8").splitlines())
    if n_lines > max_lines:
        errors.append(f"CLAUDE.md raiz tem {n_lines} linhas (limite {max_lines}): mova fatos para as áreas")

    areas = root / vault.AREAS_DIR
    for folder in sorted(p for p in areas.rglob("*") if p.is_dir()) if areas.is_dir() else []:
        rel = folder.relative_to(root).as_posix()
        if not (folder / "CLAUDE.md").exists() and any(folder.glob("*.md")):
            errors.append(f"{rel}/ tem notas mas não tem CLAUDE.md (placa)")
        if folder.parent == areas and f"{rel}/CLAUDE.md" not in notes[vault.ROOT_ROUTER].links:
            errors.append(f"CLAUDE.md raiz não aponta para {rel}/CLAUDE.md")

    for n in notes.values():
        for b in n.broken:
            errors.append(f"{n.path}: link quebrado → {b}")

    hops = vault.hops_from_root(notes)
    for path, n in sorted(notes.items()):
        h = hops.get(path)
        if h is None:
            errors.append(f"{path}: inalcançável a partir do CLAUDE.md raiz (nenhuma placa aponta para ela)")
        elif h > MAX_HOPS:
            errors.append(f"{path}: está a {h} saltos (máx {MAX_HOPS}); aponte-a no roteador da área")
        if not n.is_router and not n.summary:
            warnings.append(f"{path}: sem resumo (adicione `summary:` no frontmatter)")

    map_path = root / MAP_FILE
    if not map_path.exists() or map_path.read_text(encoding="utf-8") != render_map(notes) + "\n":
        errors.append(f"{MAP_FILE} desatualizado: rode `python -m aios brain`")
    return errors, warnings
