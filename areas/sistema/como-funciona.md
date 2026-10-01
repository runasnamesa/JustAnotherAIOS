---
summary: Arquitetura do AIOS — Memory, Agent, Pulse, Screen; máquinas, sync e travas de segurança.
tags: [sistema]
---
# Como funciona

Quatro camadas (MAPS): **Memory** (CLAUDE.md → placas → notas, mais o MAP.md gerado),
**Agent** (o mesmo Claude Code no Mac e na VPS, pasta sincronizada por git a cada 5 min),
**Pulse** (`pulse/routines.toml`, um scheduler por máquina) e **Screen** (`screen/`, só mostra).
Detalhes em `docs/ARQUITETURA.md`.
