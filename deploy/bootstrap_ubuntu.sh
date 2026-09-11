#!/usr/bin/env bash
# Подготовка чистой Ubuntu к запуску «Пути героя».
#
# Облачный сервер приезжает голым: без Docker, без swap, с открытыми наружу
# портами. Каждый пункт ниже приходилось делать руками и вспоминать по памяти —
# отсюда скрипт. Он идемпотентен: повторный запуск ничего не ломает.
#
#   sudo bash deploy/bootstrap_ubuntu.sh
#
set -euo pipefail

SWAP_SIZE="${SWAP_SIZE:-2G}"
TIMEZONE="${TIMEZONE:-Europe/Moscow}"
SSH_PORT="${SSH_PORT:-22}"

log() { printf '\n\033[1;35m==> %s\033[0m\n' "$1"; }

if [ "$(id -u)" -ne 0 ]; then
  echo "Запускать от root: sudo bash deploy/bootstrap_ubuntu.sh" >&2
  exit 1
fi

log "Часовой пояс: $TIMEZONE"
# Расписание Celery расписано в московском времени; без этого шага задачи
# «ночью» будут выполняться по UTC, то есть на три часа раньше.
timedatectl set-timezone "$TIMEZONE"

log "Обновление пакетов"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get upgrade -y -qq
apt-get install -y -qq ca-certificates curl gnupg git ufw

log "Docker"
if command -v docker >/dev/null 2>&1; then
  echo "Docker уже установлен: $(docker --version)"
else
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -qq
  apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
systemctl enable --now docker

log "Swap $SWAP_SIZE"
# На 4 ГБ сборка фронта (vite) и установка Chromium для Playwright упираются
# в память, и сборка падает с «killed» без внятной причины.
if swapon --show | grep -q '/swapfile'; then
  echo "swap уже подключён"
else
  fallocate -l "$SWAP_SIZE" /swapfile
  chmod 600 /swapfile
  mkswap /swapfile >/dev/null
  swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

log "Файрвол"
# Наружу нужны только 80 и 443: базу и Redis прод-стек не публикует вовсе.
ufw allow "$SSH_PORT"/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
ufw status verbose

log "Готово"
cat <<'NEXT'
Дальше:
  1. git clone <репозиторий> /opt/hero_path && cd /opt/hero_path
  2. cp .env.prod.example .env.prod  и заполнить (см. docs/DEPLOY_TIMEWEB.md)
  3. docker compose -p hero_prod -f docker-compose.prod.yml --env-file .env.prod up -d --build

Проверить, что Docker жив:  docker run --rm hello-world
NEXT
