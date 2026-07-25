# ProjectFactory - System Architecture

> Version: 1.0 | Last Updated: 2026-05-11

---

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND                                  │
│                   Next.js 15 + TypeScript                        │
│                                                                  │
│  ┌──────────┐  ┌──────────────┐  ┌──────────┐  ┌────────────┐  │
│  │   Chat   │  │   Pipeline   │  │   Doc    │  │  Project   │  │
│  │  Panel   │  │    Graph     │  │  Viewer  │  │  Explorer  │  │
│  └────┬─────┘  └──────┬───────┘  └────┬─────┘  └─────┬──────┘  │
│       └────────────────┼───────────────┼──────────────┘          │
│                        │ WebSocket + REST                        │
├────────────────────────┼─────────────────────────────────────────┤
│                        │                                         │
│                  ┌─────▼──────┐                                  │
│                  │   API      │                                  │
│                  │  Gateway   │  FastAPI                         │
│                  └─────┬──────┘                                  │
│                        │                                         │
│         ┌──────────────┼──────────────┐                         │
│         │              │              │                          │
│    ┌────▼────┐   ┌─────▼─────┐  ┌────▼────┐                    │
│    │ Project │   │ Pipeline  │  │  Auth   │                     │
│    │ Service │   │  Engine   │  │ Service │                     │
│    └────┬────┘   └─────┬─────┘  └────┬────┘                    │
│         │              │              │                          │
│         │        ┌─────▼──────────────┘                         │
│         │        │                                               │
│         │   ┌────▼─────────────────────────────┐                │
│         │   │        LANGGRAPH ENGINE           │                │
│         │   │                                   │                │
│         │   │  ┌─────────────────────────────┐  │                │
│         │   │  │      ORCHESTRATOR NODE       │  │                │
│         │   │  └──────────┬──────────────────┘  │                │
│         │   │             │                      │                │
│         │   │  ┌──────────▼──────────────────┐  │                │
│         │   │  │     AGENT NODES (19x)       │  │                │
│         │   │  │  ┌─────┐ ┌─────┐ ┌─────┐   │  │                │
│         │   │  │  │Idea │ │Mkt  │ │Comp │   │  │                │
│         │   │  │  │Anlst│ │Rsch │ │Anlst│   │  │                │
│         │   │  │  └─────┘ └─────┘ └─────┘   │  │                │
│         │   │  │  ┌─────┐ ┌─────┐ ┌─────┐   │  │                │
│         │   │  │  │Tech │ │Spec │ │Arch │   │  │                │
│         │   │  │  │Feas │ │Wrtr │ │Desg │   │  │                │
│         │   │  │  └─────┘ └─────┘ └─────┘   │  │                │
│         │   │  │  ┌─────┐ ┌─────┐ ┌─────┐   │  │                │
│         │   │  │  │UX   │ │Qual │ │Devil│   │  │                │
│         │   │  │  │Strt │ │Revw │ │Advoc│   │  │                │
│         │   │  │  └─────┘ └─────┘ └─────┘   │  │                │
│         │   │  │  ┌─────┐ ┌─────┐ ┌─────┐   │  │                │
│         │   │  │  │DocFm│ │Cnsst│ │Plan │   │  │                │
│         │   │  │  │ ttr │ │Chkr │ │Agnt │   │  │                │
│         │   │  │  └─────┘ └─────┘ └─────┘   │  │                │
│         │   │  └─────────────────────────────┘  │                │
│         │   │                                   │                │
│         │   │  ┌─────────────────────────────┐  │                │
│         │   │  │    TOOL REGISTRY             │  │                │
│         │   │  │  web_search, file_write,     │  │                │
│         │   │  │  template_engine, quality_   │  │                │
│         │   │  │  scorer, decision_presenter  │  │                │
│         │   │  └─────────────────────────────┘  │                │
│         │   └───────────────────────────────────┘                │
│         │                                                        │
│    ┌────▼──────────────────────────────────┐                    │
│    │            DATA LAYER                  │                    │
│    │                                        │                    │
│    │  ┌──────────┐  ┌──────────┐  ┌──────┐ │                    │
│    │  │PostgreSQL│  │  Redis   │  │ File │ │                    │
│    │  │(Projects │  │(Sessions │  │System│ │                    │
│    │  │ State,   │  │ Cache,   │  │(Docs)│ │                    │
│    │  │ History) │  │ PubSub)  │  │      │ │                    │
│    │  └──────────┘  └──────────┘  └──────┘ │                    │
│    └────────────────────────────────────────┘                    │
│                        BACKEND                                   │
│                   Python 3.12 + FastAPI                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Tech Stack

