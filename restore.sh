#!/usr/bin/env bash
#
# Restore a backup produced by backup.sh. DESTRUCTIVE: overwrites the
# current database and media contents. Requires explicit confirmation.
#
# Usage:
#   bash restore.sh --list                 # show available backup timestamps
#   bash restore.sh 20260724T120000Z       # restore that backup (asks to confirm)
#   bash restore.sh 20260724T120000Z --yes # skip the confirmation prompt
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

export COMPOSE_PROJECT_NAME=annet_platform
ENV_FILE=".env"
BACKUP_DIR="${BACKUP_DIR:-$SCRIPT_DIR/backups}"
DC="docker compose"

c_green="\033[0;32m"; c_yellow="\033[0;33m"; c_red="\033[0;31m"; c_reset="\033[0m"
log()  { echo -e "${c_green}[restore]${c_reset} $*"; }
warn() { echo -e "${c_yellow}[restore][warn]${c_reset} $*"; }
err()  { echo -e "${c_red}[restore][error]${c_reset} $*" >&2; }

if [ "${1:-}" = "--list" ] || [ $# -eq 0 ]; then
    log "Available backups in $BACKUP_DIR:"
    find "$BACKUP_DIR" -maxdepth 1 -type f \( -name "db_*.sql.gz" -o -name "media_*.tar.gz" -o -name "private_media_*.tar.gz" \) 2>/dev/null \
        | sed -E 's#.*/##; s/^(db|media|private_media)_//; s/\.(sql\.gz|tar\.gz)$//' | sort -u || true
    echo
    echo "Usage: bash restore.sh <timestamp> [--yes]"
    exit 0
fi

TIMESTAMP="$1"
ASSUME_YES="false"
[ "${2:-}" = "--yes" ] && ASSUME_YES="true"

DB_BACKUP="$BACKUP_DIR/db_${TIMESTAMP}.sql.gz"
MEDIA_BACKUP="$BACKUP_DIR/media_${TIMESTAMP}.tar.gz"
PRIVATE_MEDIA_BACKUP="$BACKUP_DIR/private_media_${TIMESTAMP}.tar.gz"

if [ ! -f "$DB_BACKUP" ]; then
    err "No database backup found at $DB_BACKUP"
    err "Run 'bash restore.sh --list' to see available timestamps."
    exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
    err "No $ENV_FILE found — has the stack been deployed with deploy.sh?"
    exit 1
fi
DB_NAME="$(grep -E '^DB_NAME=' "$ENV_FILE" | cut -d'=' -f2-)"
DB_USER="$(grep -E '^DB_USER=' "$ENV_FILE" | cut -d'=' -f2-)"

echo
warn "This will PERMANENTLY REPLACE the current database"
[ -f "$MEDIA_BACKUP" ] && warn "and the current media files"
[ -f "$PRIVATE_MEDIA_BACKUP" ] && warn "and the current private media files (compliance evidence, receipts, board documents)"
warn "with the contents of backup '$TIMESTAMP'. This cannot be undone."
echo

if [ "$ASSUME_YES" != "true" ]; then
    read -r -p "Type 'restore' to continue: " CONFIRM
    if [ "$CONFIRM" != "restore" ]; then
        log "Aborted — nothing was changed."
        exit 0
    fi
fi

log "Stopping the application (database stays up)..."
$DC stop web nginx >/dev/null 2>&1 || true

log "Restoring database..."
$DC exec -T db psql -U "$DB_USER" -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${DB_NAME}' AND pid <> pg_backend_pid();" >/dev/null
$DC exec -T db dropdb -U "$DB_USER" --if-exists "$DB_NAME"
$DC exec -T db createdb -U "$DB_USER" -O "$DB_USER" "$DB_NAME"
gunzip -c "$DB_BACKUP" | $DC exec -T db psql -U "$DB_USER" -d "$DB_NAME" >/dev/null
log "  Database restored from $DB_BACKUP"

restore_volume() {
    local suffix="$1" archive="$2"
    local volume="${COMPOSE_PROJECT_NAME}_${suffix}_volume"
    if [ -f "$archive" ] && docker volume inspect "$volume" >/dev/null 2>&1; then
        log "Restoring ${suffix}..."
        docker run --rm \
            -v "${volume}:/data" \
            -v "${BACKUP_DIR}:/backup:ro" \
            alpine:latest \
            sh -c "rm -rf /data/* /data/..?* /data/.[!.]* 2>/dev/null; tar xzf /backup/$(basename "$archive") -C /data"
        log "  ${suffix} restored from $archive"
    fi
}
restore_volume "media" "$MEDIA_BACKUP"
restore_volume "private_media" "$PRIVATE_MEDIA_BACKUP"

log "Starting the application..."
$DC up -d --wait web
$DC up -d nginx

log "Restore complete. Verify the site before considering this done."
