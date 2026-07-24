#!/usr/bin/env bash
#
# ANNET Digital Network & NPO Operating Platform — one-command production deploy.
#
# Usage (on a clean Ubuntu VPS, as root):
#   bash deploy.sh
#
# Optional overrides (environment variables, all have safe production defaults):
#   DOMAIN=annet.naleli.co.za     # public domain this deployment serves
#   ADMIN_EMAIL=admin@<domain>    # platform admin login + Let's Encrypt contact
#   SKIP_TLS=false                # set true to stay on HTTP only (e.g. before DNS is live)
#
# What it does, every time it's run (idempotent):
#   1. Installs Docker Engine + Compose plugin if not already present.
#   2. Generates (or reuses) all secrets into a root-only .env file — nothing
#      to edit by hand, ever.
#   3. Builds the application image and brings up PostgreSQL, Redis and the
#      Django app (which runs migrations, collects static files, and
#      ensures a platform admin account exists on every start).
#   4. Brings up Nginx, then attempts to obtain a Let's Encrypt certificate
#      for DOMAIN and switches Nginx to HTTPS — falling back to HTTP-only
#      with a clear warning if DNS/network isn't ready yet (safe to re-run
#      deploy.sh later once it is).
#   5. Prints the final URL and, only the first time an admin account is
#      created, its email + generated password (also saved to
#      DEPLOYMENT_CREDENTIALS.txt, root-readable only).

set -euo pipefail

# ------------------------------------------------------------------
# Configuration (safe defaults; override via environment variables)
# ------------------------------------------------------------------
DOMAIN="${DOMAIN:-annet.naleli.co.za}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@${DOMAIN}}"
LETSENCRYPT_EMAIL="${LETSENCRYPT_EMAIL:-$ADMIN_EMAIL}"
SKIP_TLS="${SKIP_TLS:-false}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

export COMPOSE_PROJECT_NAME=annet_platform
ENV_FILE=".env"
CREDENTIALS_FILE="DEPLOYMENT_CREDENTIALS.txt"
DC="docker compose"

# ------------------------------------------------------------------
# Output helpers
# ------------------------------------------------------------------
c_green="\033[0;32m"; c_yellow="\033[0;33m"; c_red="\033[0;31m"; c_bold="\033[1m"; c_reset="\033[0m"
log()   { echo -e "${c_green}[deploy]${c_reset} $*"; }
warn()  { echo -e "${c_yellow}[deploy][warn]${c_reset} $*"; }
err()   { echo -e "${c_red}[deploy][error]${c_reset} $*" >&2; }
step()  { echo -e "\n${c_bold}==> $*${c_reset}"; }

# ------------------------------------------------------------------
# 0. Preconditions
# ------------------------------------------------------------------
if [ "$(id -u)" -ne 0 ]; then
    err "This script must run as root (it installs system packages and binds ports 80/443)."
    err "Try: sudo bash deploy.sh"
    exit 1
fi

if [ ! -f "$SCRIPT_DIR/manage.py" ]; then
    err "deploy.sh must be run from inside the cloned repository."
    exit 1
fi

# ------------------------------------------------------------------
# 1. Install Docker Engine + Compose plugin (skipped if already present)
# ------------------------------------------------------------------
step "Checking Docker installation"
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    log "Docker + Compose plugin already installed ($(docker --version)) — skipping install."
else
    log "Installing Docker Engine + Compose plugin..."
    apt-get update -qq
    apt-get install -y -qq ca-certificates curl gnupg >/dev/null

    install -m 0755 -d /etc/apt/keyrings
    if [ ! -f /etc/apt/keyrings/docker.asc ]; then
        curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
        chmod a+r /etc/apt/keyrings/docker.asc
    fi

    # shellcheck disable=SC1091
    . /etc/os-release
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${UBUNTU_CODENAME:-$VERSION_CODENAME} stable" \
        > /etc/apt/sources.list.d/docker.list

    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin >/dev/null
    systemctl enable --now docker
    log "Docker installed: $(docker --version)"
