#!/usr/bin/env bash
# Um ciclo completo: sync → pulse (enfileira + executa) → sync. Chamado a cada 5 min.
set -uo pipefail
cd "$(dirname "$0")/.."
exec 9>/tmp/aios-tick.lock
flock -n 9 || exit 0   # ciclo anterior ainda rodando (rotina longa): pula este
./ops/sync.sh || exit 1
python3 -m aios pulse
./ops/sync.sh
