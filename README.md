# Hayam Marketplace — Phase 1

Arabic RTL, mobile-first Egyptian fashion storefront built with Python 3.12,
Django 5.2, DRF, templates, HTMX and Tailwind. This release contains the core
single-store catalog, variants/images/stock, filters/search, guest cart/checkout,
orders, staff status actions, and durable email/WhatsApp-ready notification hooks.
Prices use Decimal and EGP; no live payment gateway is connected.

**Status:** see `docs/reviews/phase-1.md` and `docs/VALIDATION.md` for actual
verification. Docker files are supplied but untested locally, as requested.
PostgreSQL CI must be run after this project is published to the private repo.
Phases 2–6 are future work, not enabled features.

## Local setup (about five minutes after prerequisites)

Install Python 3.12 or [uv](https://docs.astral.sh/uv/getting-started/installation/).
Precompiled CSS/HTMX are committed, so Node is only needed when editing assets.
From the repository directory:

```sh
uv sync --frozen --python 3.12
uv run python manage.py migrate
uv run python manage.py seed_demo
uv run python manage.py runserver 127.0.0.1:8000
```

Open <http://127.0.0.1:8000>. Local settings automatically use SQLite, in-memory
cache and console email, with no PostgreSQL/Redis/Docker dependency. A randomly
generated local signing secret is persisted in ignored `.local-secret`. Keep it
to preserve guest sessions. Never use `config.settings.local` in production.

Create your own administrator interactively:

```sh
uv run python manage.py createsuperuser
uv run python manage.py deliver_notifications
```

Visit `/admin/` to manage products, variants and images. Products default to
inactive. Publish only after adding variants, prices, stock and image alt text.
Order financial fields are read-only. Select orders and use explicit status
actions; accepting a returned order means the goods are approved for restocking.
Guest order details remain accessible only in the browser session that ordered.

Optional asset changes require Node 22:

```sh
npm ci
npm run build
```

## Checks

```sh
uv run ruff check .
uv run black --check .
uv run mypy config store tests manage.py
uv run bandit -r config store manage.py -c pyproject.toml
uv run pip-audit
npm audit --audit-level=high
uv run pytest
uv run python manage.py makemigrations --check --dry-run
```

The suite enforces 85% coverage. Local SQLite runs intentionally skip two
PostgreSQL row-lock concurrency cases. CI sets `TEST_POSTGRES=1` and runs them
against PostgreSQL 16. Query-budget tests cover cold/warm catalog and detail
pages. Install hooks with `uv run pre-commit install`.

Run production checks with environment variables set (PowerShell shown):

```powershell
$env:DJANGO_SETTINGS_MODULE = 'config.settings.production'
$env:DJANGO_SECRET_KEY = (uv run python -c 'import secrets; print(secrets.token_urlsafe(64))')
$env:DJANGO_ALLOWED_HOSTS = 'shop.example.com'
$env:DJANGO_CSRF_TRUSTED_ORIGINS = 'https://shop.example.com'
uv run python manage.py check --deploy --fail-level WARNING
```

## Environment

Copy `.env.example` to `.env` for Docker; do not commit the resulting file.
Direct Python processes use exported environment variables (the app deliberately
does not implicitly load `.env`). Required production settings:

| Variable | Purpose |
| --- | --- |
| `DJANGO_SETTINGS_MODULE` | `config.settings.production` |
| `DJANGO_SECRET_KEY` | Unique random 50+ character secret |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated store hostnames |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Comma-separated HTTPS origins |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Database credentials |
| `POSTGRES_HOST`, `POSTGRES_PORT` | `db:5432` in compose |
| `REDIS_URL` | Shared cache and Celery broker; `redis://redis:6379/0` |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | TLS SMTP |
| `DEFAULT_FROM_EMAIL` | Verified sender address |
| `SENTRY_DSN` | Optional error reporting, PII disabled |

No Paymob, SMS or AI keys are needed for Phase 1. Future keys belong only in
deployment secrets, not source or logs.

## VPS deployment with HTTPS

This runbook is provided for review; the container stack has not been executed
on this Windows machine. Validate it on a staging VPS before accepting orders.

1. Provision an Ubuntu LTS VPS, set a domain A/AAAA record, install Docker Engine
   with its Compose plugin using Docker's official instructions, and install
   `nginx`, `certbot`, and `python3-certbot-nginx` from the OS package manager.
   Allow SSH/80/443 through the host firewall. Do not open 5432/6379/8000/8080.
2. Clone **only the new private repository**, enter it, copy `.env.example` to
   `.env`, `chmod 600 .env`, and replace every placeholder. Generate a secret
   using `python3 -c 'import secrets; print(secrets.token_urlsafe(64))'`. Set
   the domain/CSRF origin and SMTP credentials. Check `.env` is ignored by Git.
3. Build and initialize (run migrations once, not from each worker):

   ```sh
   docker compose build
   docker compose up -d db redis
   docker compose run --rm web python manage.py migrate --noinput
   docker compose run --rm web python manage.py collectstatic --noinput
   docker compose run --rm web python manage.py createsuperuser
   docker compose run --rm web python manage.py check --deploy --fail-level WARNING
   docker compose up -d
   docker compose ps
   ```

   Do not seed demo data in production. Confirm the web service is healthy.
4. Create `/etc/nginx/sites-available/hayam` on the host with your actual domain:

   ```nginx
   server {
       listen 80;
       server_name shop.example.com;
       client_max_body_size 6m;
       location / {
           proxy_pass http://127.0.0.1:8080;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```

   Enable it with a symlink in `sites-enabled`, run `sudo nginx -t`, and reload
   nginx. The internal proxy is loopback-bound. It passes only host-controlled
   protocol/IP headers to Django. Never expose Gunicorn directly.
5. Run `sudo certbot --nginx -d shop.example.com --redirect`, then
   `sudo certbot renew --dry-run`. Visit HTTPS and confirm no redirect loop,
   secure session cookies, valid image/static requests and security headers.
6. Run a real staging checkout, retry its POST, check stock, change status in
   admin, inspect outbox/email delivery, then test cancellation and returns.
   `/health/` checks database/cache. Monitor Celery worker and beat separately.
7. Before releases: back up first, review migrations, pull the tested revision,
   rebuild, run migrate/collectstatic once, and recreate services. Use a
   maintenance window when a migration is incompatible with the running app.

## Backup and restore

Run backups daily from the project directory. Protect files containing customer
data and copy them encrypted to a separate host/storage with retention. SQL and
media snapshots must be taken within a maintenance window for consistency.

```sh
mkdir -p backups
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > backups/hayam.dump
docker compose exec -T web tar -czf - -C /app/media . > backups/media.tar.gz
```

Restore only into the intended empty staging/recovery database after checking
the target hostname. Stop writes and workers first; preserve a fresh pre-restore
backup if the target already contains data. Example for an empty recovery DB:

```sh
docker compose stop web worker beat
docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --exit-on-error' < backups/hayam.dump
docker compose run --rm -T web tar -xzf - -C /app/media < backups/media.tar.gz
docker compose run --rm web python manage.py migrate --noinput
docker compose up -d
```

Never restore over a live database casually. Test catalog/order counts and media
after restoring. Keep deployment secrets separately; they are absent from Git.

## Operational limitations

- Phase 1 has guest sessions, free shipping, manual fulfillment/status changes,
  and no online gateway or customer accounts.
- Notifications are at least once; SMTP can duplicate a message after an
  ambiguous provider timeout. A WhatsApp provider must deduplicate by event ID.
- Local cache/rate limits are per process; production requires shared Redis.
- SQLite local testing does not establish production concurrency behavior.
- Add store-specific policies/support information and a data-retention process
  before launch. Demo imagery is a labeled placeholder.

See `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/ROADMAP.md`, and
`docs/PRODUCTION_CHECKLIST.md` for boundaries and launch work.
