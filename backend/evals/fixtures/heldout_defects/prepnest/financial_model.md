# PrepNest — Financial Model

## Revenue assumptions
- Single paid plan: Plus at **$19/month**, 3 micro-sessions included; extra sessions $5 (assume 0.4 extras/subscriber/month)
- Free→Plus conversion: 6% of active free users (the 1-session/month free cap creates a monthly decision point)
- Month-12 target: 700 paying subscribers → **$13,300 MRR** + ~$1,400/month in extra-session sales

## Unit economics
- **ARPU:** $19/month
- **Direct cost per subscriber:** ~$10/month (3 tutor payouts at $3/session + ~$1 video/recording infra) → **$9 monthly contribution**
- **CAC (blended, month 6 target):** $25
- **Average paid lifetime:** ~16 months (6% monthly churn, seasonal spike after exam month averaged in)
- **LTV:** $144 (≈ $9 contribution × 16-month lifetime)
- **LTV:CAC ≈ 5.8 : 1** — comfortably above the 3:1 threshold
- **CAC payback:** ~2.8 months ($25 ÷ $9)

## Cost structure (monthly, at month-12 scale)
- Tutor payouts: ~$6,700 (scales with sessions; included in contribution above)
- Video infrastructure + recording storage (LiveKit + S3 lifecycle): $900
- Background checks: $28 per tutor onboarded (~$400/month at steady tutor intake)
- Stripe fees ~2.9% (pass-through), tools & misc $250
- Fixed team + ops burn: **$9,000/month** (two engineers part-cash part-equity, safeguarding reviewer stipend, legal)

## Break-even
Fixed burn ÷ contribution ≈ 1,000 paying subscribers → roughly **month 14** on current growth assumptions; sensitivity: if churn runs at 9% (bad seasonality), lifetime drops to ~11 months, LTV to ~$99, and break-even slips to month 18.

## Funding
Angel pre-seed of $120k covers the 14-month pre-break-even gap with margin; no institutional raise planned before season-2 retention data exists.
