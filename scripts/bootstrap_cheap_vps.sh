#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${METERA_REPO_URL:-https://github.com/Chukwu-jay/metera-api.git}"
APP_DIR="${METERA_APP_DIR:-/opt/metera-api}"
UPSTREAM_API_KEY="${METERA_UPSTREAM_API_KEY:-}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run this script as root." >&2
  exit 1
fi

if [[ -z "$UPSTREAM_API_KEY" ]]; then
  echo "Set METERA_UPSTREAM_API_KEY before running this script." >&2
  echo "Example: METERA_UPSTREAM_API_KEY='...' bash scripts/bootstrap_cheap_vps.sh" >&2
  exit 1
fi

apt-get update
apt-get install -y ca-certificates curl git openssl python-is-python3

install -m 0755 -d /etc/apt/keyrings
if [[ ! -f /etc/apt/keyrings/docker.asc ]]; then
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
fi

if [[ ! -f /etc/apt/sources.list.d/docker.list ]]; then
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${UBUNTU_CODENAME:-$VERSION_CODENAME} stable" > /etc/apt/sources.list.d/docker.list
fi

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

if [[ ! -d "$APP_DIR/.git" ]]; then
  mkdir -p "$(dirname "$APP_DIR")"
  git clone "$REPO_URL" "$APP_DIR"
else
  git -C "$APP_DIR" pull --ff-only
fi

cd "$APP_DIR"

if [[ ! -f .env.production ]]; then
  cat > .env.production <<'ENV'
METERA_UPSTREAM_BASE_URL=https://api.openai.com
METERA_UPSTREAM_API_KEY=CHANGE_ME_UPSTREAM_PROVIDER_KEY
METERA_UPSTREAM_TIMEOUT_SECONDS=60
METERA_UPSTREAM_MAX_RETRIES=1

METERA_ADMIN_API_KEY=CHANGE_ME_LONG_RANDOM_ADMIN_KEY
METERA_CONTROLPLANE_STATIC_API_KEY=CHANGE_ME_LONG_RANDOM_WORKSPACE_KEY
METERA_POSTGRES_PASSWORD=CHANGE_ME_LONG_RANDOM_POSTGRES_PASSWORD

METERA_DEFAULT_EXACT_TTL_SECONDS=3600
METERA_DEFAULT_SEMANTIC_TTL_SECONDS=86400
ENV
  chmod 600 .env.production
  ADMIN_KEY="$(openssl rand -hex 32)"
  WORKSPACE_KEY="$(openssl rand -hex 32)"
  POSTGRES_PASSWORD="$(openssl rand -hex 32)"
  sed -i "s|CHANGE_ME_UPSTREAM_PROVIDER_KEY|$UPSTREAM_API_KEY|g" .env.production
  sed -i "s|CHANGE_ME_LONG_RANDOM_ADMIN_KEY|$ADMIN_KEY|g" .env.production
  sed -i "s|CHANGE_ME_LONG_RANDOM_WORKSPACE_KEY|$WORKSPACE_KEY|g" .env.production
  sed -i "s|CHANGE_ME_LONG_RANDOM_POSTGRES_PASSWORD|$POSTGRES_PASSWORD|g" .env.production
else
  echo ".env.production already exists; leaving existing secrets unchanged."
fi

docker compose --env-file .env.production -f deploy/docker-compose.cheapest.yml up -d --build

echo
echo "Metera deployment command completed."
echo "API health check:"
echo "  curl -fsS https://api.getmetera.com/health"
echo
echo "Save these local-only values from $APP_DIR/.env.production:"
echo "  METERA_ADMIN_API_KEY"
echo "  METERA_CONTROLPLANE_STATIC_API_KEY"
