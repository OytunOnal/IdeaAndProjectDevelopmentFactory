# ProjectFactory - Implementation Roadmap

> Version: 1.0 | Last Updated: 2026-05-11

---

## Overview

4-phase implementation plan. Each phase produces a deployable increment.

```
Phase 1: Foundation          Phase 2: Research Pipeline
[Chat + 2 agents + BYOK]    [+3 agents + parallel + pipeline viz]
        ↓                            ↓
Phase 3: Spec Engine         Phase 4: Polish & Advanced
[+4 agents + editor + QA]   [+3 agents + dashboard + export]
```

---

## Phase 1: Foundation (Weeks 1-3)

> Goal: User can describe an idea and get a structured brief through conversational chat.

### Deliverables
- [ ] Project scaffolding (Next.js + FastAPI monorepo)
- [ ] Authentication (Supabase Auth)
- [ ] BYOK API key management (encrypted storage)
- [ ] LangGraph setup with 2 agents: Orchestrator + Idea Analyst
- [ ] Chat interface (WebSocket streaming)
- [ ] Basic project CRUD
- [ ] Deploy to Vercel + Railway

### Tasks

#### Week 1: Scaffolding & Infrastructure
```
1.1  Initialize monorepo structure
     /frontend  (Next.js 15, TypeScript, Tailwind, Shadcn)
     /backend   (Python 3.12, FastAPI, Poetry/uv)
     
1.2  Set up Supabase project
     - Auth (email + GitHub OAuth)
     - PostgreSQL tables: users, projects
     
1.3  Backend: FastAPI boilerplate
     - Project structure (routers, services, models)
     - CORS, error handling, logging
     - Health check endpoint
     - Supabase JWT validation middleware
     
1.4  Frontend: Next.js boilerplate
     - App Router setup
     - Shadcn/UI installation
     - Auth flow (sign up, sign in, session)
     - Basic layout shell (header, 3-panel placeholder)
     
1.5  API key management
     - POST /api/settings/api-keys (encrypt + store in Redis)
     - GET /api/settings/api-keys (check status)
     - Key validation (test call to provider)
     - Frontend: Settings page with key input
```

#### Week 2: LangGraph + First Agents
```
2.1  LangGraph integration
     - Install langgraph, litellm
     - Define ProjectState schema
     - Create graph skeleton with placeholder nodes
     - Checkpointing setup (PostgreSQL checkpointer)
     
2.2  Orchestrator agent
     - System prompt
     - Routing logic (for now: START → idea_analyst only)
     - State management
     
2.3  Idea Analyst agent
     - System prompt
     - Decision point system (DecisionPoint model)
     - Conversational flow: ask questions → build brief
     - Output: structured IdeaBrief
     
2.4  Decision handler node
     - Pause pipeline on decision point
     - Store pending decision in state
     - Resume on user input
     - Autonomy level check (ask/suggest/delegate)
     
2.5  WebSocket setup
     - Socket.io server (FastAPI)
     - Socket.io client (Next.js)
     - Events: chat:message, agent:streaming, decision:required
     - Connection authentication
```

#### Week 3: Chat UI + Integration
```
3.1  Chat panel component
     - Message list with agent avatars
     - Streaming text display
     - Message input with send button
     - Auto-scroll
     
3.2  Decision card component
     - Inline decision UI in chat
     - Option buttons
     - "You decide" and "Tell me more" options
     - Free-form text input
     - Post-resolution read-only state
     
3.3  Agent status component
     - Active agent indicator
     - Completed agents list
     - Elapsed time
     
3.4  Project creation flow
     - New project page
     - Initial message → starts pipeline
     - Redirects to workspace
     
3.5  End-to-end testing
     - Create project → chat with Idea Analyst → get brief
     - Test decision points
     - Test streaming
     - Test resume after page reload (checkpointing)
     
3.6  Deploy
     - Vercel (frontend)
     - Railway (backend + Redis)
     - Supabase (production project)
     - Environment variables
     - Basic CI (GitHub Actions: lint + type check)
```

### Phase 1 Exit Criteria
- [ ] User can sign up, add API key, create project
- [ ] User can chat with Idea Analyst and receive structured brief
- [ ] Decision points work (ask, delegate)
- [ ] Chat streams in real-time
- [ ] Pipeline state persists across page reloads
- [ ] Deployed and accessible via URL

---

## Phase 2: Research Pipeline (Weeks 4-6)

