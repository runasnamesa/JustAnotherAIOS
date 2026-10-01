"""Bot do Telegram (roda na VPS): mensagem/voz → texto → Claude Code → resposta no chat.

- Só responde aos chat_ids em AIOS_TELEGRAM_ALLOWED (lista separada por vírgula). Qualquer
  outro remetente é ignorado em silêncio.
- Voz: transcrita localmente com faster-whisper, se instalado (`pip install faster-whisper`).
- O Claude roda com as permissões do `.claude/settings.local.json` da VPS
  (ver ops/vps/settings.local.json): pode ler e rascunhar, não pode enviar/compartilhar/apagar.
- `send_message` também é usado pelas rotinas (ex.: morning-digest) via `python -m aios notify`.

Variáveis: AIOS_TELEGRAM_TOKEN, AIOS_TELEGRAM_ALLOWED.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

from .config import ROOT, claude_bin

API = "https://api.telegram.org"
MAX_LEN = 4000


def _token() -> str:
    tok = os.environ.get("AIOS_TELEGRAM_TOKEN", "")
    if not tok:
        raise SystemExit("defina AIOS_TELEGRAM_TOKEN")
    return tok


def allowed_chats() -> set[int]:
    raw = os.environ.get("AIOS_TELEGRAM_ALLOWED", "")
    return {int(x) for x in raw.split(",") if x.strip()}


def _call(method: str, http_timeout: int = 40, **params) -> dict:
    data = urllib.parse.urlencode(params).encode()
    with urllib.request.urlopen(f"{API}/bot{_token()}/{method}", data=data, timeout=http_timeout) as r:
        return json.loads(r.read())


def send_message(text: str, chat_id: int | None = None) -> None:
    _token()
    targets = [chat_id] if chat_id else sorted(allowed_chats())
    if not targets:  # sem destino não é sucesso: o heartbeat ficaria verde sem avisar ninguém
        raise SystemExit("defina AIOS_TELEGRAM_ALLOWED com seu chat_id")
    for cid in targets:
        for i in range(0, max(len(text), 1), MAX_LEN):
            _call("sendMessage", chat_id=cid, text=text[i:i + MAX_LEN] or "(vazio)")


def _transcribe(file_id: str) -> str:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return ""
    info = _call("getFile", file_id=file_id)["result"]
    with tempfile.NamedTemporaryFile(suffix=".oga") as tmp:
        url = f"{API}/file/bot{_token()}/{info['file_path']}"
        with urllib.request.urlopen(url, timeout=60) as r:
            tmp.write(r.read())
        tmp.flush()
        model = WhisperModel(os.environ.get("AIOS_WHISPER_MODEL", "small"), device="cpu",
                             compute_type="int8")
        segments, _ = model.transcribe(tmp.name, vad_filter=True)
        return " ".join(s.text.strip() for s in segments)


def ask_claude(question: str, root: Path = ROOT) -> str:
    prompt = ("Você está respondendo pelo Telegram, no celular. Comece pelo mapa "
              "(CLAUDE.md → map/MAP.md), abra só o necessário e responda curto. "
              "Nunca envie nada para terceiros: no máximo deixe um rascunho.\n\n"
              f"Pergunta: {question}")
    proc = subprocess.run([claude_bin(), "-p", prompt], cwd=root, capture_output=True,
                          text=True, timeout=600)
    return proc.stdout.strip() or f"(sem resposta; exit {proc.returncode})\n{proc.stderr[-500:]}"


def handle(update: dict, root: Path = ROOT) -> str | None:
    msg = update.get("message") or {}
    chat_id = msg.get("chat", {}).get("id")
    if chat_id not in allowed_chats():
        return None
    text = msg.get("text", "")
    if not text and msg.get("voice"):
        text = _transcribe(msg["voice"]["file_id"])
        if not text:
            return "Não consegui transcrever (faster-whisper não instalado?). Mande em texto."
    if not text:
        return None
    return ask_claude(text, root)


def poll(root: Path = ROOT) -> None:
    if not allowed_chats():
        raise SystemExit("defina AIOS_TELEGRAM_ALLOWED com seu chat_id (o bot ignora todos os outros)")
    offset = 0
    print("bot ouvindo…")
    while True:
        try:
            updates = _call("getUpdates", http_timeout=65, offset=offset, timeout=50)
            for u in updates.get("result", []):
                offset = u["update_id"] + 1
                reply = handle(u, root)
                if reply:
                    send_message(reply, u["message"]["chat"]["id"])
        except Exception as e:  # rede cai; o bot não pode morrer por isso
            print(f"erro: {e}; tentando de novo em 10s")
            time.sleep(10)
