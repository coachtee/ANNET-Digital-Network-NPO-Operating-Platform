#!/usr/bin/env bash
#
# Back up the PostgreSQL database and both media roots for the Docker
# deployment. Safe to run at any time (does not stop the stack) and safe
# to run repeatedly — each backup gets its own timestamped file.
#
# Usage:
#   bash backup.sh                 # backs up to ./backups/
#   BACKUP_DIR=/mnt/offsite bash backup.sh
#   KEEP=30 bash backup.sh         # retain the last 30 backups instead of the default 14
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

export COMPOSE_PROJECT_NAME=annet_platform
ENV_FILE=".env"
BACKUP_DIR="${BACKUP_DIR:-$SCRIPT_DIR/backups}"
KEEP="${KEEP:-14}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DC="docker compose"

c_green="\033[0;32m"; c_red="\033[0;31m"; c_reset="\033[0m"
log()  { echo -e "${c_green}[backup]${c_reset} $*"; }
err()  { echo -e "${c_red}[backup][error]${c_reset} $*" >&2; }

if [ ! -f "$ENV_FILE" ]; then
    err "No $ENV_FILE found — nothing to back up (has the stack been deployed with deploy.sh?)."
    exit 1
fi

DB_NAME="$(grep -E '^DB_NAME=' "$ENV_FILE" | cut -d'=' -f2-)"
DB_USER="$(grep -E '^DB_USER=' "$ENV_FILE" | cut -d'=' -f2-)"

if [ -z "$($DC ps db --status running --quiet 2>/dev/null)" ]; then
    err "The 'db' container isn't running. Start the stack first: bash deploy.sh"
    exit 1
fi

mkdir -p "$BACKUP_DIR"

log "Backing up database ($DB_NAME)..."
$DC exec -T db pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$BACKUP_DIR/db_${TIMESTAMP}.sql.gz"
log "  -> $BACKUP_DIR/db_${TIMESTAMP}.sql.gz ($(du -h "$BACKUP_DIR/db_${TIMESTAMP}.sql.gz" | cut -f1))"

for volume_suffix in media private_media; do
    volume="${COMPOSE_PROJECT_NAME}_${volume_suffix}_volume"
    if docker volume inspect "$volume" >/dev/null 2>&1; then
        log "Backing up ${volume_suffix}..."
        docker run --rm \
            -v "${volume}:/data:ro" \
            -v "${BACKUP_DIR}:/backup" \
            alpine:latest \
            tar czf "/backup/${volume_suffix}_${TIMESTAMP}.tar.gz" -C /data .
        log "  -> $BACKUP_DIR/${volume_suffix}_${TIMESTAMP}.tar.gz ($(du -h "$BACKUP_DIR/${volume_suffix}_${TIMESTAMP}.tar.gz" | cut -f1))"
    fi
done

if [ "$KEEP" -gt 0 ]; then
    log "Pruning backups older than the most recent $KEEP per type..."
    for prefix in db media private_media; do
        # shellcheck disable=SC2012
        ls -1t "$BACKUP_DIR"/${prefix}_*.* 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -f
    done
fi

log "Done. Backups in $BACKUP_DIR:"
find "$BACKUP_DIR" -maxdepth 1 -name "*${TIMESTAMP}*" -exec ls -lh {} \;
