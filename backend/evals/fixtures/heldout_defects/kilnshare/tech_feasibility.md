# KilnShare — Technical Feasibility

## Verdict
Feasible for a 2-engineer team in ~3.5 months. The engineering is well-trodden marketplace plumbing; the genuinely hard parts are money-path correctness and the trust/safety flows — integration discipline, not invention.

## Recommended stack
**Next.js (responsive web, no native apps) + PostgreSQL + Stripe Connect (destination charges, deposit holds) + Stripe Identity + S3 for handover photos + Postmark.** A deliberate monolith: marketplace complexity lives in the booking state machine and payment reconciliation, not in service topology.

## Hard parts, honestly assessed
- **Escrow + deposit money paths** — charge-at-booking, hold, partial-capture on damage, auto-release at 48h: every path must be idempotent and nightly-reconciled against Stripe. This is the schedule's long pole; budget month 2 entirely for it.
- **Double-booking prevention** — availability as DB-level calendar blocks with transactional writes; boring and essential.
- **Dispute evidence flow** — handover photos must be tamper-evident (hash + timestamp at upload) or the dispute system's credibility collapses.
- **Safety-quiz gating** — technically trivial, legally load-bearing; the gate events need an audit trail for liability defense.

## What NOT to build in v1
- Smart-lock/IoT access integration (explicitly out of scope; hardware support would triple the surface area)
- Dynamic pricing or utilization ML (owners set prices; the market is too thin to train on)
- Native mobile apps (booking is a considered, desktop-friendly purchase; responsive web suffices)
- In-house identity or payments (Stripe's rails are the whole point at this scale)

## Timeline
Month 1: listings + booking calendar. Month 2: Stripe Connect escrow + identity. Month 3: messaging + reviews + dispute flow. Final two weeks: hardening, reconciliation drills, supply onboarding.
