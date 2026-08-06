# KilnShare — Product Requirements Document

## Problem
Hobbyist makers can't justify owning $2,000-8,000 equipment (kilns, laser cutters, resin printers) they'd use twice a month — while owners' machines sit idle more than 90% of the time. Makerspaces partially solve this but bind users to memberships, fixed hours, and waitlists.

## Target users
- Primary: hobbyist makers (ceramics, laser-cut goods, 3D printing) needing occasional access
- Secondary: equipment owners (home studios, small workshops) monetizing idle machines

## Core features (v1)
1. Listings & booking — searchable equipment listings with hourly/daily rates and real availability calendar
2. Escrow payments — renter charged at booking; owner paid out after dispute-free return; damage deposit held automatically
3. Safety certification gate — dangerous categories (kilns, lasers) require a passed safety quiz + owner-confirmed induction before first booking
4. Verified profiles & reviews — ID-verified users on both sides, two-way reviews after each booking

## Business model
**15% take rate** on every booking (10% renter fee + 5% owner fee), plus a $3 per-booking protection fee that funds the damage pool. No listing fees, no subscription.

## Scope
- In (v1): listings, booking, escrow + deposits, safety gate, reviews, messaging inside bookings
- Out (v1): smart-lock/IoT access integration, delivery or logistics, B2B fleet accounts, consumables marketplace, insurance products beyond the damage pool

## Damage protection & liability
Dangerous equipment changes hands here; this section is load-bearing. v1 ships with: damage protection up to **$2,500 per booking** funded by the protection fee, a signed liability waiver in the booking flow, the safety-certification gate for kiln/laser categories, and a photo-documented handover checklist that anchors dispute resolution.

## Success metrics
- 70% of listed machines get ≥1 booking in their first month listed
- <10% of bookings end in a dispute; <2% draw on the damage pool