### Frontend
| Technology | Purpose | Why |
|-----------|---------|-----|
| **Next.js 15** | Framework | App Router, SSR, API routes, industry standard |
| **TypeScript** | Language | Type safety, better DX |
| **React Flow** | Pipeline graph | Purpose-built for node/edge graph visualization |
| **Monaco Editor** | Document editor | VS Code's editor component, rich markdown support |
| **Shadcn/UI** | Component library | Customizable, accessible, modern design |
| **Tailwind CSS** | Styling | Utility-first, rapid development |
| **Zustand** | State management | Lightweight, simple, works with WebSocket |
| **Socket.io Client** | Real-time | WebSocket client for streaming agent output |

### Backend
| Technology | Purpose | Why |
|-----------|---------|-----|
| **Python 3.12** | Language | LangGraph ecosystem, AI/ML libraries |
| **FastAPI** | API framework | Async, fast, auto-docs, WebSocket support |
| **LangGraph** | Agent orchestration | State machine, checkpointing, streaming, HITL |
| **LiteLLM** | LLM proxy | Unified API for Claude/GPT/Gemini, BYOK support |
| **Socket.io** | Real-time | Server-side WebSocket for streaming |
| **Pydantic** | Data validation | Type-safe models, serialization |
| **Jinja2** | Template engine | Rendering project templates |

### Data & Infrastructure
| Technology | Purpose | Why |
|-----------|---------|-----|
| **PostgreSQL** | Primary database | Projects, users, decision history, agent logs |
| **Redis** | Cache & PubSub | Session state, real-time event streaming |
| **Supabase** | Auth + DB hosting | Free tier, built-in auth, hosted PostgreSQL |
| **Vercel** | Frontend hosting | Next.js native, edge functions, free tier |
| **Railway / Fly.io** | Backend hosting | Python hosting, WebSocket support, affordable |

---

## 3. LangGraph Pipeline Architecture

### 3.1 State Schema

The entire pipeline operates on a shared state object:

```python
from typing import TypedDict, Literal, Optional
from langgraph.graph import MessagesState

class ProjectState(TypedDict):
    # Project identity
    project_id: str
    project_name: str
    project_category: str  # "saas", "fintech", "mobile", "ai_ml", "infrastructure", "multi_platform"
    
    # Pipeline control
    current_phase: Literal["discovery", "specification", "quality", "packaging", "completed"]
    current_agent: str
    pipeline_status: Literal["running", "waiting_for_user", "paused", "completed", "failed"]
    
    # Autonomy settings
    autonomy_level: dict  # {"strategic": "ask", "technical": "delegate", "content": "delegate", "quality": "ask"}
    
    # Discovery phase outputs
    idea_brief: dict          # Structured idea from Idea Analyst
    market_research: dict     # Market Research Agent output
    competitor_analysis: dict # Competitor Agent output
    tech_feasibility: dict    # Tech Feasibility Agent output
    brand_identity: dict      # Brand Strategist output (name, voice, colors)
    legal_requirements: dict  # Legal Advisor output
    research_approved: bool   # User approved research findings
    
    # Specification phase outputs
    prd: str                  # Product Requirements Document (markdown)
    architecture: str         # System Architecture (markdown)
    ux_design: str            # UX/Design spec (markdown)
    user_stories: str         # User stories (markdown)
    wireframe_components: dict # Visual Designer output (filename → React code)
    design_system: dict       # Design System Architect output (tokens, CSS)
    gtm_strategy: str         # GTM Strategist output (markdown)
    financial_model: str      # Financial Modeler output (markdown)
    
    # Quality phase outputs
    quality_score: int        # 0-100
    quality_breakdown: dict   # Per-category scores
    quality_feedback: str     # Reviewer feedback
    devils_advocate: str      # Challenge report
    consistency_report: str   # Consistency check results
    
    # Packaging phase outputs
    project_files: dict       # {filename: content} - all generated files
    implementation_roadmap: str
    
    # Decision tracking
    decisions: list           # [{agent, question, options, user_choice, reasoning, timestamp}]
    pending_decision: dict    # Current decision waiting for user input (or None)
    
    # Chat messages
    messages: list            # Conversation history (LangGraph MessagesState)
    
    # Metadata
    created_at: str
    updated_at: str
    total_llm_calls: int
    total_tokens_used: int
    estimated_cost: float
```

