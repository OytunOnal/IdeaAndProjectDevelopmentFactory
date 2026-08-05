# InvoiceFox — UX Specification

## Personas
- **Selin, freelance designer** — 8 invoices/month, hates confrontation, wants the tool to "be the bad cop politely"
- **Marco, micro-agency owner** — cares about cash-flow overview more than individual invoices

## Core flows
1. **Onboarding (target: <3 minutes)** — connect email → import or create first invoice → pick a tone template → activate default reminder sequence. One guided path, no empty-state dead ends.
2. **Invoice board** — kanban-style columns by status; overdue column is visually loudest; row click opens a side panel (edit, history, pause reminders).
3. **Sequence editor** — timeline view of reminder steps (day 3 friendly → day 10 neutral → day 21 firm); live preview of each email with the client's real name.
4. **Paid moment** — when Stripe confirms payment, a small celebration state + prompt to send a thank-you note. Positive loop, not just nagging.

## Principles
- Calm interface: no red alarms except genuinely overdue items
- Every automated email is previewable before the sequence activates — trust through transparency
- Empty states teach: each shows one example invoice with fake data

## Accessibility
Keyboard navigation for all board actions; WCAG AA contrast; email templates readable in dark-mode clients.
