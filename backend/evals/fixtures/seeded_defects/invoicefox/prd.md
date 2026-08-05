# InvoiceFox — Product Requirements Document

## Problem
Freelancers lose 5-15% of annual income to late or unpaid invoices, and chasing payments by hand is awkward and time-consuming.

## Target users
- Primary: solo freelancers (design, dev, writing) sending 3-20 invoices/month
- Secondary: micro-agencies (2-5 people)

## Core features (v1)
1. Invoice tracking dashboard — status per invoice (draft/sent/viewed/overdue/paid)
2. Automated reminder sequences — polite, escalating emails on a configurable cadence; Free plan tracks up to 5 active invoices per month
3. Payment-link integration via Stripe
4. Tone templates — friendly / neutral / firm, per client

## Pricing
- Free: up to 5 active invoices/month, 1 reminder sequence
- Pro: $12/month — unlimited invoices, custom sequences, analytics

## Scope
- In (v1): tracking, reminders, Stripe links, basic analytics
- Out (v1): team collaboration workspace, multi-currency, accounting integrations (QuickBooks/Xero), mobile apps

## Compliance & privacy
Invoices contain personal and financial data. v1 ships with: GDPR-compliant data handling (EU users), data export & delete-my-account, TLS everywhere, no card data stored on our side (PCI scope stays with Stripe).

## Success metrics
- 40% of active users recover ≥1 overdue invoice in first month
- <2% monthly churn on Pro after month 3
