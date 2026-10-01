"""Screen: servidor do painel. Mostra, nunca guarda.

- GET  /                 → screen/index.html (+ assets estáticos de screen/)
- GET  /api/snapshot     → status.snapshot() lido dos arquivos na hora
- GET  /api/file?path=…  → conteúdo de uma nota/rotina/skill (somente leitura, caminhos permitidos)
- POST /api/run          → grava um pedido em runs/queue/ (o runner do host certo executa)

Segurança: escuta em 127.0.0.1 por padrão. Para usar pelo celular, rode com
`--bind <ip-tailscale>` — só dispositivos da sua tailnet alcançam. O POST exige o cabeçalho
`X-AIOS: 1` (um site qualquer aberto no navegador não consegue enviá-lo sem preflight CORS,
que este servidor nunca autoriza) e, se `AIOS_TOKEN` estiver definido, `X-AIOS-Token`.
"""
from __future__ import annotations

import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import status
from .config import ROOT
from .pulse import enqueue, load_routines
from .vault import _split_frontmatter

READABLE_PREFIXES = ("CLAUDE.md", "areas/", "map/", "pulse/", ".claude/commands/")


def _skill_hosts(root: Path) -> dict[str, str]:
    """nome da skill → host onde roda (frontmatter `host:`, padrão "mac")."""
    out = {}
    for p in (root / ".claude" / "commands").glob("*.md"):
        meta, _ = _split_frontmatter(p.read_text(encoding="utf-8"))
        out[p.stem] = meta.get("host", "mac")
    return out


def make_handler(root: Path):
    screen = (root / "screen").resolve()
    token = os.environ.get("AIOS_TOKEN", "")

    class Handler(BaseHTTPRequestHandler):
        server_version = "aios"

        def log_message(self, fmt, *args):  # silencioso; erros ainda aparecem
            pass

        def _send(self, code: int, body: bytes, ctype: str = "application/json") -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, obj) -> None:
            self._send(code, json.dumps(obj, ensure_ascii=False).encode())

        def do_GET(self):
            url = urlparse(self.path)
            if url.path == "/api/snapshot":
                return self._json(200, status.snapshot(root))
            if url.path == "/api/file":
                rel = parse_qs(url.query).get("path", [""])[0]
                target = (root / rel).resolve()
                ok = rel.startswith(READABLE_PREFIXES) and target.is_file() and \
                    target.is_relative_to(root.resolve()) and ".." not in rel
                if not ok:
                    return self._json(404, {"error": "arquivo não permitido"})
                return self._json(200, {"path": rel, "text": target.read_text(encoding="utf-8")})
            rel = "index.html" if url.path in ("", "/") else url.path.lstrip("/")
            target = (screen / rel).resolve()
            if not target.is_relative_to(screen) or not target.is_file():
                return self._send(404, b"not found", "text/plain")
            ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            self._send(200, target.read_bytes(), ctype)

        def do_POST(self):
            if urlparse(self.path).path != "/api/run":
                return self._json(404, {"error": "rota desconhecida"})
            if self.headers.get("X-AIOS") != "1" or (token and self.headers.get("X-AIOS-Token") != token):
                return self._json(403, {"error": "proibido"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                req = json.loads(self.rfile.read(min(length, 10_000)) or b"{}")
            except ValueError:
                return self._json(400, {"error": "json inválido"})
            kind, name, host = req.get("kind"), req.get("name"), req.get("host")
            routines = {r.name: r for r in load_routines(root)}
            if kind == "routine" and name in routines:
                host = routines[name].host  # rotina sempre roda na máquina dela
            elif kind == "skill" and name in (skills := _skill_hosts(root)):
                host = skills[name]
            else:
                return self._json(400, {"error": f"{kind} desconhecido: {name}"})
            path = enqueue(root, kind=kind, name=name, host=host, source="screen")
            self._json(202, {"queued": path.name, "host": host})

    return Handler


def serve(root: Path = ROOT, bind: str = "127.0.0.1", port: int = 8765) -> None:
    httpd = ThreadingHTTPServer((bind, port), make_handler(root))
    print(f"AIOS screen em http://{bind}:{port}  (Ctrl+C para sair)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
