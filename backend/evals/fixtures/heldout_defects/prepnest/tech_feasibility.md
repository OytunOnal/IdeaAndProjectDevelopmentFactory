# PrepNest — Technical Feasibility

## Verdict
Feasible for a 2-engineer team in ~4 months. Nothing here is research-grade; the risk is operational (safeguarding, supply liquidity), not technical.

## Recommended stack
**React Native (iOS+Android) + FastAPI + PostgreSQL + Redis + LiveKit (WebRTC) + Stripe Billing + Stripe Identity + Postmark.** One deployable backend service in v1; matching is rules-based (subject + exam track + rating) — no ML needed to hit the 2-hour booking promise.

## Hard parts, honestly assessed
- **WebRTC on low-end Android over 4G** — the single biggest UX risk. LiveKit simulcast plus an audio-only fallback mode is mandatory, not optional; budget a full week of device-lab testing.
- **Safeguarding pipeline** — recording every session (90-day retention), tutor ID verification + background-check gating, and an in-session report path are all integration work with third-party providers, but they are *launch-blocking*: no partial launch without them.
- **Evening peak load** — exam-season peaks run ~6× baseline and concentrate 19:00-23:00. Queue-backed booking/matching and pre-provisioned LiveKit capacity handle it; this is capacity planning, not architecture.
- **Recording storage cost** — the main variable infra cost; an S3 lifecycle rule deleting at day 90 keeps it bounded and matches the retention policy.

## What NOT to build in v1
- ML-based matching or answer-quality scoring (rules + ratings suffice at this scale)
- Group rooms / shared whiteboards (out of scope, and WebRTC complexity jumps an order of magnitude)
- A tutor self-serve marketplace (vetting gate is the product's trust core; keep supply curated)

## Timeline
Months 1-2: booking + video core. Month 3: question bank + parent digest. Month 4: vetting hardening, device-lab pass, closed launch.
