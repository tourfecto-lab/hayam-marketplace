# Architecture

The storefront uses server-rendered Arabic RTL Django templates, HTMX filter
requests, and locally compiled Tailwind CSS. It works without JavaScript through
normal forms and links. DRF exposes a throttled read-only catalog API.

`store.models` contains categories, products, variants, optimized images, immutable
order line snapshots, status events, and a notification outbox. `store.services`
owns checkout and status transitions. HTTP views cannot set prices or statuses.
Checkout locks the session and variant rows in deterministic ID order inside a
database transaction. Conditional stock updates provide an additional guard.
Retries use a unique session-bound checkout key. Cancellation/return locks the
order and restores stock exactly once. Staff use explicit admin actions instead
of editing financial/order records.

PostgreSQL is the production source of truth. Redis backs shared catalog caches,
rate limits, and the Celery broker. A periodic Celery task drains the outbox;
events are created in the order transaction, so broker outages do not lose orders.
Email is one notification provider; WhatsApp can implement the same protocol.

Gunicorn serves Django behind nginx. WhiteNoise/volume-based nginx static serving
and re-encoded image uploads avoid application image processing on page requests.
The health endpoint checks the database and cache, but not worker heartbeat or
external providers. Monitor workers separately.

Future phases should split bounded domains into customers, payments, wallet,
sellers, and AI applications. They must preserve the order service's transaction
boundary and append-only financial audit records.
