# InvoiceFox — Tech Feasibility

## Requirements driving tech decisions
- Functional: invoice CRUD, scheduled multi-step email sequences, Stripe payment links + webhook status sync, open/click tracking, per-client tone templates.
- Non-functional: email deliverability is existential; solo-dev buildable; near-zero infra cost until revenue; data privacy (financial PII).

## Stack alternatives
1. **Next.js + FastAPI + Postgres + Celery/Redis + Postmark + Stripe** — boring, well-documented, one developer can own it end to end. ~$50-150/mo at early scale. Learning curve: low for the target builder.
2. Full-stack TypeScript (Next.js + tRPC + Prisma + BullMQ) — one language everywhere; background-job ecosystem slightly weaker than Celery; comparable cost.
3. Low-code core (Airtable/Zapier + transactional email) — fastest to fake, collapses at sequence complexity and deliverability control; rejected for anything past a landing-page test.

## Recommended stack
Option 1. Rationale: scheduling reliability and deliverability tooling are the product; Celery + a DB-driven `next_send_at` index and a reputable ESP (Postmark) are the proven path. Stripe stays the system of record for payment status.

## Technical risks
- **Deliverability** (top risk): shared-domain reputation, warm-up, DKIM/SPF/DMARC from day one; mitigation — dedicated sending domain + gradual volume ramp + ESP with strong reputation.
- Webhook loss → idempotent handlers + nightly reconciliation.
- Buy-vs-build: email sending (buy: ESP), scheduling (build: it's core), payment rails (buy: Stripe).

## MVP technical scope
Tracking dashboard + one default 3-step sequence + Stripe links + paid/viewed status. Defer: multi-currency, accounting integrations, mobile apps, team features. A solo developer ships this in 6-10 weeks at the recommended stack's happy path.
