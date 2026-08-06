# KilnShare — Financial Model

## Revenue assumptions
- **Average booking value: $35** (blend of hourly kiln/printer sessions and daily laser rentals)
- **Take rate: 15%** → $5.25 platform revenue per booking; the $3 protection fee is earmarked for the damage pool, not counted as revenue
- Month-12 target: **$120k monthly GMV** ≈ 3,430 bookings/month → **~$18k monthly revenue**

## Unit economics
- **Revenue per booking:** $5.25
- **Variable cost per booking:** ~$1.75 (Stripe processing ≈ $1.32, support/dispute amortization ≈ $0.43) → **$3.50 contribution per booking**
- **Active renter behavior:** 1.8 bookings/month → **$6.30 monthly contribution per renter**
- **Monthly renter churn: 8%** → average active lifetime ≈ 12.5 months → **~37% of renters retained after 12 months**
- **LTV:** ~$79 ($6.30 × 12.5 months)
- **CAC (blended, month 6 target):** $20 → **LTV:CAC ≈ 3.9 : 1**
- **CAC payback:** ~3.2 months ($20 ÷ $6.30)

## Cost structure (monthly, at month-12 scale)
- Fixed burn: **$11,000/month** (two engineers, community/ops lead, hosting, legal/insurance counsel)
- Variable: scales with bookings per the contribution math above
- Damage pool: protection fees in ≈ $10.3k/month vs. target draw <2% of bookings; pool surplus is reserved, never P&L

## Break-even
Fixed burn ÷ booking contribution ≈ 3,150 bookings/month (~$110k GMV) → crossed around **month 11-12** on the GMV ramp; the model is utilization-led, so the sensitivity that matters is bookings-per-listing, not listing count.

## Sensitivity
- If average booking value drops to $28 (hourly mix shifts), contribution falls to $2.45 and break-even needs ~4,500 bookings/month → month 15+
- If churn runs 11%, LTV drops to ~$57 and CAC ceiling tightens to ~$15 for a 3.8:1 ratio

## Funding
$150k pre-seed covers the ~12-month pre-break-even gap including two-metro supply seeding; the damage pool is capitalized separately at $10k floor before launch.
