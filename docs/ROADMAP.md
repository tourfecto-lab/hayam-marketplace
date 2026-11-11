# Roadmap

1. Core store: current implementation and local verification; PostgreSQL CI and
   container execution must be verified before production.
2. Phone OTP customers, addresses, history, wishlist, verified fit reviews.
3. COD/Paymob payment abstraction, verified HMAC callbacks and idempotency.
4. Append-only cashback/referral ledger, delayed vesting, reversal and expiry.
5. Seller onboarding, isolated dashboards, moderation, commission/payout ledger.
6. AI provider interfaces, grounded sales assistant, image content assistance,
   size recommendations, per-user throttles and cache.

Each phase requires tests, security/type/format checks, a written self-review,
and a release tag only after its agreed quality gate succeeds. Docker was waived
for local Phase 1 execution only; the files remain untested locally.
