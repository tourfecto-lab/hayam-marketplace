# Production checklist

- [ ] Create the private `hayam-marketplace` repository and confirm access.
- [ ] Confirm PostgreSQL CI, security audit and container build pass.
- [ ] Run the full compose stack smoke test on a Docker-capable host.
- [ ] Set domain DNS and HTTPS, test renewal and HTTP-to-HTTPS redirects.
- [ ] Generate a unique Django secret; configure hosts and trusted CSRF origins.
- [ ] Set a unique PostgreSQL password; keep database/Redis ports private.
- [ ] Configure SMTP credentials/from-domain, SPF/DKIM/DMARC and test delivery.
- [ ] Configure support contact, privacy notice, shipping/returns policy and terms.
- [ ] Replace demo catalog with approved prices, stock and actual product photos.
- [ ] Create a named administrator with a strong password; remove unused staff.
- [ ] Verify guest order isolation, checkout retries and stock with real workflows.
- [ ] Verify trusted proxy headers, shared Redis rate limits and admin access.
- [ ] Back up PostgreSQL AND uploaded media; rehearse restoration off-host.
- [ ] Set Sentry DSN and alerts for health, worker failures, disk and backups.
- [ ] Add retention/erasure operations for customer phone, address and email data.
- [ ] Review OWASP controls against actual hosting configuration.
- [ ] Phase 2: configure SMS/OTP backend and abuse controls before enabling login.
- [ ] Phase 3: configure Paymob keys/HMAC secret and sandbox-test callbacks.
- [ ] Phase 6: configure AI provider keys/quotas only when those features exist.

Phase 1 is not a complete marketplace and must not accept online gateway payments.
