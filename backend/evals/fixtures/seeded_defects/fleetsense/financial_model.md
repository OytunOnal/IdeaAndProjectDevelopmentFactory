# FleetSense — Financial Model

## Revenue assumptions
- **$8 per van per month** (per PRD/GTM), average fleet size 15 vans → **$120/month per fleet**
- Month-12 target: 120 paying fleets → **$14,400 MRR**
- Trial→paid conversion 25% (with-your-own-stops demo), sensitivity run at 15%

## Unit economics
- **ARPU (per fleet):** $120/month
- **CAC (blended):** $360 — partnerships are cheap, outbound is not; weighted by channel mix
- **Monthly fleet churn: 3%** → average paid lifetime ≈ 33 months → **~69% of fleets retained after 12 months**
- **LTV:** ≈ $3,960 (33 × $120)
- **LTV:CAC ≈ 11 : 1** — strong, driven by B2B stickiness (switching means retraining drivers)

## Cost structure (monthly, month-12 scale)
- Infrastructure incl. map tiles & geocoding APIs: $900 (maps API is the biggest line — capped via tile caching)
- OR-Tools solver compute: $150
- Two founder-engineers at reduced salary from month 6: $6,000
- Support (part-time, TR+EN): $800 from month 8

## Break-even
Crosses at ~75 paying fleets ≈ **month 10** on the base case; the 15%-conversion sensitivity pushes it to month 15.

## Funding
Pre-seed target $150k at month 3 (after design-partner metrics exist) to cover salaries through break-even; bootstrap fallback plan trims outbound and slips launch by one quarter.
