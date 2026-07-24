#!/usr/bin/env bash
#
# Update an already-deployed instance: pull the latest code, rebuild the
# application image, and restart the stack. Migrations and static files
# are handled automatically by docker/django/entrypoint.sh on container
# start, exactly as they are on every deploy.sh run.
#
# A database backup is taken before anything else, specifically so a
# migration that turns out to be wrong has a fast way back
# (see restore.sh). Safe to run repeatedly.
#
# Usage:
#   bash update.sh                # git pull + rebuild + restart
#   SKIP_BACKUP=true bash update.sh
#   SKIP_GIT_PULL=true bash update.sh   # rebuild/restart only, e.g. after editing files directly on the server
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

export COMPOSE_PROJECT_NAME=annet_platform
ENV_FILE=".env"
DC="docker compose"
SKIP_BACKUP="${SKIP_BACKUP:-false}"
SKIP_GIT_PULL="${SKIP_GIT_PULL:-false}"

c_green="\033[0;32m"; c_yellow="\033[0;33m"; c_red="\033[0;31m"; c_bold="\033[1m"; c_reset="\033[0m"
log()  { echo -e "${c_green}[update]${c_reset} $*"; }
warn() { echo -e "${c_yellow}[update][warn]${c_reset} $*"; }
err()  { echo -e "${c_red}[update][error]${c_reset} $*" >&2; }
step() { echo -e "\n${c_bold}==> $*${c_reset}"; }

if [ ! -f "$ENV_FILE" ]; then
    err "No $ENV_FILE found — this instance hasn't been deployed yet. Run: bash deploy.sh"
    exit 1
fi

if [ "$SKIP_GIT_PULL" != "true" ] && [ -d .git ]; then
    if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
        err "There are uncommitted local changes to tracked files:"
        git status --short --untracked-files=no >&2
        err "Commit, stash, or discard them before updating (or set SKIP_GIT_PULL=true to skip pulling)."
        exit 1
    fi
fi

if [ "$SKIP_BACKUP" != "true" ]; then
    step "Backing up before update"
    bash backup.sh
else
    warn "SKIP_BACKUP=true — proceeding without a fresh backup."
fi

if [ "$SKIP_GIT_PULL" != "true" ] && [ -d .git ]; then
    step "Pulling latest code"
    CURRENT_COMMIT="$(git rev-parse --short HEAD)"
    if ! git pull --ff-only; then
        err "git pull --ff-only failed — the local branch has likely diverged from its remote."
        err "Resolve manually (git fetch && git log --oneline HEAD..@{u}), then re-run."
        exit 1
    fi
    NEW_COMMIT="$(git rev-parse --short HEAD)"
    if [ "$CURRENT_COMMIT" = "$NEW_COMMIT" ]; then
        log "Already up to date ($NEW_COMMIT)."
    else
        log "Updated $CURRENT_COMMIT -> $NEW_COMMIT"
    fi
else
    warn "Skipping git pull."
fi

step "Rebuilding application image"
$DC build web

step "Restarting the stack"
$DC up -d --wait db redis
$DC up -d --wait web
$DC up -d nginx

step "Verifying"
HEALTH_OK=false
for _ in $(seq 1 10); do
    if curl -fsS -o /dev/null "http://127.0.0.1/accounts/login/"; then
        HEALTH_OK=true
        break
    fi
    sleep 2
done

if [ "$HEALTH_OK" = "true" ]; then
    log "Application is responding. Update complete."
else
    warn "Could not confirm the application is responding on localhost:80 — check: docker compose logs web"
fi

DOMAIN_FROM_ENV="$(grep -E '^ALLOWED_HOSTS=' "$ENV_FILE" | cut -d'=' -f2- | cut -d',' -f1)"
[ -n "$DOMAIN_FROM_ENV" ] && log "Site: https://${DOMAIN_FROM_ENV}/ (or http:// if TLS isn't enabled yet)"