fi

# ------------------------------------------------------------------
# 2. Safety check: never regenerate secrets against a pre-existing database
# ------------------------------------------------------------------
if [ ! -f "$ENV_FILE" ] && docker volume inspect "${COMPOSE_PROJECT_NAME}_postgres_data" >/dev/null 2>&1; then
    err "No $ENV_FILE was found, but an existing '${COMPOSE_PROJECT_NAME}_postgres_data' volume was."
    err "Generating new secrets now would create a database password that no longer matches"
    err "the running PostgreSQL instance and lock the application out of its own data."
    err ""
    err "If you meant to start completely fresh, first remove the old stack and its data:"
    err "    docker compose down -v"
    err "Otherwise, restore your original $ENV_FILE (from backup / secrets manager) and re-run."
    exit 1
fi

# ------------------------------------------------------------------
# 3. Generate (or reuse) secrets and write .env
# ------------------------------------------------------------------
step "Preparing environment configuration for domain: $DOMAIN"

gen_hex() { openssl rand -hex "$1"; }
gen_password() {
    # 25 characters, alphanumeric plus a guaranteed uppercase/digit/symbol —
    # comfortably clears Django's password validators (min length 10,
    # not entirely numeric, not a common password).
    local base
    base="$(openssl rand -base64 32 | tr -dc 'A-Za-z0-9' | cut -c1-22)"
    echo "${base}Xk9!"
}
env_lookup() {
    if [ -f "$ENV_FILE" ]; then
        grep -E "^$1=" "$ENV_FILE" | head -n1 | cut -d'=' -f2- || true
    fi
}

SECRET_KEY="$(env_lookup SECRET_KEY)"; [ -z "$SECRET_KEY" ] && SECRET_KEY="$(gen_hex 32)"
DB_NAME="$(env_lookup DB_NAME)"; [ -z "$DB_NAME" ] && DB_NAME="annet_platform"
DB_USER="$(env_lookup DB_USER)"; [ -z "$DB_USER" ] && DB_USER="annet_platform"
DB_PASSWORD="$(env_lookup DB_PASSWORD)"; [ -z "$DB_PASSWORD" ] && DB_PASSWORD="$(gen_hex 24)"
REDIS_PASSWORD="$(env_lookup REDIS_PASSWORD)"; [ -z "$REDIS_PASSWORD" ] && REDIS_PASSWORD="$(gen_hex 24)"

SUPERUSER_EMAIL="$(env_lookup DJANGO_SUPERUSER_EMAIL)"; [ -z "$SUPERUSER_EMAIL" ] && SUPERUSER_EMAIL="$ADMIN_EMAIL"
EXISTING_SUPERUSER_PASSWORD="$(env_lookup DJANGO_SUPERUSER_PASSWORD)"
if [ -n "$EXISTING_SUPERUSER_PASSWORD" ]; then
    SUPERUSER_PASSWORD="$EXISTING_SUPERUSER_PASSWORD"
else
    SUPERUSER_PASSWORD="$(gen_password)"
fi

# Starts False so the HTTP-only fallback (before a certificate exists)
# never force-redirects to an HTTPS listener that isn't up yet. Flipped to
# True further down, in-place, only once certbot actually succeeds.
SECURE_SSL_REDIRECT="$(env_lookup SECURE_SSL_REDIRECT)"; [ -z "$SECURE_SSL_REDIRECT" ] && SECURE_SSL_REDIRECT="False"

cat > "$ENV_FILE" <<EOF
# Generated automatically by deploy.sh on $(date -u +%FT%TZ).
# Re-running deploy.sh regenerates this file but PRESERVES all secrets
# already set below — do not hand-edit unless you know what you're doing,
# and never delete this file while the database volume still exists.

SECRET_KEY=${SECRET_KEY}
DEBUG=False
ENVIRONMENT=production
ALLOWED_HOSTS=${DOMAIN},www.${DOMAIN}
CSRF_TRUSTED_ORIGINS=https://${DOMAIN},https://www.${DOMAIN}

