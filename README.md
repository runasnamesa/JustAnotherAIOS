# JustAnotherAIOS

Um "sistema operacional" pessoal em cima do Claude Code: **memória** que o Claude navega
sozinho, o **mesmo agente** no laptop e numa VPS que nunca dorme, **rotinas** que rodam com
o laptop fechado e um **painel** que só mostra — tudo em arquivos simples que você controla.

Inspirado no framework **MAPS** (Memory · Agent · Pulse · Screen) do vídeo "PAV OS — Agentic OS".

```
                ┌──────────── GitHub (repo privado) ────────────┐
                │   sync a cada 5 min, nos dois sentidos        │
        ┌───────┴────────┐                             ┌────────┴────────┐
        │  Mac/PC        │◄──── Tailscale (privada) ──►│  VPS            │
        │  Claude Code   │                             │  Claude Code    │
        │  painel        │                             │  rotinas 24/7   │
        │  rotinas locais│                             │  bot Telegram   │
        └────────────────┘                             │  só rascunha    │
                                                       └─────────────────┘
```

## As quatro camadas

| Camada | O que é aqui | Pergunta de teste |
|---|---|---|
| **Memory** | `CLAUDE.md` (só ponteiros) → `areas/*/CLAUDE.md` (placas) → notas. `map/MAP.md` gerado. | O Claude acha qualquer fato em 2 saltos? |
| **Agent** | O mesmo Claude Code no Mac e na VPS, mesma pasta via git. VPS travada: lê e rascunha, não envia. | Algo roda com o laptop fechado? |
| **Pulse** | `pulse/routines.toml` + `python -m aios pulse` a cada 5 min em cada máquina. | Uma rotina quebrada consegue queimar a cota? (não: trava após 3 falhas + teto diário) |
| **Screen** | `screen/` + `python -m aios serve`. Lê arquivos a cada requisição. | Se o painel morrer, você perde algo? (não) |

## Começo rápido (5 minutos, só no seu computador)

```bash
git clone <este repo> ~/JustAnotherAIOS && cd ~/JustAnotherAIOS
python3 -m aios brain        # gera map/MAP.md e map/graph.json
python3 -m aios lint         # checa placas, links e saltos (falha alto)
python3 -m aios serve        # painel em http://127.0.0.1:8765
claude                       # e rode /interview para preencher a memória com seus dados
```

Requisitos: Python 3.11+ (só biblioteca padrão) e [Claude Code](https://code.claude.com).
Opcional: `faster-whisper` (voz no Telegram).

## Comandos

```
python3 -m aios brain | lint | pulse | tick | drain | status
python3 -m aios run routine morning-digest     # enfileira (roda no host da rotina)
python3 -m aios run skill brain-build
python3 -m aios reset NOME                     # destrava rotina pausada por falhas
python3 -m aios serve [--bind IP] [--port N]
python3 -m aios telegram                       # bot (VPS)
python3 -m aios export painel.html             # painel como HTML único (foto estática, sem servidor)
python3 -m aios.measure "pergunta" --expect areas/x.md --runs 2   # mapa ajuda mesmo?
python3 -m unittest discover -s tests -t .     # testes
```

## Ordem recomendada (e por quê)

1. **Memory primeiro.** `/interview` → lint verde → `/calibrate` para medir. Sem mapa bom, o resto
   só automatiza confusão.
2. **Pulse no Mac** com 1–2 rotinas `kind = "script"` (custo zero) para validar o ciclo.
3. **VPS + Tailscale + travas** (docs/SETUP.md). Só então rotinas `claude` sem supervisão.
4. **Telegram.**
5. **Screen por último** — é o que menos gera valor por hora investida.

Detalhes: [docs/SETUP.md](docs/SETUP.md) · [docs/ARQUITETURA.md](docs/ARQUITETURA.md) ·
[docs/ANALISE.md](docs/ANALISE.md) (riscos e o que eu mudaria em relação ao vídeo).
