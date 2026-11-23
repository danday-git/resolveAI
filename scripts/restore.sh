#!/usr/bin/env bash
# Restores a backup made by scripts/backup.sh into a running Compose stack.
#   scripts/restore.sh backups/resolveai-<stamp>.dump
# This REPLACES the current database and uploaded files.
set -euo pipefail
dump="$(realpath "${1:?usage: scripts/restore.sh <backup.dump>}")"
uploads="${dump%.dump}.uploads.tgz"
[ -f "$dump" ] || { echo "no such backup: $dump" >&2; exit 1; }
cd "$(dirname "$0")/.."
compose=(docker compose ${COMPOSE_ARGS:--f infra/docker-compose.yml --env-file .env})

if [ "${RESTORE_CONFIRM:-}" != "yes" ]; then
	read -r -p "Replace the current database and uploads with $(basename "$dump")? Type yes: " answer
	[ "$answer" = "yes" ] || { echo "cancelled"; exit 1; }
fi

# The worker must not ingest while the tables are being replaced.
"${compose[@]}" stop worker
"${compose[@]}" exec -T db pg_restore -U resolveai -d resolveai --clean --if-exists \
	--no-owner --single-transaction <"$dump"
if [ -f "$uploads" ]; then
	"${compose[@]}" exec -T api sh -c 'rm -rf /data/uploads/* && tar -C /data/uploads -xzf -' <"$uploads"
else
	echo "warning: $uploads not found, uploaded files were not restored" >&2
fi
"${compose[@]}" exec -T api alembic upgrade head
"${compose[@]}" start worker
echo "restored $(basename "$dump")"
