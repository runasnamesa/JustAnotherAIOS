#!/usr/bin/env bash
# Sincroniza a pasta com o repositório privado nos dois sentidos. Rodado a cada 5 min
# (antes e depois do pulse) em cada máquina. Conflito → para e avisa; nunca força.
set -euo pipefail
cd "$(dirname "$0")/.."
host="${AIOS_HOST:-$(hostname -s)}"

git add -A
git diff --cached --quiet || git commit -q -m "sync($host): $(date '+%Y-%m-%d %H:%M')"
if ! git pull -q --rebase --autostash; then
  git rebase --abort 2>/dev/null || true
  msg="⚠ AIOS sync em $host: conflito no git. Resolva à mão (git status)."
  echo "$msg" >&2
  echo "$msg" | python3 -m aios notify 2>/dev/null || true
  exit 1
fi
git push -q
