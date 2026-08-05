# InvoiceFox — System Architecture

## Overview
A boring-on-purpose stack: Next.js frontend, FastAPI backend, PostgreSQL, deployed on a single cloud provider. Monolith first; extract services only when metrics demand it.

## Components
- **Web app (Next.js)** — dashboard, invoice CRUD, sequence editor
- **API (FastAPI)** — REST endpoints, auth (JWT + refresh), rate limiting
- **PostgreSQL** — invoices, clients, sequences, events (append-only table for reminder history)
- **Background worker (Celery + Redis)** — schedules and sends reminder emails; retries with exponential backoff
- **Stripe integration** — payment links + webhooks for paid-status sync
- **Email service (Postmark)** — transactional sends, open/click tracking feeds the "viewed" status

## Key decisions
- Reminder scheduling is DB-driven (a `next_send_at` index), not cron-per-user — one worker scan per minute scales past 100k sequences
- Email deliverability is the product's lifeline: dedicated sending domain, DKIM/SPF/DMARC from day one, warm-up plan
- Multi-tenancy via row-level `account_id` scoping; no per-tenant schemas in v1

## Risks
- Reminder emails landing in spam → mitigated by Postmark reputation + gradual warm-up
- Stripe webhook loss → idempotent handlers + nightly reconciliation job