> Goal: Three research agents run in parallel, user reviews findings, discovery loop works.

### Deliverables
- [ ] 5 new agents: Market Researcher, Competitor Analyst, Tech Feasibility, Brand Strategist, Legal Advisor
- [ ] Parallel agent execution (LangGraph fan-out - 5 agents)
- [ ] Web search tool for research agents
- [ ] Domain/handle availability check tool (for Brand Strategist)
- [ ] User checkpoint after research
- [ ] Discovery loop (idea ↔ research iteration)
- [ ] Pipeline visualization (basic)
- [ ] File explorer (basic)

### Tasks

#### Week 4: Research Agents
```
4.1  Web search tool
     - Integration with Tavily / SerpAPI / Brave Search API
     - Rate limiting
     - Result formatting for LLM consumption
     
4.2  Market Researcher agent
     - System prompt with TAM/SAM/SOM framework
     - Web search integration
     - Decision points (market segment, geography)
     - Output: market_research dict
     
4.3  Competitor Analyst agent
     - System prompt with competitive matrix framework
     - Web search integration
     - Decision points (differentiation strategy, pricing)
     - Output: competitor_analysis dict
     
4.4  Tech Feasibility agent
     - System prompt with evaluation framework
     - Decision points (stack selection, build vs buy)
     - Output: tech_feasibility dict

4.5  Brand Strategist agent
     - System prompt with naming + identity framework
     - Domain availability check tool (web search based)
     - Social media handle check
     - Decision points: name selection (always ask user)
     - Output: brand_identity dict

4.6  Legal Advisor agent
     - System prompt with compliance framework
     - Web search for regulations
     - Decision points: legal blockers, compliance scope
     - Output: legal_requirements dict
```

#### Week 5: Parallel Execution + Discovery Loop
```
5.1  LangGraph fan-out for research
     - Send() to 5 agents simultaneously
     - Fan-in: collect all 5 results
     - Handle partial failures
     
5.2  User checkpoint node
     - After research → mandatory user review
     - Present research summary
     - Options: approve, revise idea, redo specific research
     
5.3  Discovery loop
     - Idea ↔ Research iteration
     - Max 5 iterations
     - Research findings can trigger idea revision
     - Orchestrator manages loop logic
     
5.4  Agent finding presentation
     - present_finding() tool for agents
     - Important findings shown to user in real-time
     - User can respond to findings during research
```

#### Week 6: Pipeline Viz + File Explorer
```
6.1  Pipeline visualization (React Flow)
     - Node components for each agent
     - Status indicators (running, complete, waiting)
     - Progress bars on active nodes
     - Edge animations
     - Phase grouping
     
6.2  File explorer (basic)
     - Tree view of project files
     - Status icons per file
     - Click → view file content (read-only)
     
6.3  Document viewer (basic)
     - Markdown preview (react-markdown)
     - File metadata header
     - No editing yet
     
6.4  Status bar
     - Current phase
     - Active agent
     - Cost tracker
     - Pause/Stop buttons
     
6.5  Integration testing
     - Full discovery loop: idea → research → review → approve
     - Parallel research agents
     - Resume from checkpoint
```

### Phase 2 Exit Criteria
- [ ] 5 research agents produce quality reports (including brand + legal)
- [ ] Brand Strategist generates name options with domain availability
- [ ] Research runs in parallel (visible in UI)
- [ ] User checkpoint pauses pipeline for review
- [ ] Discovery loop allows idea refinement
- [ ] Pipeline visualization shows live progress
- [ ] File explorer shows generated files
- [ ] Documents viewable in markdown preview

---

## Phase 3: Specification Engine (Weeks 7-9)

> Goal: Full specification pipeline produces complete project documentation.

### Deliverables
- [ ] 7 new agents: Spec Writer, Architecture Designer, UX Strategist, Visual Designer, Design System Architect, GTM Strategist, Financial Modeler
- [ ] Quality Reviewer agent
- [ ] Template engine (category-specific)
- [ ] Document editor (Monaco)
- [ ] Wireframe preview (render React components in browser)
- [ ] Quality scoring dashboard (updated rubric with brand/legal/financial)
- [ ] Quality feedback loop (fail → revise → re-check)

### Tasks

