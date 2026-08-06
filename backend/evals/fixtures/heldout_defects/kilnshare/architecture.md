# KilnShare — System Architecture

## Overview
A **Next.js** web app (responsive; no native apps in v1) with API routes against **PostgreSQL**. Deliberately a monolith: a two-sided marketplace's complexity lives in payments and trust flows, not in service topology.

## Components
- **Listings & search** — Postgres full-text + category/geo filters; availability stored as calendar blocks to prevent double-booking at the DB level
- **Booking engine** — state machine per booking: requested → confirmed → in-progress → returned → released | disputed; every transition audited
- **Payments** — Payments run through **Stripe Connect**: the renter is charged at booking, funds are held in escrow, the damage deposit auto-releases 48 hours after a dispute-free return, and the owner payout settles daily.
- **Trust layer** — Stripe Identity for both sides at first transaction; safety-quiz service gates kiln/laser bookings; two-way reviews unlock only after the booking closes
- **Messaging** — scoped to active bookings only (no open DMs); retained for dispute evidence
- **Dispute flow** — photo-documented handover checklist (before/after) attached to the booking record; support resolves against it, deposit and damage pool draw from the same case

## Data flow (a booking)
1. Renter passes the safety gate (if category requires) → requests slot → owner confirms
2. Stripe charge + deposit hold created; calendar block written transactionally
3. Handover: both sides complete the photo checklist in the booking screen
4. Return + 48h dispute window → deposit released, owner payout queued, reviews unlock

## Non-functional
- Deposit/payout money paths must be idempotent and reconciled nightly against Stripe
- Search is metro-scoped in v1 (two launch cities); no geo-sharding needed below ~50k listings

## Team & timeline
Two engineers, 3.5 months to v1: month 1 listings + booking calendar, month 2 Stripe Connect escrow + identity verification, month 3 messaging + reviews, final two weeks hardening and supply-side onboarding.
