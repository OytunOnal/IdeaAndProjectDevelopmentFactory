# InvoiceFox — Financial Model

## Revenue assumptions
- Single paid plan: Pro at **$12/month** (matches PRD pricing; no annual discount in v1)
- Free→Pro conversion: 8% of active free users (industry range 2-10%; we sit mid-high because the 5-invoice limit bites monthly)
- Month-12 target: 600 paying users → **$7,200 MRR**

## Unit economics
- **ARPU:** $12/month
- **CAC (blended, month 6 target):** $40
- **Average paid lifetime:** 12 months (assumes ~8% monthly churn early, improving to <5%)
- **LTV:** $144 (12 × $12)
- **LTV:CAC ≈ 3.6 : 1** — healthy above the 3:1 rule-of-thumb threshold

## Cost structure (monthly, at month 12 scale)
- Infrastructure (hosting, DB, Redis): $180
- Email delivery (Postmark, ~120k sends): $220
- Stripe fees: ~2.9% of payment volume (pass-through, not revenue cost)
- Tools & misc: $150
- Founder salary deferred until month 9; contractor design budget $500/mo from month 4

## Break-even
Fixed+variable costs cross MRR at roughly **month 14** at current assumptions; sensitivity: if conversion drops to 5%, break-even slips to month 19.

## Funding
Bootstrapped; no external raise planned for v1. A 6-month runway buffer ($15k) covers the pre-revenue period.