### 3.2 Graph Definition

```python
from langgraph.graph import StateGraph, START, END

graph = StateGraph(ProjectState)

# ── NODES ──────────────────────────────────────────
graph.add_node("orchestrator", orchestrator_node)
graph.add_node("idea_analyst", idea_analyst_node)
# Discovery agents (parallel)
graph.add_node("market_researcher", market_researcher_node)
graph.add_node("competitor_analyst", competitor_analyst_node)
graph.add_node("tech_feasibility", tech_feasibility_node)
graph.add_node("brand_strategist", brand_strategist_node)
graph.add_node("legal_advisor", legal_advisor_node)
graph.add_node("user_checkpoint", user_checkpoint_node)      # HITL
# Specification agents
graph.add_node("spec_writer", spec_writer_node)
graph.add_node("architecture_designer", architecture_designer_node)
graph.add_node("ux_strategist", ux_strategist_node)
graph.add_node("visual_designer", visual_designer_node)
graph.add_node("design_system_architect", design_system_architect_node)
graph.add_node("gtm_strategist", gtm_strategist_node)
graph.add_node("financial_modeler", financial_modeler_node)
# Quality agents
graph.add_node("quality_reviewer", quality_reviewer_node)
graph.add_node("devils_advocate", devils_advocate_node)
graph.add_node("consistency_checker", consistency_checker_node)
# Packaging agents
graph.add_node("doc_formatter", doc_formatter_node)
graph.add_node("planning_agent", planning_agent_node)
graph.add_node("decision_handler", decision_handler_node)     # HITL

# ── EDGES ──────────────────────────────────────────

# Entry
graph.add_edge(START, "orchestrator")

# Orchestrator routes to appropriate phase
graph.add_conditional_edges("orchestrator", route_orchestrator, {
    "intake": "idea_analyst",
    "research": "market_researcher",      # Fan-out starts here
    "specification": "spec_writer",
    "quality": "quality_reviewer",
    "packaging": "doc_formatter",
    "decision": "decision_handler",       # User needs to answer
    "completed": END
})

# Discovery Phase: Idea ↔ Research loop
graph.add_conditional_edges("idea_analyst", after_idea_analysis, {
    "need_user_input": "decision_handler",
    "start_research": "orchestrator",
    "refine_idea": "idea_analyst"
})

# Research agents (parallel via fan-out - 5 agents)
graph.add_edge("market_researcher", "orchestrator")
graph.add_edge("competitor_analyst", "orchestrator")
graph.add_edge("tech_feasibility", "orchestrator")
graph.add_edge("brand_strategist", "orchestrator")
graph.add_edge("legal_advisor", "orchestrator")

# Decision handler (Human-in-the-Loop)
graph.add_conditional_edges("decision_handler", after_decision, {
    "continue": "orchestrator",
    "revise_idea": "idea_analyst",
    "redo_research": "orchestrator",
    "abort": END
})

# Specification Phase (sequential core + parallel extensions)
graph.add_edge("spec_writer", "architecture_designer")
graph.add_edge("architecture_designer", "ux_strategist")
graph.add_edge("ux_strategist", "visual_designer")
graph.add_edge("visual_designer", "design_system_architect")
# GTM and Financial run in parallel with design agents
graph.add_edge("gtm_strategist", "orchestrator")
graph.add_edge("financial_modeler", "orchestrator")
graph.add_edge("design_system_architect", "orchestrator")

# Quality Phase
graph.add_edge("quality_reviewer", "devils_advocate")
graph.add_conditional_edges("devils_advocate", after_quality, {
    "pass": "consistency_checker",
    "fail": "orchestrator",    # Back to spec with feedback
    "need_user": "decision_handler"
})
graph.add_edge("consistency_checker", "orchestrator")

# Packaging Phase
graph.add_edge("doc_formatter", "planning_agent")
graph.add_edge("planning_agent", "orchestrator")  # Final check → END
```

