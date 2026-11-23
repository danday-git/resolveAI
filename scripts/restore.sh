#!/usr/bin/env bash
# Restores a backup made by scripts/backup.sh into a running Compose stack. The API and the
# worker are stopped while it runs.
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

# Nothing may read or write while the data is replaced: an upload accepted in between would
# keep its database row and lose its file. Both come back however the restore ends.
"${compose[@]}" stop api worker
trap '"${compose[@]}" start api worker' EXIT
db() { "${compose[@]}" exec -T db "$@"; }
# Into an empty database, swapped in only once it loaded: dropping objects in place fails on
# tables added since the backup, and a failed restore must leave the current data alone.
db dropdb -U resolveai --if-exists resolveai_restore
db dropdb -U resolveai --if-exists resolveai_old
db createdb -U resolveai resolveai_restore
db pg_restore -U resolveai -d resolveai_restore --no-owner --exit-on-error <"$dump"
# Both renames in one transaction, so there is a complete database under the name at any
# moment. The current data is dropped only after the backup has taken its place.
# shortcut: another open session on the database (a psql left running) stops the restore here
# with the data untouched; close it and run again, or end such sessions first if that recurs.
db psql -U resolveai -d postgres -q -v ON_ERROR_STOP=1 --single-transaction \
	-c 'ALTER DATABASE resolveai RENAME TO resolveai_old' \
	-c 'ALTER DATABASE resolveai_restore RENAME TO resolveai'
db dropdb -U resolveai --force resolveai_old
run=("${compose[@]}" run --rm --no-deps -T api)
if [ -f "$uploads" ]; then
	"${run[@]}" sh -c 'find /data/uploads -mindepth 1 -delete && tar -C /data/uploads -xzf -' <"$uploads"
else
	echo "warning: $uploads not found, uploaded files were not restored" >&2
fi
"${run[@]}" alembic upgrade head
echo "restored $(basename "$dump")"
