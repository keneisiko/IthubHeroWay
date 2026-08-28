#!/usr/bin/env sh
# Дамп прод-базы в ./backups. Запускать с хоста, где поднят прод-стек:
#   sh scripts/backup_db.sh
# Для регулярности — в cron хоста, например ежедневно в 03:30:
#   30 3 * * * cd /srv/hero-path && sh scripts/backup_db.sh >> /var/log/hero_path_backup.log 2>&1
set -eu

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-.env.prod}"
KEEP_DAYS="${KEEP_DAYS:-14}"

STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="/backups/hero_path_${STAMP}.sql.gz"

# Дамп пишется внутрь контейнера в /backups — этот каталог смонтирован
# с хоста (./backups), поэтому файл сразу оказывается снаружи.
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T db \
    sh -c "pg_dump -U \$POSTGRES_USER -d \$POSTGRES_DB | gzip > $OUT"

echo "Дамп готов: ./backups/hero_path_${STAMP}.sql.gz"

# Старые дампы удаляем, иначе диск кончится молча.
find ./backups -name 'hero_path_*.sql.gz' -mtime "+${KEEP_DAYS}" -delete
echo "Удалены дампы старше ${KEEP_DAYS} дней."
