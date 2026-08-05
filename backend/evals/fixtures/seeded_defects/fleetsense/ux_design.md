# FleetSense — UX Specification

## Personas
- **Ayşe, dispatcher** — juggles 18 vans and a ringing phone; needs the morning plan done in 10 minutes, not 60
- **Kenan, driver** — mid-range Android phone, gloves half the day; anything requiring precision taps will fail

## Dispatcher console flows
1. **Morning planning** — drag CSV onto the board → stops appear grouped by suggested van → dispatcher adjusts by dragging between columns → "publish routes" pushes to all driver phones. A simple guided wizard covers the first-week learning curve.
2. **Live day view** — map + timeline hybrid; delayed stops bubble to the top; clicking a van shows its remaining stops and lets the dispatcher re-order or reassign mid-day.
3. **End-of-day report** — one screen: km, fuel estimate, cost/stop, exceptions (failed deliveries with photos).

## Driver app flows
- **Big-target design**: next-stop card fills half the screen; single thumb-reach action per state (navigate → arrived → photo → done)
- Offline banner is calm, not alarming — "route saved, will sync"
- Proof-of-delivery: camera opens pre-focused; photo + optional note; auto-queued upload

## Principles
- Dispatcher screen optimizes for *scanning* (dense, glanceable); driver screen optimizes for *doing* (huge targets, minimal text)
- No feature may add a mandatory tap to the driver's per-stop loop
- All alerts actionable: every delay alert offers reassign / notify-customer / ignore

## Accessibility
Driver app tested with gloves and in direct sunlight (contrast ≥ 7:1 on critical actions); console fully keyboard-operable for power dispatchers.
