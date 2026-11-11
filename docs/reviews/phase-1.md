# Phase 1 self-review

Reviewed the core store diff, transaction boundaries, HTTP routes, admin actions,
uploads, dependency audit, templates, settings, CI and deployment files.

## Findings resolved

1. Caching a Django paginator serialized its unsliced queryset and performed
   extra queries. Cache only page items/count/number; cold catalog is five queries,
   warm catalog one, detail three, independent of product count.
2. Cart monetary output used implicit locale separators. Explicitly format
   Decimal amounts consistently; persisted and API prices remain decimal strings.
3. Initial DRF/Pillow constraints selected vulnerable releases. Updated to
   DRF 3.18.3 and Pillow 13.0.0; the dependency audit reports no known issues.
4. Local signing key was a source constant. Generate a local-only secret in an
   ignored file; production requires an environment secret with no fallback.
5. Empty CSRF trusted-origin configuration produced a production check error.
   Filter empty values; deployment check now passes with warnings treated as errors.
6. Stock bulk updates bypass model signals. Services explicitly invalidate the
   catalog after commit; regression test checks the cache version changes.
7. An unpublished product could become impossible to remove from a cart. Show
   existing cart items and permit removal while prohibiting new inactive purchases.
8. A missing/expired session caused an unhandled service lookup failure. Reject
   it as a checkout error; retries remain session-bound.
9. A failed SMTP delivery blocked later outbox entries and rolled back attempt
   counts. Persist attempt counts, isolate each delivery and retry pending items.
   Tests verify later entries still send and successful entries are not resent.
10. Administrative order editing could bypass transition rules. Financial fields
    and order lines are read-only; creation/deletion are disabled; status actions
    use the atomic service and reject invalid transitions.
11. Added throttles to checkout/admin login, paginated the public API, bounded
    filters/cart quantities, and disabled HTMX eval/style injection for the CSP.
12. JSON-LD product text could close its script element. Escape `<` in serialized
    data; regression test covers a malicious product title.
13. Added proxy protocol handling and a health redirect exemption. Forwarded
    client IPs are trusted only in production behind the documented private proxy.

## Security review

- Access control: session ownership for guest orders; Django staff permissions
  for admin; public API read-only; inactive products excluded from public catalog.
- Injection/XSS: ORM filters, autoescaped HTML, bounded inputs, escaped JSON-LD,
  local scripts and CSP; CSRF enforced for session mutations.
- Cryptography/configuration: environment production secret, secure cookies,
  HSTS/HTTPS, no source credentials, fail-closed production secret validation.
- Supply chain/uploads: locked dependencies, audits, image signature/size/pixel
  validation and re-encoding, non-root container user, no public DB/Redis ports.
- Integrity/races: Decimal money, database constraints, session/stock/order locks,
  deterministic stock lock order, conditional stock decrement, idempotency key.
- Logging/SSRF: no user-selected external fetches; notification logs omit customer
  details; Sentry PII disabled. Health failures do not disclose exception details.

## Verification and accepted boundaries

See `../VALIDATION.md` and `../checks.txt` for command evidence. Local SQLite tests
pass; two PostgreSQL concurrency tests are deliberately skipped locally and must
pass in GitHub Actions. Docker execution was explicitly deferred by the user
because Docker is unavailable. Container syntax/build/runtime are not claimed
verified. Notification delivery remains at least once (documented SMTP boundary).

No unresolved implementation findings from this review. Release tagging awaits
the PostgreSQL CI gate; a local pass does not substitute for that gate.