# Kept in lockstep with whether Nginx actually has a working HTTPS listener
# — see the certbot section of deploy.sh. Do not set this True by hand
# unless Nginx is genuinely terminating TLS, or every request will 301 into
# a dead end.
SECURE_SSL_REDIRECT=${SECURE_SSL_REDIRECT}

DB_ENGINE=postgresql
DB_NAME=${DB_NAME}
DB_USER=${DB_USER}
DB_PASSWORD=${DB_PASSWORD}
DB_HOST=db
DB_PORT=5432

REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
REDIS_PASSWORD=${REDIS_PASSWORD}

# No SMTP provider can be safely auto-configured without credentials only
# you can supply. Password reset / verification emails print to the web
# container's logs (docker compose logs web) until you set real EMAIL_HOST_*
# values here and redeploy. See DEPLOYMENT.md.
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
DEFAULT_FROM_EMAIL=ANNET Platform <no-reply@${DOMAIN}>

# Unhandled server errors are emailed here once EMAIL_HOST_* above is set
# to a real provider (harmless no-op until then).
ADMIN_EMAIL=${ADMIN_EMAIL}

PLATFORM_NAME=ANNET Digital Network
NETWORK_SHORT_NAME=ANNET
NETWORK_TAGLINE=Unity. Collaboration. Impact.

DJANGO_SUPERUSER_EMAIL=${SUPERUSER_EMAIL}
DJANGO_SUPERUSER_PASSWORD=${SUPERUSER_PASSWORD}
DJANGO_SUPERUSER_FIRST_NAME=Platform
DJANGO_SUPERUSER_LAST_NAME=Administrator

LOAD_DEMO_DATA=false
EOF
chmod 600 "$ENV_FILE"
log "Environment written to $ENV_FILE (permissions 600)."

mkdir -p docker/certbot-webroot docker/letsencrypt
chmod 755 docker/certbot-webroot

# ------------------------------------------------------------------
# 4. Render the initial (HTTP-only) Nginx config
# ------------------------------------------------------------------
step "Rendering Nginx configuration"
if [ -f "docker/letsencrypt/live/${DOMAIN}/fullchain.pem" ]; then
    log "Existing certificate found for $DOMAIN — starting directly in HTTPS mode."
    sed "s/__DOMAIN__/${DOMAIN}/g" docker/nginx/https.conf.template > docker/nginx/active.conf
    CERT_ALREADY_PRESENT=true
else
    sed "s/__DOMAIN__/${DOMAIN}/g" docker/nginx/http.conf.template > docker/nginx/active.conf
    CERT_ALREADY_PRESENT=false
fi

# ------------------------------------------------------------------
# 5. Build and start the application stack
# ------------------------------------------------------------------
step "Building application image"
$DC build web

step "Starting database and cache"
$DC up -d --wait db redis

step "Starting application (runs migrations, collects static files, ensures admin account)"
$DC up -d --wait web

step "Ensuring platform admin account"
SUPERUSER_STATUS="$($DC exec -T web python manage.py ensure_superuser | tail -n1 | tr -d '\r')"
log "Admin account status: $SUPERUSER_STATUS"

step "Starting Nginx"
$DC up -d nginx

# ------------------------------------------------------------------
# 6. HTTPS via Let's Encrypt (best-effort — falls back to HTTP on failure)
# ------------------------------------------------------------------
TLS_ENABLED=false
if [ "$CERT_ALREADY_PRESENT" = "true" ]; then
    TLS_ENABLED=true
elif [ "$SKIP_TLS" = "true" ]; then
    warn "SKIP_TLS=true — leaving the deployment on HTTP only."
