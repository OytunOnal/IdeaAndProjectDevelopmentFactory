# FleetSense — System Architecture

## Overview
Two clients (dispatcher web console, driver Android app) against one cloud backend. The driver app is **offline-tolerant**: it caches the day's route and queues proof-of-delivery uploads, syncing when connectivity returns; live tracking and re-optimization require a connection by nature.

## Components
- **Dispatcher console (React)** — route planning board, live map (WebSocket updates)
- **API (FastAPI)** — auth, fleet/route CRUD, report generation
- **Optimization service (Python, OR-Tools)** — VRP solver behind a job queue; 50-van/600-stop day solves in ~10-20s
- **PostgreSQL + PostGIS** — fleets, routes, stops, geo-queries
- **Location pipeline** — driver app posts GPS pings (adaptive 15-60s interval); Redis stream → map fanout + trip log
- **Push notifications (FCM)** — route changes, delay alerts

## Key decisions
- OR-Tools over a routing SaaS: keeps per-van cost near zero at our price point; trade-off is owning solver tuning
- GPS ping interval adapts to battery level and movement — battery drain is the #1 driver-app complaint in this market
- Single region deploy for v1; multi-region only if a customer demands data residency

## Delivery plan
Two engineers, 4 months to v1: months 1-2 route planner + driver app core, month 3 live map + reports, month 4 hardening and pilot onboarding.

## Risks
- Android device fragmentation → test matrix of the 6 most common cheap devices
- GPS gaps in urban canyons → dead-reckoning between pings, honest "last seen" timestamps on the map
