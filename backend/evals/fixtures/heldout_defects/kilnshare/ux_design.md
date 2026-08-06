# KilnShare — UX Design

## Design philosophy
Two audiences, one rule each. Renters: **trust before checkout** — every screen answers "is this machine real, safe, and actually available?" Owners: **effortless listing** — the machine earns money without the owner becoming a customer-service desk.

## Critical flows
1. **Search → book** — metro-scoped browse with category and date filters; a listing page shows photos, hourly/daily rate, house rules, owner verification badge, and the availability calendar. Booking is one screen: slot, waiver signature, price breakdown with fees shown line-by-line.
2. **Safety gate** — first kiln/laser booking routes through the safety quiz (5-8 minutes, retakable); a passed badge persists on the profile so the friction is once per category, not per booking.
3. **Owner listing** — A guided three-step listing wizard (photos → availability → house rules) gets an owner live in under ten minutes.
4. **Handover checklist** — both parties photograph the machine state in the booking screen at pickup and return; the UI makes skipping feel unsafe rather than convenient, because this checklist is the dispute system's evidence.

## Key screens
- **Listing page** — trust elements above the fold (verification badge, review count, safety category label); price calculator with deposit shown before any commitment
- **Booking detail** — state timeline (confirmed → handover → in use → returned → released), checklist entry points, scoped messaging thread
- **Owner dashboard** — earnings, upcoming bookings, deposit/dispute status per booking

## Interaction notes
- Fees are never discovered at checkout: the 15% split and $3 protection fee appear on the listing page calculator
- Dispute entry is calm by design: "report an issue with this return" opens the checklist comparison first, not a complaint form
- Reviews are double-blind for 72 hours to prevent retaliation dynamics
