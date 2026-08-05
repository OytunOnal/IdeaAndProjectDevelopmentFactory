# FleetSense — Product Requirements Document

## Problem
Small delivery fleets (5-50 vans) plan routes in spreadsheets and WhatsApp; drivers waste 60-90 minutes/day on inefficient routes, and dispatchers have no live picture of the day.

## Target users
- Primary: dispatchers at local delivery/courier companies — desktop-heavy professionals, working under time pressure
- Secondary: fleet owners (want cost reports), drivers (mobile app consumers)

## Core features (v1)
1. Route planner — import the day's stops (CSV), optimized multi-van routes in <30s
2. Live map — van positions, ETA per stop, delay alerts
3. Driver mobile app — turn-by-turn stop list, proof-of-delivery photo, one-tap "delayed" flag
4. Daily cost report — km driven, fuel estimate, cost per stop

## Pricing
**$8 per van per month**, flat. No per-seat pricing — dispatchers and owners ride free.

## Scope
- In (v1): route optimization, live tracking, driver app (Android first), cost reports
- Out (v1): predictive maintenance, fuel-card integrations, iOS app, multi-depot optimization

## Driver privacy & consent
Live GPS tracking of employees is legally sensitive. v1 ships with: explicit driver consent flow in the app, tracking active only during shift hours, owner-visible audit log of location access, and per-country data-retention defaults (KVKK/GDPR aligned).

## Success metrics
- ≥15% average route-time reduction within first month of use
- 70% of drivers using proof-of-delivery daily by week 4
