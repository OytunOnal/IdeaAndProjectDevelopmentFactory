# PrepNest — System Architecture

## Overview
Mobile-first: a **React Native** app (iOS + Android) against a **FastAPI** backend with **PostgreSQL**. Session state and matching queues live in **Redis**. Everything runs as a single deployable service in v1 — no microservices.

## Components
- **Booking & matching service** — rules-based v1 matching (subject + exam track + tutor rating); returns 3 candidate slots within the 2-hour window
- **Video sessions** — LiveKit WebRTC rooms; recordings retained 90 days for safeguarding review
- **Question bank** — versioned content store, per-topic mastery scoring (simple spaced-repetition weights, no ML in v1)
- **Payments** — Stripe Billing for subscriptions, metered extra sessions
- **Parent digest** — weekly cron render of the mastery view, email via Postmark
- **Tutor onboarding** — ID verification (Stripe Identity) + background-screening provider webhook gate; tutors cannot go live before both clear

## Data flow (a session)
1. Student posts a stuck-concept photo → booking service offers slots
2. Match accepted → LiveKit room provisioned, both sides get push reminders
3. Session ends → recording archived (90-day retention), tutor payout ledger entry, mastery tracker updated
4. Parent digest picks up the delta in the Sunday render

## Non-functional
- Session join must work on low-end Android over 4G; LiveKit simulcast + audio-only fallback
- Recording storage is the main variable cost; lifecycle rule auto-deletes at day 90
- Uptime target 99.5%; exam-season evening peaks are 6× baseline, so booking and matching are queue-backed

## Team & timeline
Two engineers, 4 months to v1: months 1-2 booking + video core, month 3 question bank + parent digest, month 4 tutor-vetting hardening and closed launch.
