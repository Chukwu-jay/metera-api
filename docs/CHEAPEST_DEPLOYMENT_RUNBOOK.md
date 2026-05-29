# Cheapest Metera Deployment Runbook

## Decision

Use one small VPS, Docker Compose, Postgres/pgvector, Redis, and Caddy.

Public surface:

- `https://getmetera.com` - static marketing site on GitHub Pages
- `https://api.getmetera.com` - Metera API on the VPS

Current VPS IPv4:

- `178.104.24.76`

Do not expose dashboards publicly for the first beta. Keep dashboards local-only or behind SSH/VPN until access controls are tightened.

## Cheapest Practical Provider

Recommended:

- Hetzner Cloud CX22 or equivalent 2 vCPU / 4 GB RAM VPS

Why:

- Metera's Python app plus sentence-transformer dependencies, Postgres/pgvector, and Redis need more memory than the smallest 512 MB or 1 GB instances.
- A single 4 GB VPS is cheaper and simpler than splitting app, Redis, and Postgres across managed services.
- Docker Compose already matches the repo.

Free alternative:

- Oracle Cloud Always Free Ampere A1 can work if capacity is available, but account setup and regional capacity can slow the beta down.

Fallback if Hetzner account setup is blocked:

- DigitalOcean 2 GB or 4 GB Basic Droplet.

## DNS

Keep `getmetera.com` on GitHub Pages.

Add:

```text
Type: A
Name: api
Value: 178.104.24.76
```

Optional:

```text
Type: AAAA
Name: api
Value: <VPS_PUBLIC_IPV6>
```

## Server Bootstrap

Use Ubuntu 24.04 LTS if available.

Install Docker:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git python-is-python3
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo ${UBUNTU_CODENAME:-$VERSION_CODENAME}) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Clone the repo:

```bash
git clone https://github.com/Chukwu-jay/metera-api.git
cd metera-api
```

Create production env:

```bash
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
```

Edit `.env.production` and set real values:

- `METERA_UPSTREAM_API_KEY`
- `METERA_ADMIN_API_KEY`
- `METERA_CONTROLPLANE_STATIC_API_KEY`
- `METERA_POSTGRES_PASSWORD`

Generate strong values:

```bash
openssl rand -hex 32
```

## Start

From the repo root:

```bash
docker compose --env-file .env.production -f deploy/docker-compose.cheapest.yml up -d --build
```

Check containers:

```bash
docker compose --env-file .env.production -f deploy/docker-compose.cheapest.yml ps
docker logs metera-app --tail 100
docker logs metera-caddy --tail 100
```

## First Smoke

From your local machine:

```powershell
$env:METERA_BASE_URL='https://api.getmetera.com'
$env:METERA_API_KEY='<METERA_CONTROLPLANE_STATIC_API_KEY>'
python scripts/smoke_test.py
python scripts/demo_semantic_hit.py
```

Expected:

- smoke test passes
- semantic demo proves hardened posture with `shadow_regression_alert`

## Extension Bundle

After the API is healthy:

```powershell
python scripts/package_browser_extension.py `
  --output-dir dist/browser-extension-beta `
  --version-suffix beta `
  --build-label beta-001 `
  --profile production `
  --api-origin https://api.getmetera.com
```

## Security Rules

- Do not commit `.env.production`.
- Do not expose ports `5432`, `6379`, `8501`, or `8502`.
- Keep only ports `80` and `443` open publicly.
- Use `support@getmetera.com` for public contact.
- Rotate the static beta key before inviting external testers.

## Backups

Minimum beta backup:

```bash
docker exec metera-pgvector pg_dump -U metera_user metera > metera-backup-$(date +%Y%m%d%H%M).sql
```

Copy backups off the VPS regularly.
