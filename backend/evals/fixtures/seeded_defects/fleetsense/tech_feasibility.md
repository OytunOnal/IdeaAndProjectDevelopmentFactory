# FleetSense — Tech Feasibility

## Requirements driving tech decisions
- Functional: CSV stop import, multi-van VRP optimization (<30s for 50 vans/600 stops), live GPS pipeline, offline-tolerant driver app (Android first), proof-of-delivery, daily cost reports.
- Non-functional: map/geocoding API cost control; battery-friendly tracking; cheap-Android reality; per-country location-data compliance (KVKK/GDPR).

## Stack alternatives
1. **React console + FastAPI + PostGIS + OR-Tools + Redis streams + FCM** — proven open-source VRP core keeps per-van costs near zero; PostGIS handles geo queries; ~$300-900/mo at early scale (map tiles dominate). Learning curve: moderate (solver tuning).
2. Routing-API-first (Google Cloud Fleet Routing / Mapbox Optimization) — faster to first demo; per-request pricing erodes the flat-$8 unit economics at daily-optimization volumes; lock-in.
3. Node/TypeScript end-to-end with VROOM solver — viable; VROOM strong but OR-Tools' constraint flexibility (time windows, capacities) fits messier real fleets better.

## Recommended stack
Option 1. Rationale: the business model (flat $8/van) only works if optimization marginal cost ≈ 0 — that means owning an open-source solver behind a job queue, plus tile caching and geocode caching to cap the map-API line.

## Technical risks
- Map/geocoding costs at scale → aggressive caching, self-hosted tiles/OSRM as a scaling path.
- Driver-app battery/permission friction on cheap Androids → adaptive ping intervals, foreground-service discipline, test matrix of common devices.
- GPS gaps in dense urban areas → dead-reckoning between pings; honest "last seen" UI.
- Solver tuning drift (real fleets violate tidy assumptions) → per-fleet constraint presets + fallback greedy routes.

## MVP technical scope
CSV import → optimized routes → publish to driver app → live map + delay flags → end-of-day cost report. Defer: multi-depot, iOS, predictive maintenance, fuel-card integrations. Two engineers, ~4 months to pilot-ready at the recommended stack.