else
    step "Requesting a Let's Encrypt certificate for $DOMAIN"
    set +e
    $DC run --rm --entrypoint certbot certbot certonly \
        --webroot -w /var/www/certbot \
        -d "$DOMAIN" \
        --email "$LETSENCRYPT_EMAIL" --agree-tos --no-eff-email --non-interactive
    CERTBOT_EXIT=$?
    set -e

    if [ "$CERTBOT_EXIT" -eq 0 ]; then
        log "Certificate obtained for $DOMAIN."
        sed "s/__DOMAIN__/${DOMAIN}/g" docker/nginx/https.conf.template > docker/nginx/active.conf
        $DC exec -T nginx nginx -s reload
        $DC up -d certbot

        # Now that Nginx genuinely terminates TLS, it's safe to tell Django
        # to redirect HTTP -> HTTPS. Flip the flag in .env and recreate the
        # web container so it picks up the new value.
        sed -i "s/^SECURE_SSL_REDIRECT=.*/SECURE_SSL_REDIRECT=True/" "$ENV_FILE"
        $DC up -d --wait web
        TLS_ENABLED=true
    else
        warn "Could not obtain a Let's Encrypt certificate for $DOMAIN (exit code $CERTBOT_EXIT)."
        warn "This is expected if DNS for $DOMAIN doesn't point at this server's public IP yet,"
        warn "or if ports 80/443 aren't reachable from the internet."
        warn "The application is still running over plain HTTP. Once DNS/network is ready, just re-run:"
        warn "    bash deploy.sh"
        warn "to retry certificate issuance — nothing else will be re-created."
    fi
fi

# ------------------------------------------------------------------
# 7. Final health check
# ------------------------------------------------------------------
step "Verifying the deployment"
PROTO="http"; [ "$TLS_ENABLED" = "true" ] && PROTO="https"
FINAL_URL="${PROTO}://${DOMAIN}/"

HEALTH_OK=false
for _ in $(seq 1 10); do
    if curl -fsS -o /dev/null "http://127.0.0.1/accounts/login/"; then
        HEALTH_OK=true
        break
    fi
    sleep 2
done

if [ "$HEALTH_OK" = "true" ]; then
    log "Application is responding."
else
    warn "Could not confirm the application is responding on localhost:80 yet — check 'docker compose logs' if $FINAL_URL doesn't load."
fi

# ------------------------------------------------------------------
# 8. Credentials output
# ------------------------------------------------------------------
step "Deployment summary"

if [ "$SUPERUSER_STATUS" = "CREATED" ]; then
    cat > "$CREDENTIALS_FILE" <<EOF
ANNET Digital Network & NPO Operating Platform — deployment credentials
Generated: $(date -u +%FT%TZ)

URL:            ${FINAL_URL}
Admin sign-in:  ${FINAL_URL}accounts/login/
Admin email:    ${SUPERUSER_EMAIL}
Admin password: ${SUPERUSER_PASSWORD}

This file is created only once, when the admin account is first created.
Store these credentials in a password manager, then delete this file:
    rm ${SCRIPT_DIR}/${CREDENTIALS_FILE}
EOF
    chmod 600 "$CREDENTIALS_FILE"
fi

echo
echo -e "${c_bold}  URL:${c_reset}            $FINAL_URL"
if [ "$TLS_ENABLED" != "true" ]; then
    echo -e "  ${c_yellow}(HTTPS not yet active — see warning above)${c_reset}"
fi
echo -e "${c_bold}  Admin sign-in:${c_reset}  ${FINAL_URL}accounts/login/"
echo -e "${c_bold}  Admin email:${c_reset}    $SUPERUSER_EMAIL"
if [ "$SUPERUSER_STATUS" = "CREATED" ]; then
    echo -e "${c_bold}  Admin password:${c_reset} $SUPERUSER_PASSWORD"
    echo -e "  ${c_yellow}Also saved to ${CREDENTIALS_FILE} (permissions 600) — store it and delete the file.${c_reset}"
else
    echo -e "  Admin account already existed — password unchanged (not re-displayed)."
fi
echo
log "Done. Re-run 'bash deploy.sh' any time — it is safe and idempotent."