### 3.3 Pipeline State Machine

```
States:
  IDLE → INTAKE → RESEARCHING → RESEARCH_REVIEW → 
  SPECIFYING → QUALITY_CHECK → PACKAGING → COMPLETED

Transitions:
  IDLE → INTAKE:           User submits idea
  INTAKE → RESEARCHING:    Idea brief complete, user confirmed
  INTAKE ↔ RESEARCHING:    Research reveals need to refine idea
  RESEARCHING → RESEARCH_REVIEW: All research agents complete
  RESEARCH_REVIEW → INTAKE: User wants to revise idea
  RESEARCH_REVIEW → SPECIFYING: User approves research
  SPECIFYING → QUALITY_CHECK: All specs written
  QUALITY_CHECK → SPECIFYING: Score < 80, revision needed
  QUALITY_CHECK → PACKAGING: Score >= 80
  PACKAGING → COMPLETED: All files formatted and validated

Special State:
  WAITING_FOR_USER: Any state can transition here when a 
                    decision point requires user input.
                    Resumes to previous state after input.
```

### 3.4 Parallel Execution

Research agents run in parallel using LangGraph's fan-out pattern:

```python
from langgraph.constants import Send

def start_research(state: ProjectState):
    """Fan-out: dispatch 5 research agents simultaneously."""
    return [
        Send("market_researcher", {**state, "current_agent": "market_researcher"}),
        Send("competitor_analyst", {**state, "current_agent": "competitor_analyst"}),
        Send("tech_feasibility", {**state, "current_agent": "tech_feasibility"}),
        Send("brand_strategist", {**state, "current_agent": "brand_strategist"}),
        Send("legal_advisor", {**state, "current_agent": "legal_advisor"}),
    ]
```

### 3.5 Human-in-the-Loop (Decision Points)

Every agent can raise a decision point:

```python
class DecisionPoint:
    id: str
    agent: str                    # Which agent is asking
    category: str                 # "strategic" | "technical" | "content" | "quality"
    question: str                 # Human-readable question
    context: str                  # Why this matters
    options: list[DecisionOption] # Predefined choices (if any)
    agent_recommendation: str     # What the agent would choose
    agent_reasoning: str          # Why the agent recommends this
    allow_delegate: bool          # Can user say "you decide"?
    allow_freeform: bool          # Can user type a custom answer?
    
class DecisionOption:
    id: str
    label: str
    description: str
    pros: list[str]
    cons: list[str]
```

Decision flow:
```
Agent encounters decision point
    ↓
Check autonomy_level[category]
    ↓
If "auto" → agent uses its recommendation, logs decision, continues
If "suggest" → present recommendation, wait for user approval (timeout = auto)
If "ask" → present options, wait for user input (no timeout)
    ↓
User responds (or delegates)
    ↓
Decision recorded in state.decisions[]
Pipeline resumes
```

---

## 4. API Architecture

### 4.1 REST Endpoints