#### Week 7: Specification Agents
```
7.1  Spec Writer agent
     - System prompt with PRD framework
     - Reads all research outputs (including brand + legal)
     - Produces: PRD, user stories, feature specs
     - Decision points: MVP scope, feature priorities
     
7.2  Architecture Designer agent
     - System prompt with architecture patterns
     - Reads PRD + tech feasibility
     - Produces: architecture doc, API spec, DB schema
     - Decision points: architecture style, DB choice
     
7.3  UX Strategist agent
     - System prompt with UX frameworks
     - Reads PRD + competitor analysis
     - Produces: user flows, wireframe descriptions
     - Decision points: navigation pattern, design system
     
7.4  Visual Designer agent
     - System prompt with React/Tailwind wireframe generation
     - Reads UX flows + PRD features + brand identity
     - Produces: wireframe React components (.tsx files)
     - Platform renders components in preview panel
     
7.5  Design System Architect agent
     - System prompt with design token framework
     - Reads brand identity + UX requirements
     - Produces: tailwind.config.ts, globals.css, typography.md
     
7.6  GTM Strategist agent
     - System prompt with go-to-market framework
     - Reads market research + competitor analysis + brand
     - Produces: launch plan, channel strategy, first 1000 users plan
     - Decision points: primary channel, launch platform
     
7.7  Financial Modeler agent
     - System prompt with financial projection framework
     - Reads market research + competitor pricing + GTM
     - Produces: 12-month projection, unit economics, break-even
     - Decision points: pricing model, funding strategy
```

#### Week 8: Quality + Template Engine
```
8.1  Quality Reviewer agent
     - System prompt with scoring rubric
     - Reads all spec documents
     - Produces: quality score, gap list, revision instructions
     - Independent review (different prompt context)
     
8.2  Quality feedback loop
     - Score < 80 → route back to spec agents with feedback
     - Max 3 revision iterations
     - Track score improvement per iteration
     
8.3  Template engine
     - Load category templates from 99_TEMPLATES
     - Map agent outputs to template sections
     - Jinja2 rendering
     
8.4  Quality dashboard (center panel)
     - Score visualization (gauge + bar chart)
     - Gap list with severity
     - Score history (across iterations)
```

#### Week 9: Document Editor + Wireframe Preview
```
9.1  Monaco Editor integration
     - Markdown language support
     - Syntax highlighting
     - Preview/Raw toggle
     - Auto-save with debounce
     
9.2  Wireframe preview system
     - Render React/Tailwind wireframe components in iframe sandbox
     - Preview/Code toggle for .tsx wireframe files
     - Hot reload on edit
     
9.3  Agent edit notifications
     - When agent modifies a file, show inline diff
     - Accept/Reject changes
     - Version tracking
     
9.4  File status management
     - Draft → Reviewed → Final
     - Status visible in file explorer
     
9.5  Integration testing
     - Full pipeline: idea → research → specs → quality
     - Quality fail → revision loop
     - User edits document → re-check quality
     - Wireframe preview renders correctly
```

### Phase 3 Exit Criteria
- [ ] Complete spec documents generated for a test project (including brand, legal, GTM, financial)
- [ ] Wireframe components render in preview panel
- [ ] Design system outputs valid tailwind.config.ts and CSS
- [ ] Quality score calculated with updated rubric (brand/legal/financial categories)
- [ ] Feedback loop improves quality score
- [ ] Documents editable with Monaco Editor
- [ ] Template engine produces correct file structure (with new folders: 06_LEGAL, wireframes/, design_system/)
- [ ] End-to-end: idea to scored specification

---

## Phase 4: Polish & Advanced (Weeks 10-12)

> Goal: Production-ready with all agents, multi-project, export.

### Deliverables
- [ ] 3 final agents: Devil's Advocate, Consistency Checker, Doc Formatter, Planning Agent
- [ ] Multi-project dashboard
- [ ] Export (ZIP download)
- [ ] Decision history view
- [ ] Agent activity log
- [ ] Performance optimization
- [ ] Landing page

### Tasks

#### Week 10: Remaining Agents
```
10.1 Devil's Advocate agent
     - Challenge report generation
     - Risk assessment
     - Display in quality dashboard
     
10.2 Consistency Checker agent
     - Cross-document validation
     - Inconsistency report
     
10.3 Doc Formatter agent
     - Template application
     - File structure generation
     - INDEX.md generation
     - Cross-reference linking
     
10.4 Planning Agent
     - Sprint plan generation
     - Roadmap creation
     - Budget estimation
```

