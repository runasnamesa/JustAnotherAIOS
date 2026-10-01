# Arquitetura

## Memory — três níveis

| Nível | Forma | Custo por pergunta |
|---|---|---|
| 1 | Pilha de pastas | Claude abre ~20 arquivos |
| 2 | Placas: `CLAUDE.md` em cada pasta dizendo o que tem e quando abrir | 2–3 arquivos |
| 3 | Mapa gerado (`map/MAP.md`): uma linha por nota com resumo | 1 índice + 1 nota |

Regras:
- `CLAUDE.md` raiz: ≤ 60 linhas (`aios.toml`), sem fatos, uma linha por área.
- Cada fato tem uma casa. Duplicar = apontar.
- Toda nota tem `summary:` no frontmatter — é o que entra no mapa.
- `aios lint` (rotina noturna `lint-routers`) falha se: pasta sem placa, área fora da raiz,
  link quebrado, nota a > 2 saltos ou inalcançável, MAP.md velho, raiz gorda.

## Agent

Mesmo Claude Code, mesma pasta, duas máquinas. A pasta viaja por git (`ops/sync.sh`):
`add -A → commit → pull --rebase --autostash → push`. Em conflito: aborta, avisa no Telegram,
não força. `ops/tick.sh` usa `flock` para não sobrepor ciclos.

## Pulse

`pulse/routines.toml` → cada rotina tem `schedule` (cron), `host` e `kind`:

- `script`: comando shell, custo zero.
- `claude`: `claude -p` com o prompt de `pulse/prompts/`.
- `skill`: `claude -p /skill`.

Ciclo a cada 5 min: `tick` (enfileira o que venceu desde o último tick deste host — se a máquina
dormiu, roda **uma vez** ao acordar, sem replay) → `drain` (executa a fila deste host).
Registros: `runs/done/*.json` (versionado, o painel lê) e `runs/log/` (local).
Estado por host: `runs/state-<host>.json` (um arquivo por máquina = sem conflito de git).

Proteções de custo: rotina pausa após `max_consecutive_failures` falhas seguidas
(`aios reset NOME` destrava); teto `max_runs_per_day` por host.

## Screen

Servidor stdlib. `GET /api/snapshot` monta tudo dos arquivos na hora; `GET /api/file` lê só
caminhos permitidos; `POST /api/run` **só grava um pedido** em `runs/queue/` — o runner do host
certo executa no próximo tick. O painel não tem banco, cache ou estado.

Arquivos que alimentam os painéis (todos em `areas/sistema/`):
`precisa-de-voce.md` (`- [ ] **Título** — detalhe`), `agenda.md` (`- AAAA-MM-DD HH:MM — texto`),
`resumo-do-dia.md` (escrito pela rotina `morning-digest`).

Vistas: **Anéis** (raiz no centro; placas, notas, rotinas e skills em anéis; setor por área) e
**Links** (força). Filtro por área, busca, clique → detalhes → "abrir" mostra o arquivo.
