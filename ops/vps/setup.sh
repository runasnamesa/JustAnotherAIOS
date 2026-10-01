#!/usr/bin/env bash
# Prepara uma VPS Ubuntu/Debian limpa. Rode como root. LEIA antes de rodar.
set -euo pipefail
REPO_URL="${1:?uso: setup.sh git@github.com:voce/JustAnotherAIOS.git}"
HOME_DIR=/home/aios
APP=$HOME_DIR/JustAnotherAIOS

apt-get update -q && apt-get install -yq git python3 python3-pip ffmpeg curl ufw util-linux

# Tailscale: a VPS só aparece na sua rede privada (laptop + celular + VPS)
curl -fsSL https://tailscale.com/install.sh | sh
tailscale up --ssh
ufw default deny incoming
ufw allow in on tailscale0
ufw --force enable

# usuário sem sudo para o agente
id aios >/dev/null 2>&1 || useradd -m -s /bin/bash aios
sudo -iu aios git clone "$REPO_URL" "$APP"
sudo -iu aios pip3 install --user --break-system-packages faster-whisper || true

# Claude Code, instalado para o usuário aios
sudo -iu aios bash -c 'curl -fsSL https://claude.ai/install.sh | bash'

install -m 600 -o aios -g aios "$APP/ops/vps/aios.env.example" "$HOME_DIR/.aios.env"
install -m 644 -o aios -g aios "$APP/ops/vps/settings.local.json" "$APP/.claude/settings.local.json"
cp "$APP"/ops/vps/aios-tick.service "$APP"/ops/vps/aios-tick.timer "$APP"/ops/vps/aios-telegram.service /etc/systemd/system/
systemctl daemon-reload

cat <<MSG
Falta (manual, de propósito):
  1. sudo -iu aios claude                 # login com SUA conta Claude (ou claude setup-token)
  2. sudo -iu aios ssh-keygen -t ed25519   # adicione ~/.ssh/id_ed25519.pub como deploy key COM escrita
  3. nano $HOME_DIR/.aios.env             # token do bot e seu chat_id
  4. sudo -iu aios bash -c 'cd $APP && AIOS_HOST=vps python3 -m aios lint'   # sanidade
  5. systemctl enable --now aios-tick.timer aios-telegram.service
MSG