#### Week 11: Dashboard + Export
```
11.1 Multi-project dashboard
     - Project cards with status
     - Phase progress indicators
     - Quality score badges
     - Sort/filter options
     
11.2 Export system
     - ZIP generation with all project files
     - PDF option (markdown → PDF)
     - Download endpoint with temp tokens
     
11.3 Decision history
     - Timeline view of all decisions
     - Filter by agent, category
     - Who decided (user vs agent)
     
11.4 Agent activity log
     - Detailed log per agent
     - Token usage per agent
     - Duration per agent
```

#### Week 12: Polish + Launch
```
12.1 Landing page
     - Value proposition
     - Feature highlights
     - Demo video/GIF
     - Sign up CTA
     
12.2 Performance optimization
     - Frontend bundle optimization
     - API response caching
     - WebSocket reconnection handling
     - Error recovery
     
12.3 README and documentation
     - GitHub README with screenshots
     - Architecture overview for portfolio
     - Setup instructions
     - Contributing guide
     
12.4 Final testing
     - End-to-end: complete project generation
     - Multi-project concurrency
     - Edge cases: API key expires mid-pipeline
     - Error handling: agent failure recovery
     
12.5 Production deployment
     - Custom domain
     - SSL
     - Monitoring (Sentry)
     - Analytics (PostHog/Plausible)
```

### Phase 4 Exit Criteria
- [ ] All 18 agents functional
- [ ] Complete project generated end-to-end
- [ ] Multi-project dashboard working
- [ ] Export produces valid ZIP
- [ ] Landing page live
- [ ] GitHub repo with good README
- [ ] Portfolio-ready

---

## Tech Debt & Future Work

### Known Tech Debt (Accept for MVP)
- No unit tests (add post-MVP)
- No i18n (English only)
- No rate limiting on API (add before scale)
- WebSocket reconnection is basic (improve for production)
- No caching on LLM responses (potential cost saving)

### Post-MVP Features
| Feature | Priority | Effort |
|---------|----------|--------|
| Code generation handoff (Cursor/Claude Code) | High | Large |
| Team collaboration (real-time multi-user) | High | Large |
| Custom agent creation | Medium | Large |
| API access (programmatic pipeline) | Medium | Medium |
| Template marketplace | Low | Medium |
| Mobile app (React Native) | Low | Large |
| Self-hosted option (Docker) | Medium | Medium |
| Figma export (wireframes → Figma) | Medium | Medium |
| AI UI generation (image-based mockups) | Medium | Large |
| v0.dev-style interactive UI builder | Low | Large |
| OAuth providers (more options) | Low | Small |
| Webhook notifications | Low | Small |
| Audit log | Low | Small |

---

## Repository Structure

