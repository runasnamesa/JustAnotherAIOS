"""Configuração compartilhada: raiz do projeto, host atual e binário do Claude Code."""
from __future__ import annotations

import os
import socket
import tomllib
from pathlib import Path

ROOT = Path(os.environ.get("AIOS_ROOT", Path(__file__).resolve().parent.parent))


def load_settings(root: Path = ROOT) -> dict:
    path = root / "aios.toml"
    return tomllib.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def current_host(root: Path = ROOT) -> str:
    """Nome lógico desta máquina ("mac", "vps"...). AIOS_HOST tem prioridade;
    senão procura o hostname real em [hosts] do aios.toml."""
    if os.environ.get("AIOS_HOST"):
        return os.environ["AIOS_HOST"]
    hostname = socket.gethostname().split(".")[0].lower()
    for name, aliases in load_settings(root).get("hosts", {}).items():
        if hostname in [a.lower() for a in aliases]:
            return name
    return hostname


def claude_bin() -> str:
    return os.environ.get("AIOS_CLAUDE_BIN", "claude")
