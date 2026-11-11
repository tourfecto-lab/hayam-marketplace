# Phase 1 validation — 2026-11-11

Executed locally with CPython 3.12.16 on Windows and SQLite. Exact final command
output is recorded in `checks.txt`.

- pytest: 49 passed, 2 skipped; coverage 97.94% (minimum required 85%).
- The two skips are PostgreSQL-only simultaneous stock/retry tests. CI runs these
  against PostgreSQL 16; no local PostgreSQL result is claimed.
- Ruff, Black, mypy and Bandit pass after fixes.
- pip-audit reports no known vulnerabilities after DRF/Pillow upgrades.
- Django production deployment checks pass with warnings treated as failures.
- Migrations applied and realistic Arabic seed command ran successfully locally.
- Live Python server responded HTTP 200 for `/`, `/health/`, and `/static/app.css`.
  `/health/` returned `{"status": "ok"}`.
- Automated tests exercise guest checkout/retry, order privacy, CSRF, stock and
  status transitions, query budgets, uploads, admin permissions, notification
  failures/retries, filters, pagination, and JSON-LD escaping.
- Docker build/compose execution explicitly deferred locally by the user.
- Remote CI execution is separate from this local report; inspect Actions after
  pushing before considering a phase release tag or production launch.

No claim of zero possible bugs, production readiness, or successful container
execution is made by this report.
