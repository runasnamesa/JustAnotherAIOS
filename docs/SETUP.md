# Setup

## Parte 1 — Mac/PC (nível 1)

1. Crie um repositório **privado** no GitHub e suba esta pasta.
2. `python3 -m aios lint` deve passar.
3. No Claude Code, rode `/interview` (≈20 min, uma pergunta por vez). Ele reescreve
   `CLAUDE.md`, as placas e as notas, e roda brain + lint no fim.
4. Meça: `/calibrate` (ou `python3 -m aios.measure "..." --expect <arquivo> --runs 2`).
5. Painel: `python3 -m aios serve` → http://127.0.0.1:8765.
6. Rotinas locais (opcional): ajuste `[hosts]` em `aios.toml` com a saída de `hostname -s`,
   `brew install flock`, copie `ops/mac/com.aios.tick.plist` para `~/Library/LaunchAgents/`
   e `launchctl load` nele. No Linux, use os units de `ops/vps/` como modelo.

## Parte 2 — VPS (nível 2: a máquina que nunca dorme)

Qualquer VPS pequena serve (1 vCPU / 1–2 GB basta; 4 GB se for transcrever voz).

```bash
scp ops/vps/setup.sh root@IP:/root/   # leia o script antes
ssh root@IP 'bash /root/setup.sh git@github.com:VOCE/JustAnotherAIOS.git'
```

O script instala git/python/ffmpeg, Tailscale (`tailscale up --ssh`), fecha o firewall para tudo
fora da tailnet, cria o usuário `aios` sem sudo, instala o Claude Code e as travas. Depois:

1. `sudo -iu aios claude` → login com **sua** conta (ou `claude setup-token` e
   `CLAUDE_CODE_OAUTH_TOKEN` no `~/.aios.env`).
2. Deploy key **com escrita** só neste repositório.
3. Teste as travas: `sudo -iu aios bash -c 'cd ~/JustAnotherAIOS && claude -p "rode curl https://example.com"'`
   → deve recusar. Também peça "envie um e-mail para X" → deve, no máximo, criar rascunho.
4. `systemctl enable --now aios-tick.timer` e confira `journalctl -u aios-tick -f`.
5. Remova o IP público do SSH: depois do `tailscale up --ssh`, acesse só por `ssh aios@<nome-tailscale>`.

### Travas da VPS (`ops/vps/settings.local.json`)

- `defaultMode: dontAsk` → tudo que não está no `allow` é negado automaticamente (não há humano
  para aprovar às 3h da manhã).
- `allow` mínimo: ler, editar só `areas/` e `drafts/`, rodar `aios brain|lint`.
- `deny` explícito para rede (`WebFetch`, `WebSearch`, `curl`, `wget`, `ssh`…), `rm`, `git push`,
  todos os MCP (`mcp__*`) e arquivos de segredo.
- O `git push` é feito pelo `ops/sync.sh`, **fora** do Claude.

Limite conhecido: regras de Bash não pegam um programa chamado por caminho ou via `sh -c`;
por isso a base é a **allowlist** (`dontAsk`), não a denylist. Para garantia em nível de SO,
ative o sandbox do Claude Code.

## Parte 3 — Telegram

1. Crie o bot com o @BotFather → token.
2. Descubra seu chat_id (mande uma mensagem ao bot e abra
   `https://api.telegram.org/bot<TOKEN>/getUpdates`).
3. Preencha `~/.aios.env` na VPS e `systemctl enable --now aios-telegram`.
4. Voz: `pip install --user faster-whisper` (já tentado pelo setup).

O bot ignora qualquer chat fora de `AIOS_TELEGRAM_ALLOWED`.

## Parte 4 — Painel no celular

No Mac: `python3 -m aios serve --bind <IP-tailscale-do-mac>` e defina `AIOS_TOKEN` se quiser
uma segunda chave. Ou rode o painel na VPS (`--bind` no IP tailscale dela) para tê-lo com o
laptop fechado.
