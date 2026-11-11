# Decisions

- Phase 1 is the current scope. No customer accounts, wallet, payment gateway,
  seller payouts, or AI features are represented as implemented.
- Per the user's 2026-11-11 override, SQLite is used locally and PostgreSQL in CI.
  Docker build/compose smoke tests are explicitly deferred locally because Docker
  is unavailable. Container files are provided for later validation.
- Django 5.2 LTS is used with Python 3.12. Dependencies are locked with uv and npm.
- Guest orders belong to a database-backed browser session. UUIDs are identifiers,
  not authorization tokens. Losing the session requires contacting store support.
  Phase 2 adds authenticated order history.
- Shipping is free during Phase 1. EGP is the only enabled currency; stored orders
  carry a currency code for future SAR/AED support. No exchange rates are invented.
- Checkout is pay-on-delivery only at this stage. `paid` is a manual staff status;
  an actual COD/Paymob provider abstraction belongs to Phase 3.
- Staff acceptance of a return means goods were received and approved for restock.
  Pending/paid orders may be cancelled; shipped orders must be returned instead.
- Notification delivery uses a durable database outbox, polled by Celery beat.
  Local development can drain it with a management command. Delivery is at least
  once: an SMTP timeout/crash after delivery can duplicate an email. A WhatsApp
  provider must deduplicate with the event ID; no outbound WhatsApp service is
  enabled. Notifications never block checkout.
- Catalog data is cached for 60 seconds, with invalidation on committed changes.
  No rendered CSRF/session HTML is cached. Raw database bulk edits outside the
  service layer may remain stale until the TTL expires.
- SQLite does not prove PostgreSQL row-lock/concurrency behavior. PostgreSQL-only
  concurrency tests are included in CI and their local skip is reported honestly.
- Product media is re-encoded to WebP and thumbnailed. Demo products have honest
  placeholders; no fabricated product photography is included.
- Production terminates TLS at host nginx and forwards through a loopback-bound
  container nginx. Only this controlled proxy may supply forwarded protocol/IP
  headers. Do not expose application or internal proxy ports publicly.