```
POST   /api/projects                    Create new project
GET    /api/projects                    List user's projects
GET    /api/projects/:id                Get project details
DELETE /api/projects/:id                Delete project
POST   /api/projects/:id/start         Start pipeline
POST   /api/projects/:id/pause         Pause pipeline
POST   /api/projects/:id/resume        Resume pipeline
POST   /api/projects/:id/decision      Submit user decision
GET    /api/projects/:id/files          List generated files
GET    /api/projects/:id/files/:name    Get file content
PUT    /api/projects/:id/files/:name    Update file content
GET    /api/projects/:id/decisions      Get decision history
GET    /api/projects/:id/quality        Get quality score
POST   /api/projects/:id/export         Export project as ZIP
POST   /api/settings/api-keys           Save API keys (encrypted)
GET    /api/settings/api-keys           Check which keys are set (no values)
PUT    /api/settings/autonomy           Update autonomy levels
GET    /api/templates                   List available templates
GET    /api/templates/:category         Get template details
```

### 4.2 WebSocket Events

```
Client → Server:
  chat:message          User sends chat message
  decision:submit       User submits a decision
  pipeline:pause        Pause pipeline
  pipeline:resume       Resume pipeline

Server → Client:
  agent:started         Agent began execution {agent_name, phase}
  agent:streaming       Agent streaming output {agent_name, token}
  agent:completed       Agent finished {agent_name, output_summary}
  agent:error           Agent encountered error {agent_name, error}
  decision:required     Decision point reached {decision_point}
  pipeline:phase_change Pipeline moved to new phase {phase}
  pipeline:completed    Pipeline finished {quality_score}
  file:created          New document generated {filename}
  file:updated          Document updated {filename, diff}
  quality:score         Quality score calculated {score, breakdown}
  chat:response         AI chat message {agent_name, content}
  cost:update           Running cost update {tokens, estimated_cost}
```

---

## 5. Security Architecture

### 5.1 API Key Management

```
User enters API key in browser
    ↓
Frontend encrypts key with session-derived key (AES-256-GCM)
    ↓
Encrypted key sent to backend over HTTPS
    ↓
Backend stores encrypted key in session (Redis, TTL=24h)
    ↓
When needed, backend decrypts and uses key for LLM call
    ↓
Key NEVER stored in database, NEVER logged, NEVER in error reports
```

### 5.2 Session Security
- Session tokens via HttpOnly, Secure, SameSite cookies
- CSRF protection on all mutating endpoints
- Rate limiting: 100 req/min per session
- WebSocket authenticated via session token

---

## 6. Deployment Architecture

### MVP Deployment
```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Vercel    │────→│  Railway     │────→│  Supabase   │
│  (Frontend) │     │  (Backend)   │     │ (DB + Auth) │
│  Next.js    │     │  FastAPI     │     │ PostgreSQL  │
│  Free tier  │     │  $5/month    │     │ Free tier   │
└─────────────┘     │  + Redis     │     └─────────────┘
                    └──────────────┘
                    
Total cost: ~$5-15/month
```

### Scale Deployment
```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Vercel    │────→│  Fly.io      │────→│  Supabase   │
│  (Frontend) │     │  (Backend)   │     │  (Pro)      │
│  Pro: $20/m │     │  Workers x3  │     │  $25/month  │
└─────────────┘     │  $30/month   │     └─────────────┘
                    │  + Redis     │
                    └──────────────┘

Total cost: ~$75/month (supports ~500 concurrent users)
```

---

## 7. Data Flow

### Complete Request Flow

```
1. User types "I have a boat marketplace idea" in chat
2. Frontend sends WebSocket message: chat:message
3. Backend receives, creates new project, starts LangGraph
4. LangGraph enters INTAKE state → runs idea_analyst node
5. idea_analyst calls LLM (via LiteLLM with user's API key)
6. LLM streams response tokens
7. Backend streams tokens via WebSocket: agent:streaming
8. Frontend renders tokens in chat panel in real-time
9. idea_analyst produces structured brief
10. idea_analyst raises DecisionPoint: "Confirm this brief?"
11. Backend sends WebSocket: decision:required
12. Frontend renders decision UI with options
13. User clicks "Looks good, continue"
14. Frontend sends: decision:submit
15. Backend records decision, resumes pipeline
16. Orchestrator fans out to 3 research agents (parallel)
17. Each research agent streams findings via WebSocket
18. All 3 complete → orchestrator raises checkpoint decision
19. ... cycle continues through all phases
```
