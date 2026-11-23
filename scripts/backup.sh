#!/usr/bin/env bash
# Backs up the database and the uploaded files of a running Compose stack.
#   scripts/backup.sh [backup-dir]         default ./backups, keeps the newest BACKUP_KEEP (14)
# Run it from cron on the host, and copy the directory off the machine.
set -euo pipefail
cd "$(dirname "$0")/.."
dir="${1:-backups}"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
compose=(docker compose ${COMPOSE_ARGS:--f infra/docker-compose.yml --env-file .env})
umask 077 # backups hold everything users uploaded
mkdir -p "$dir"

# Written to a temporary name first, so an interrupted run never leaves a file that looks complete.
"${compose[@]}" exec -T db pg_dump -U resolveai -d resolveai -Fc >"$dir/.db-$stamp.partial"
mv "$dir/.db-$stamp.partial" "$dir/resolveai-$stamp.dump"
"${compose[@]}" exec -T api tar -C /data/uploads -czf - . >"$dir/.uploads-$stamp.partial"
mv "$dir/.uploads-$stamp.partial" "$dir/resolveai-$stamp.uploads.tgz"

ls -1t "$dir"/resolveai-*.dump | tail -n +"$((${BACKUP_KEEP:-14} + 1))" | while read -r old; do
	rm -f "$old" "${old%.dump}.uploads.tgz"
done
echo "$dir/resolveai-$stamp.dump"
