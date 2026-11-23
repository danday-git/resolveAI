# Deployment

A single host running Docker Compose: Caddy terminates HTTPS and is the only published
service. The web app, API, worker and database talk to each other on the Compose network.

## 1. Configure

Copy `.env.example` to `.env` on the host and set at least:

| Variable | Value |
| --- | --- |
| `JWT_SECRET` | 32+ random characters (`openssl rand -hex 32`) |
| `DEMO_USER_PASSWORD` | Password of the first administrator created by the seed |
| `SITE_ADDRESS` | Public domain, e.g. `resolveai.example.com`. Its DNS record must point at the host |
| `APP_URL`, `CORS_ORIGINS` | `https://<SITE_ADDRESS>` (used in password reset links) |
| `LLM_PROVIDER`, `EMBEDDING_PROVIDER` and keys | See the README |
| `ALLOW_REGISTRATION` | `false` to close password sign-up. Single sign-on still creates an account for every identity the provider accepts; limit those with `OIDC_ALLOWED_DOMAINS` |

Change the database password in `infra/docker-compose.yml` (`POSTGRES_PASSWORD` and the two
`DATABASE_URL` values) before the first start.

## 2. Start

```bash
docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml \
  --env-file .env --profile web up -d --build
docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml \
  --env-file .env exec api python -m app.seed
```

Ports 80 and 443 must be reachable from the internet: Caddy obtains and renews the
certificate from Let's Encrypt on its own. `HTTP_PORT` and `HTTPS_PORT` change the host ports.
With `SITE_ADDRESS=localhost` Caddy issues a local certificate, which is enough for a trial run.

The overlay removes the published ports of the database, API and web app, marks the session
cookie `Secure`, and lets the API trust the client address Caddy forwards, so per-client rate
limits count real clients. Do not publish the API port in this setup: that trust is only safe
while every request passes through Caddy.

Docker Hub limits anonymous image pulls. If a pull fails with `429 Too Many Requests`, log in
with `docker login` or pull the official image from a mirror
(`docker pull mirror.gcr.io/library/caddy:2 && docker tag mirror.gcr.io/library/caddy:2 caddy:2`).

## 3. Optional services

- **Malware scan:** add `--profile scan` and set `CLAMAV_HOST=clamav`. ClamAV needs about 2 GB
  of memory. Once the host is set, an upload that cannot be scanned is refused.
- **OCR:** `OCR_ENABLED=true` reads scanned PDF pages with Tesseract (`OCR_LANGUAGES=eng+ind`
  for English and Indonesian). Only the first `OCR_MAX_PAGES` scanned pages of a file are read.
- **Email:** set `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD` and `SMTP_FROM` so users can reset
  their own password. Without it an administrator issues reset links from the Admin page.
- **Single sign-on:** set `OIDC_ISSUER`, `OIDC_CLIENT_ID` and `OIDC_CLIENT_SECRET`, and register
  `https://<SITE_ADDRESS>/api/v1/auth/oidc/callback` as the redirect URI at the provider.

## 4. Backups

```bash
export COMPOSE_ARGS="-f infra/docker-compose.yml -f infra/docker-compose.prod.yml --env-file .env"
scripts/backup.sh /var/backups/resolveai      # database dump + uploaded files
scripts/restore.sh /var/backups/resolveai/resolveai-<stamp>.dump
```

`backup.sh` keeps the newest 14 backups (`BACKUP_KEEP`). `restore.sh` replaces the current
database and uploads, and asks for confirmation first. It stops the API and the worker while it
runs, so the application is unavailable for that time. Schedule the backup from cron, for
example `15 2 * * * cd /opt/resolveai && COMPOSE_ARGS="..." scripts/backup.sh /var/backups/resolveai`,
and copy the directory to another machine: a backup on the same disk does not survive losing
the host. Restore into a test stack from time to time to prove the backups work.

## 5. Monitoring

**Prometheus.** Set `METRICS_TOKEN` to a long random value. The API then serves `/metrics`
(request counts and time per route, documents by ingestion status, age of the oldest queued
document, LLM calls in the last hour, LLM spend in the last day). The endpoint is not exposed
through Caddy, so run Prometheus on the same Compose network:

```yaml
scrape_configs:
  - job_name: resolveai
    authorization:
      credentials: <METRICS_TOKEN>
    static_configs:
      - targets: ["api:8000"]
```

Useful alerts: `resolveai_ingestion_oldest_queued_seconds > 600` (worker stuck or stopped),
`resolveai_documents{status="failed"}` rising, a growing share of 5xx in
`resolveai_http_requests_total`, and `resolveai_llm_cost_usd_last_day` above budget. Request
counters are kept per API process and restart at zero with it.

**Sentry.** Set `SENTRY_DSN` to report unhandled API errors and failed ingestion jobs. A report
contains the exception type and message (with the same secret, email and IP redaction as the
logs), the stack trace with the source lines of this application, the host name, the route, and
recent log lines. It never contains request bodies, local variables, cookies or user details,
so prompts, documents and incident logs stay out of it.

**Health.** `GET /health` (process is up) and `GET /ready` (database reachable) on the API are
used by the Compose health check.

## 6. Data controls

- **Consent.** With `LLM_PROVIDER` or `EMBEDDING_PROVIDER` set to `openai` or `anthropic`, each
  user must allow sending their data to that provider on the Account page. Until then upload,
  chat, incident analysis and RCA drafting return `LLM_CONSENT_REQUIRED` for that user.
  Consent names the provider, so switching provider asks again. Ollama and the mock provider
  run locally and need no consent.
- **Retention.** `RETENTION_INCIDENT_DAYS`, `RETENTION_CONVERSATION_DAYS`,
  `RETENTION_LOG_DAYS` and `RETENTION_AUDIT_DAYS` delete records older than that many days
  (0 keeps them). Incidents age from their last change. The worker runs the cleanup hourly and
  writes a `retention.purged` audit entry with the counts. Documents are only deleted by their
  owner. Backups keep deleted data until they rotate out (`BACKUP_KEEP`).
- **Audit log.** Sign-ins, account and role changes, consent decisions, uploads, deletions,
  incident changes, analyses and RCA drafts, edits and confirmations are recorded with the
  actor, time and record ID, never the content. Administrators read it on the Admin page.

## 7. Updates

```bash
git pull
scripts/backup.sh /var/backups/resolveai
docker compose -f infra/docker-compose.yml -f infra/docker-compose.prod.yml \
  --env-file .env --profile web up -d --build
```

The API applies database migrations when it starts.

## Not covered

- One host, one database: no replication or automatic failover. A managed PostgreSQL with
  pgvector removes that risk; point `DATABASE_URL` at it and drop the `db` service.
- Running several API replicas needs a load balancer in front and a Prometheus target per
  replica. The rate limit and the ingestion queue are already shared through the database.
- Error reporting covers the API and the worker, not the browser.
