<div align="center">

# 🏭 ProjectFactory

**A multi-agent AI factory that turns a one-line idea into a complete,
quality-scored project specification — with a human in the loop at every gate.**

[![Next.js](https://img.shields.io/badge/Next.js-16-000000?logo=nextdotjs&logoColor=white)](frontend)
[![FastAPI](https://img.shields.io/badge/FastAPI-Python_3.13-009688?logo=fastapi&logoColor=white)](backend)
[![LangGraph](https://img.shields.io/badge/LangGraph-14_live_agents-1C3C3C)](backend/app/agents)
[![Claude API](https://img.shields.io/badge/Claude-web__search_grounding-D97757?logo=anthropic&logoColor=white)](backend/app/agents/research.py)
[![CI](https://github.com/OytunOnal/IdeaAndProjectDevelopmentFactory/actions/workflows/ci.yml/badge.svg)](https://github.com/OytunOnal/IdeaAndProjectDevelopmentFactory/actions)

<img src="docs/screenshot.png" alt="ProjectFactory workspace" width="850">

</div>

## What it does

You describe an idea in one message. A pipeline of LangGraph agents interviews
you, researches the market with live web data, writes the full specification
set, stress-tests it, and hands you a ZIP:

```
💡 idea ──▶ 🗣️ Idea Analyst          conversational brief (one question at a time)
                 │  ✅ you approve
            🔍 Research               market · competitors · tech feasibility
                 │  ✅ you approve       (web-grounded via Claude web_search)
            📝 Specification          PRD · architecture · UX · GTM · financials
                 │  ✅ you approve
            🥊 Quality gate           rubric score /100 · devil's advocate · consistency
                 │  ✅ you approve
            📦 Packaging              implementation roadmap + 13-document ZIP
```

Every phase ends in a **decision card** — the pipeline never runs away from you.
While agents work, progress streams to the UI over WebSocket, documents appear
in the file tree as they are written, and everything survives a server restart.

## The agents

| Phase | Agent | Output |
|---|---|---|
| Discovery | `idea_analyst` | Structured brief via guided conversation |
| Discovery | `market_researcher` | TAM/SAM/SOM, trends — **live web data, cited** |
| Discovery | `competitor_analyst` | Landscape, gaps, positioning — **live web data** |
| Discovery | `tech_feasibility` | Stack alternatives, risks, recommendation |
| Specification | `spec_writer` | PRD with MoSCoW features + user stories |
| Specification | `architecture_designer` | System design, API, DB schema (mermaid) |
| Specification | `ux_strategist` | User flows, screen specs, design system |
| Specification | `gtm_strategist` | Launch plan, channels, first-1000-users plan |
| Specification | `financial_modeler` | Pricing, projections, unit economics |
| Quality | `quality_reviewer` | 100-point rubric score with structured JSON verdict |
| Quality | `devils_advocate` | Adversarial critique, ranked unvalidated assumptions |
| Quality | `consistency_checker` | Cross-document contradiction report |
| Packaging | `planning_agent` | Phased roadmap + sprint plan |
| Packaging | `doc_formatter` | Final 13-file document set (deterministic, no LLM) |

Plus an `orchestrator` (state-machine router), a `decision_handler` (HITL
gates with per-category autonomy levels), and discussion agents that answer
questions about the documents before you approve each phase.
`brand_strategist`, `legal_advisor`, `visual_designer` and
`design_system_architect` are speced ([docs/03](docs/03_AGENT_SPECIFICATIONS.md))
and stubbed — roadmap.

## AI engineering under the hood

This project demonstrates, in working code:

- **Agent orchestration with LangGraph** — a 25-node `StateGraph` with an
  orchestrator-router, conditional edges, and per-project checkpointing
  ([graph.py](backend/app/agents/graph.py), [orchestrator.py](backend/app/agents/orchestrator.py))
- **Human-in-the-loop design** — typed decision cards, phase gates,
  configurable autonomy (`ask` / `suggest` / `delegate` per decision category)
  ([decision_handler.py](backend/app/agents/decision_handler.py))
- **Tool use / grounding** — research agents call Claude's server-side
  `web_search` tool and return cited, current data
  ([research.py](backend/app/agents/research.py))
- **Multi-provider LLM layer with automatic fallback** — Google → Cerebras →
  Groq → DeepSeek → Anthropic, 429 retry with backoff, BYOK support, provider
  inferred from key prefix ([llm.py](backend/app/agents/llm.py))
- **Graceful degradation** — no Anthropic key? Research falls back to
  knowledge-only reports, clearly flagged `web_grounded: false`. The whole
  pipeline runs on free-tier providers.
- **Structured outputs** — the brief and the quality verdict are extracted as
  fenced JSON and validated before use
- **LLM-as-judge with a rubric** — an independent reviewer scores the specs
  /100 and returns a machine-readable PASS/FAIL verdict
- **Durable state** — LangGraph `AsyncSqliteSaver`: kill the server mid-project,
  restart, continue where you left off
- **Real-time progress** — agents emit transient WebSocket updates while they
  work; the REST response remains the source of truth
- **Deterministic where possible** — document assembly and the ZIP export are
  plain code, not LLM calls

## Quick start

Prerequisites: Python 3.13+ with [uv](https://docs.astral.sh/uv/), Node 20+.

```bash
git clone https://github.com/OytunOnal/IdeaAndProjectDevelopmentFactory.git
cd IdeaAndProjectDevelopmentFactory
make install                     # uv sync + npm install

# Backend config — one free LLM key is enough (Google AI Studio / Groq / Cerebras)
cp backend/.env.example backend/.env      # add at least one key

# Frontend config
cp frontend/.env.example frontend/.env.local

make dev-backend                 # FastAPI on :8000
make dev-frontend                # Next.js on :3000  (separate terminal)
```

Open `http://localhost:3000` — with no Supabase configured the app runs in
**demo mode** (no login) — describe an idea, and approve your way through the
pipeline. Export the ZIP from the file tree when it completes.

### Cost profile

| Mode | Research quality | Cost per full run |
|---|---|---|
| Free providers only | Knowledge-based estimates, flagged as such | **$0** |
| + `ANTHROPIC_API_KEY` | Live web search, cited sources | ~$0.20 (Haiku) |

Everything except research runs on free-tier providers either way.

## Repository layout

```
├── backend/                FastAPI + LangGraph
│   ├── app/agents/         the pipeline: graph, orchestrator, 14 agents
│   │   ├── llm.py          multi-provider layer (fallback, BYOK, streaming)
│   │   ├── research.py     web-grounded discovery agents
│   │   ├── specification.py · quality.py · packaging.py
│   │   └── graph.py        StateGraph wiring + SQLite checkpointing
│   ├── app/routers/        REST API (projects, pipeline, files, export)
│   ├── app/websocket/      live progress channel
│   └── tests/              pipeline flow tests (mocked LLMs) — no API keys needed
├── frontend/               Next.js 16 + TypeScript + Tailwind + Shadcn/UI
│   └── src/                workspace: chat + decision cards, file tree, viewer
├── docs/                   product docs: PRD, architecture, 19 agent specs,
│                           API contract, UI/UX spec, roadmap
└── Makefile                dev/install/lint/test shortcuts
```

## Testing

```bash
make test-backend    # 9 tests: full pipeline flow with mocked LLMs, persistence
make lint-backend    # ruff
cd frontend && npm run lint && npx tsc --noEmit
```

The pipeline tests drive idea → research → spec → quality → packaging through
the real LangGraph graph with mocked LLM calls — routing, gates, and state
transitions are verified without spending a token.

## Honest limitations / roadmap

- Four agents are speced but stubbed (brand, legal, visual design, design system).
- Free-tier rate limits are real: context windows sent to quality agents are
  truncated to fit Groq's 6k TPM; a paid key removes the constraint.
- Auth (Supabase magic-link) is optional and off by default; the SQL schema for
  a hosted Postgres deployment ships in `backend/migrations/`.
- Streaming responses are implemented in the LLM layer but the UI currently
  updates per-message, not per-token.

## License

All rights reserved — source available for portfolio review.