```
projectfactory/
├── frontend/
│   ├── src/
│   │   ├── app/                    # Next.js App Router
│   │   │   ├── (auth)/             # Auth pages (sign in, sign up)
│   │   │   ├── dashboard/          # Dashboard page
│   │   │   ├── project/
│   │   │   │   ├── [id]/           # Project workspace
│   │   │   │   └── new/            # New project
│   │   │   ├── settings/           # Settings page
│   │   │   ├── layout.tsx
│   │   │   └── page.tsx            # Landing page
│   │   ├── components/
│   │   │   ├── chat/               # Chat panel components
│   │   │   │   ├── ChatPanel.tsx
│   │   │   │   ├── MessageList.tsx
│   │   │   │   ├── MessageBubble.tsx
│   │   │   │   ├── DecisionCard.tsx
│   │   │   │   ├── AgentStatus.tsx
│   │   │   │   └── MessageInput.tsx
│   │   │   ├── pipeline/           # Pipeline visualization
│   │   │   │   ├── PipelineGraph.tsx
│   │   │   │   ├── AgentNode.tsx
│   │   │   │   ├── PhaseGroup.tsx
│   │   │   │   └── StatusBadge.tsx
│   │   │   ├── editor/             # Document editor
│   │   │   │   ├── DocumentViewer.tsx
│   │   │   │   ├── MarkdownPreview.tsx
│   │   │   │   ├── MonacoEditor.tsx
│   │   │   │   └── DiffView.tsx
│   │   │   ├── explorer/           # File explorer
│   │   │   │   ├── FileExplorer.tsx
│   │   │   │   ├── FileTree.tsx
│   │   │   │   └── FileItem.tsx
│   │   │   ├── quality/            # Quality dashboard
│   │   │   │   ├── QualityDashboard.tsx
│   │   │   │   ├── ScoreGauge.tsx
│   │   │   │   └── GapList.tsx
│   │   │   ├── layout/             # Layout components
│   │   │   │   ├── Header.tsx
│   │   │   │   ├── StatusBar.tsx
│   │   │   │   ├── ThreePanel.tsx
│   │   │   │   └── ProjectSelector.tsx
│   │   │   └── ui/                 # Shadcn components
│   │   ├── hooks/                  # Custom React hooks
│   │   │   ├── useSocket.ts
│   │   │   ├── useProject.ts
│   │   │   └── useChat.ts
│   │   ├── stores/                 # Zustand stores
│   │   │   ├── projectStore.ts
│   │   │   ├── chatStore.ts
│   │   │   └── pipelineStore.ts
│   │   ├── lib/                    # Utilities
│   │   │   ├── api.ts              # REST API client
│   │   │   ├── socket.ts           # WebSocket client
│   │   │   └── supabase.ts         # Supabase client
│   │   └── types/                  # TypeScript types
│   │       ├── project.ts
│   │       ├── agent.ts
│   │       ├── decision.ts
│   │       └── pipeline.ts
│   ├── public/
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   └── package.json
│
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app entry
│   │   ├── config.py               # Settings and env vars
│   │   ├── routers/
│   │   │   ├── projects.py         # Project CRUD endpoints
│   │   │   ├── settings.py         # API keys, preferences
│   │   │   ├── files.py            # Project file endpoints
│   │   │   └── export.py           # Export endpoints
│   │   ├── services/
│   │   │   ├── project_service.py
│   │   │   ├── pipeline_service.py
│   │   │   ├── key_service.py      # API key encryption
│   │   │   └── export_service.py
│   │   ├── agents/
│   │   │   ├── graph.py            # LangGraph graph definition
│   │   │   ├── state.py            # ProjectState schema
│   │   │   ├── orchestrator.py
│   │   │   ├── idea_analyst.py
│   │   │   ├── market_researcher.py
│   │   │   ├── competitor_analyst.py
│   │   │   ├── tech_feasibility.py
│   │   │   ├── brand_strategist.py
│   │   │   ├── legal_advisor.py
│   │   │   ├── spec_writer.py
│   │   │   ├── architecture_designer.py
│   │   │   ├── ux_strategist.py
│   │   │   ├── visual_designer.py
│   │   │   ├── design_system_architect.py
│   │   │   ├── gtm_strategist.py
│   │   │   ├── financial_modeler.py
│   │   │   ├── quality_reviewer.py
│   │   │   ├── devils_advocate.py
│   │   │   ├── consistency_checker.py
│   │   │   ├── doc_formatter.py
│   │   │   └── planning_agent.py
│   │   ├── tools/
│   │   │   ├── web_search.py       # Web search tool
│   │   │   ├── file_writer.py      # File generation tool
│   │   │   ├── decision.py         # Decision point tool
│   │   │   ├── template_engine.py  # Template rendering
│   │   │   └── quality_scorer.py   # Quality calculation
│   │   ├── models/
│   │   │   ├── project.py          # Pydantic models
│   │   │   ├── decision.py
│   │   │   ├── agent.py
│   │   │   └── pipeline.py
│   │   ├── db/
│   │   │   ├── supabase.py         # Supabase client
│   │   │   └── redis.py            # Redis client
│   │   └── websocket/
│   │       ├── manager.py          # WebSocket connection manager
│   │       └── events.py           # Event handlers
│   ├── templates/                  # Project templates (from 99_TEMPLATES)
│   │   ├── saas/
│   │   ├── fintech/
│   │   ├── mobile/
│   │   ├── ai_ml/
│   │   ├── infrastructure/
│   │   └── multi_platform/
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
│
├── .github/
│   └── workflows/
│       ├── frontend-ci.yml
│       └── backend-ci.yml
│
├── docs/                           # This documentation
│   ├── 01_PRD.md
│   ├── 02_SYSTEM_ARCHITECTURE.md
│   ├── 03_AGENT_SPECIFICATIONS.md
│   ├── 04_API_AND_DATA_MODELS.md
│   ├── 05_UI_UX_SPECIFICATION.md
│   └── 06_IMPLEMENTATION_ROADMAP.md
│
├── README.md
├── LICENSE
└── .gitignore
```
