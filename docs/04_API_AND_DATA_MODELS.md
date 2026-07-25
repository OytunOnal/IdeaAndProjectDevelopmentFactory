# ProjectFactory - API & Data Models

> Version: 1.0 | Last Updated: 2026-05-11

---

## 1. Database Schema

### 1.1 Entity Relationship

```
┌──────────┐     ┌──────────────┐     ┌──────────────┐
│  users   │────<│   projects   │────<│  decisions   │
└──────────┘     └──────┬───────┘     └──────────────┘
                        │
                  ┌─────┼──────────┐
                  │     │          │
            ┌─────▼──┐ ┌▼────────┐ ┌▼───────────┐
            │project_│ │pipeline_│ │project_    │
            │files   │ │events   │ │snapshots   │
            └────────┘ └─────────┘ └────────────┘
```

### 1.2 Table Definitions

#### users
```sql
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT UNIQUE,
    display_name    TEXT,
    avatar_url      TEXT,
    auth_provider   TEXT NOT NULL,       -- 'supabase', 'github', 'google'
    
    -- Preferences (stored in DB, not in API key store)
    autonomy_settings JSONB DEFAULT '{
        "strategic": "ask",
        "technical": "suggest",
        "content": "delegate",
        "quality": "ask"
    }',
    default_models  JSONB DEFAULT '{
        "tier1": "claude-opus-4-6",
        "tier2": "claude-sonnet-4-6",
        "tier3": "claude-haiku-4-5-20251001"
    }',
    
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);
```

#### projects
```sql
CREATE TABLE projects (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    
    -- Identity
    name            TEXT NOT NULL,
    slug            TEXT NOT NULL,
    category        TEXT,                -- 'saas', 'fintech', 'mobile', 'ai_ml', 'infrastructure', 'multi_platform'
    description     TEXT,
    
    -- Pipeline state
    current_phase   TEXT DEFAULT 'idle', -- 'idle', 'discovery', 'specification', 'quality', 'packaging', 'completed'
    pipeline_status TEXT DEFAULT 'idle', -- 'idle', 'running', 'waiting_for_user', 'paused', 'completed', 'failed'
    current_agent   TEXT,
    
    -- LangGraph
    langgraph_thread_id TEXT,           -- LangGraph thread ID for checkpointing
    
    -- Agent outputs (JSONB for flexibility)
    idea_brief          JSONB,
    market_research     JSONB,
    competitor_analysis JSONB,
    tech_feasibility    JSONB,
    quality_score       INTEGER,
    quality_breakdown   JSONB,
    quality_feedback    TEXT,
    devils_advocate     TEXT,
    consistency_report  TEXT,
    
    -- Cost tracking
    total_llm_calls     INTEGER DEFAULT 0,
    total_tokens_used   INTEGER DEFAULT 0,
    estimated_cost_usd  DECIMAL(10,4) DEFAULT 0,
    
    -- Timestamps
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    
    UNIQUE(user_id, slug)
);

CREATE INDEX idx_projects_user ON projects(user_id);
CREATE INDEX idx_projects_status ON projects(pipeline_status);
```

#### project_files
```sql
CREATE TABLE project_files (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID REFERENCES projects(id) ON DELETE CASCADE,
    
    file_path       TEXT NOT NULL,       -- '01_STRATEGY/vision.md'
    file_name       TEXT NOT NULL,       -- 'vision.md'
    folder          TEXT NOT NULL,       -- '01_STRATEGY'
    content         TEXT NOT NULL,
    content_hash    TEXT,                -- SHA-256 for change detection
    
    generated_by    TEXT,                -- Agent that created/last modified
    version         INTEGER DEFAULT 1,
    status          TEXT DEFAULT 'draft', -- 'draft', 'reviewed', 'final'
    
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    
    UNIQUE(project_id, file_path)
);

CREATE INDEX idx_files_project ON project_files(project_id);
```

#### decisions
```sql
CREATE TABLE decisions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID REFERENCES projects(id) ON DELETE CASCADE,
    
    -- Decision context
    agent           TEXT NOT NULL,       -- Which agent asked
    category        TEXT NOT NULL,       -- 'strategic', 'technical', 'content', 'quality'
    phase           TEXT NOT NULL,       -- Pipeline phase when decision was made
    
    -- Question and answer
    question        TEXT NOT NULL,
    context         TEXT,                -- Why this matters
    options         JSONB,               -- Available options
    recommendation  TEXT,                -- Agent's recommendation
    reasoning       TEXT,                -- Agent's reasoning
    
    -- Resolution
    resolved_by     TEXT NOT NULL,       -- 'user' or 'agent' (delegated)
    chosen_option   TEXT,                -- Selected option ID or custom text
    user_input      TEXT,                -- Free-form user input if any
    
    created_at      TIMESTAMPTZ DEFAULT now(),
    resolved_at     TIMESTAMPTZ
);

CREATE INDEX idx_decisions_project ON decisions(project_id);
```

#### pipeline_events
```sql
CREATE TABLE pipeline_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID REFERENCES projects(id) ON DELETE CASCADE,
    
    event_type      TEXT NOT NULL,       -- 'agent_started', 'agent_completed', 'phase_change', etc.
    agent           TEXT,
    phase           TEXT,
    data            JSONB,               -- Event-specific data
    
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_events_project ON pipeline_events(project_id);
CREATE INDEX idx_events_type ON pipeline_events(event_type);
```

#### project_snapshots
```sql
CREATE TABLE project_snapshots (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID REFERENCES projects(id) ON DELETE CASCADE,
    
    phase           TEXT NOT NULL,        -- Phase when snapshot was taken
    state_snapshot  JSONB NOT NULL,       -- Full pipeline state
    
    created_at      TIMESTAMPTZ DEFAULT now()
);
```

---

## 2. REST API Specification

### 2.1 Authentication

All endpoints require authentication via Supabase Auth JWT token:
```
Authorization: Bearer <supabase_jwt_token>
```

### 2.2 Endpoints

#### Projects

```
POST /api/projects
```
Create a new project.
```json
// Request
{
    "name": "Boat Marketplace",
    "description": "A marketplace for boats and marine equipment in Turkey"
}

// Response 201
{
    "id": "uuid",
    "name": "Boat Marketplace",
    "slug": "boat-marketplace",
    "current_phase": "idle",
    "pipeline_status": "idle",
    "created_at": "2026-05-11T10:00:00Z"
}
```

---

```
GET /api/projects
```
List user's projects.
```json
// Response 200
{
    "projects": [
        {
            "id": "uuid",
            "name": "Boat Marketplace",
            "category": "saas",
            "current_phase": "discovery",
            "pipeline_status": "running",
            "quality_score": null,
            "created_at": "2026-05-11T10:00:00Z"
        }
    ]
}
```

---

```
GET /api/projects/:id
```
Get full project details including agent outputs.
```json
// Response 200
{
    "id": "uuid",
    "name": "Boat Marketplace",
    "category": "saas",
    "current_phase": "specification",
    "pipeline_status": "waiting_for_user",
    "idea_brief": { ... },
    "market_research": { ... },
    "competitor_analysis": { ... },
    "tech_feasibility": { ... },
    "quality_score": null,
    "pending_decision": {
        "id": "decision-uuid",
        "agent": "spec_writer",
        "question": "Which features should be in MVP?",
        "options": [ ... ],
        "recommendation": "..."
    },
    "total_tokens_used": 45000,
    "estimated_cost_usd": 1.23
}
```

---

```
POST /api/projects/:id/start
```
Start the pipeline for a project.
```json
// Request
{
    "initial_message": "I want to build a boat marketplace for Turkey"
}

// Response 200
{
    "status": "running",
    "current_phase": "discovery",
    "current_agent": "idea_analyst"
}
```

---

```
POST /api/projects/:id/decision
```
Submit a user decision.
```json
// Request
{
    "decision_id": "decision-uuid",
    "action": "choose",          // "choose" | "delegate" | "custom" | "more_info"
    "chosen_option": "option_a", // if action is "choose"
    "custom_input": ""           // if action is "custom"
}

// Response 200
{
    "status": "running",
    "message": "Decision recorded. Pipeline resuming."
}
```

---

```
POST /api/projects/:id/chat
```
Send a chat message (when pipeline is running or paused).
```json
// Request
{
    "message": "I think we should focus on B2B instead"
}

// Response 200
{
    "received": true,
    "pipeline_action": "idea_revision_triggered"
}
```

---

```
POST /api/projects/:id/pause
POST /api/projects/:id/resume
```
Pause or resume pipeline execution.

---

```
GET /api/projects/:id/files
```
List generated project files.
```json
// Response 200
{
    "files": [
        {
            "file_path": "INDEX.md",
            "folder": "root",
            "status": "final",
            "generated_by": "doc_formatter",
            "updated_at": "2026-05-11T10:30:00Z"
        },
        {
            "file_path": "01_STRATEGY/vision.md",
            "folder": "01_STRATEGY",
            "status": "draft",
            "generated_by": "spec_writer",
            "updated_at": "2026-05-11T10:25:00Z"
        }
    ]
}
```

---

```
GET /api/projects/:id/files/:path
```
Get file content.
```json
// Response 200
{
    "file_path": "01_STRATEGY/vision.md",
    "content": "# Vision\n\n...",
    "generated_by": "spec_writer",
    "version": 2,
    "status": "reviewed"
}
```

---

```
PUT /api/projects/:id/files/:path
```
User edits a file directly.
```json
// Request
{
    "content": "# Vision\n\nUpdated content..."
}

// Response 200
{
    "version": 3,
    "status": "draft",
    "updated_at": "2026-05-11T10:35:00Z"
}
```

---

```
POST /api/projects/:id/export
```
Export project as downloadable ZIP.
```json
// Response 200
{
    "download_url": "/api/projects/:id/export/download?token=temp_token",
    "expires_at": "2026-05-11T11:00:00Z",
    "file_count": 16,
    "total_size_kb": 245
}
```

---

#### Settings

```
POST /api/settings/api-keys
```
Save API keys (encrypted).
```json
// Request
{
    "provider": "anthropic",     // "anthropic" | "openai" | "google"
    "api_key": "sk-ant-..."
}

// Response 200
{
    "provider": "anthropic",
    "status": "valid",           // Key is validated on save
    "models_available": ["claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"]
}
```

---

```
GET /api/settings/api-keys
```
Check which keys are configured (never returns actual keys).
```json
// Response 200
{
    "keys": [
        {"provider": "anthropic", "configured": true, "last_validated": "2026-05-11T09:00:00Z"},
        {"provider": "openai", "configured": false},
        {"provider": "google", "configured": false}
    ]
}
```

---

```
PUT /api/settings/autonomy
```
Update autonomy preferences.
```json
// Request
{
    "strategic": "ask",
    "technical": "suggest",
    "content": "delegate",
    "quality": "ask"
}
```

---

## 3. WebSocket Protocol

### 3.1 Connection

```
ws://api.projectfactory.dev/ws?token=<jwt_token>&project_id=<uuid>
```

### 3.2 Message Format

All WebSocket messages follow this envelope:

```json
{
    "type": "event_type",
    "timestamp": "2026-05-11T10:00:00Z",
    "data": { ... }
}
```

### 3.3 Server → Client Events

#### agent:started
```json
{
    "type": "agent:started",
    "data": {
        "agent": "market_researcher",
        "phase": "discovery",
        "description": "Researching market size and trends"
    }
}
```

#### agent:streaming
```json
{
    "type": "agent:streaming",
    "data": {
        "agent": "market_researcher",
        "token": "The Turkish marine",
        "message_id": "msg-uuid"
    }
}
```

#### agent:completed
```json
{
    "type": "agent:completed",
    "data": {
        "agent": "market_researcher",
        "duration_ms": 45000,
        "tokens_used": 3200,
        "summary": "Market research complete. TAM: $1.2B, 12% annual growth."
    }
}
```

#### decision:required
```json
{
    "type": "decision:required",
    "data": {
        "decision_id": "decision-uuid",
        "agent": "tech_feasibility",
        "category": "technical",
        "question": "Which tech stack should we use?",
        "context": "Based on your requirements for a marketplace with real-time features...",
        "options": [
            {
                "id": "a",
                "label": "Next.js + Supabase",
                "description": "Fast MVP, lower cost, great DX",
                "pros": ["Rapid development", "Built-in auth", "Free tier"],
                "cons": ["Scaling limits", "Vendor lock-in"]
            },
            {
                "id": "b",
                "label": "Django + PostgreSQL",
                "description": "Battle-tested, more control",
                "pros": ["Mature ecosystem", "Full control", "No vendor lock-in"],
                "cons": ["Slower development", "More boilerplate"]
            }
        ],
        "agent_recommendation": "a",
        "agent_reasoning": "For a solo developer building an MVP, Next.js + Supabase offers the fastest path to market with lowest cost.",
        "allow_delegate": true,
        "allow_freeform": true
    }
}
```

#### pipeline:phase_change
```json
{
    "type": "pipeline:phase_change",
    "data": {
        "from_phase": "discovery",
        "to_phase": "specification",
        "summary": "Discovery phase complete. 3 research reports generated. User approved findings."
    }
}
```

#### file:created
```json
{
    "type": "file:created",
    "data": {
        "file_path": "02_PRODUCT/prd.md",
        "generated_by": "spec_writer",
        "size_bytes": 12400
    }
}
```

#### cost:update
```json
{
    "type": "cost:update",
    "data": {
        "total_tokens": 78000,
        "estimated_cost_usd": 2.34,
        "breakdown": {
            "orchestrator": 0.45,
            "idea_analyst": 0.12,
            "market_researcher": 0.67,
            "competitor_analyst": 0.55,
            "tech_feasibility": 0.55
        }
    }
}
```

### 3.4 Client → Server Events

#### chat:message
```json
{
    "type": "chat:message",
    "data": {
        "message": "I think we should target B2B instead of B2C"
    }
}
```

#### decision:submit
```json
{
    "type": "decision:submit",
    "data": {
        "decision_id": "decision-uuid",
        "action": "choose",
        "chosen_option": "a"
    }
}
```

---

## 4. LangGraph State Types (Python)

```python
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum

class Phase(str, Enum):
    IDLE = "idle"
    DISCOVERY = "discovery"
    SPECIFICATION = "specification"
    QUALITY = "quality"
    PACKAGING = "packaging"
    COMPLETED = "completed"

class PipelineStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    WAITING_FOR_USER = "waiting_for_user"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"

class AutonomyLevel(str, Enum):
    ASK = "ask"           # Always ask user
    SUGGEST = "suggest"   # Show recommendation, wait for approval
    DELEGATE = "delegate" # Agent decides, user can review later

class DecisionCategory(str, Enum):
    STRATEGIC = "strategic"
    TECHNICAL = "technical"
    CONTENT = "content"
    QUALITY = "quality"

class AutonomySettings(BaseModel):
    strategic: AutonomyLevel = AutonomyLevel.ASK
    technical: AutonomyLevel = AutonomyLevel.SUGGEST
    content: AutonomyLevel = AutonomyLevel.DELEGATE
    quality: AutonomyLevel = AutonomyLevel.ASK

class DecisionOption(BaseModel):
    id: str
    label: str
    description: str
    pros: list[str] = []
    cons: list[str] = []

class DecisionPoint(BaseModel):
    id: str
    agent: str
    category: DecisionCategory
    question: str
    context: str = ""
    options: list[DecisionOption] = []
    agent_recommendation: Optional[str] = None
    agent_reasoning: Optional[str] = None
    allow_delegate: bool = True
    allow_freeform: bool = True

class DecisionRecord(BaseModel):
    id: str
    agent: str
    category: DecisionCategory
    phase: Phase
    question: str
    options: list[DecisionOption]
    recommendation: Optional[str]
    reasoning: Optional[str]
    resolved_by: str              # "user" or "agent"
    chosen_option: Optional[str]
    user_input: Optional[str]
    created_at: str
    resolved_at: Optional[str]

class IdeaBrief(BaseModel):
    problem_statement: str
    target_users: list[dict]      # [{type, description, priority}]
    value_proposition: str
    core_features: list[str]
    revenue_model: str
    domain_category: str
    initial_scope_in: list[str]
    initial_scope_out: list[str]
    additional_context: str = ""

class QualityBreakdown(BaseModel):
    strategy: int                 # max 25
    product: int                  # max 30
    design: int                   # max 20
    technical: int                # max 25
    total: int                    # max 100
    grade: str                    # A+, A, B, C, D, F
    gaps: list[dict]              # [{section, severity, description, fix}]
```

---

## 5. Cost Estimation Model

Token cost calculation per provider:

```python
COST_PER_1K_TOKENS = {
    "claude-opus-4-6":          {"input": 0.015, "output": 0.075},
    "claude-sonnet-4-6":        {"input": 0.003, "output": 0.015},
    "claude-haiku-4-5-20251001":{"input": 0.0008, "output": 0.004},
    "gpt-4o":                   {"input": 0.0025, "output": 0.01},
    "gpt-4o-mini":              {"input": 0.00015, "output": 0.0006},
    "gemini-2.0-flash":         {"input": 0.0001, "output": 0.0004},
}

# Estimated tokens per agent (average project)
AGENT_TOKEN_ESTIMATES = {
    # Orchestrator (Tier 1)
    "orchestrator":            {"calls": 10, "tokens_per_call": 2000},
    # Discovery (Tier 2)
    "idea_analyst":            {"calls": 3,  "tokens_per_call": 3000},
    "market_researcher":       {"calls": 2,  "tokens_per_call": 5000},
    "competitor_analyst":      {"calls": 2,  "tokens_per_call": 5000},
    "tech_feasibility":        {"calls": 2,  "tokens_per_call": 4000},
    "brand_strategist":        {"calls": 2,  "tokens_per_call": 4000},
    "legal_advisor":           {"calls": 2,  "tokens_per_call": 4000},
    # Specification (Tier 1 + 2)
    "spec_writer":             {"calls": 3,  "tokens_per_call": 8000},
    "architecture_designer":   {"calls": 2,  "tokens_per_call": 6000},
    "ux_strategist":           {"calls": 2,  "tokens_per_call": 5000},
    "visual_designer":         {"calls": 4,  "tokens_per_call": 6000},
    "design_system_architect": {"calls": 2,  "tokens_per_call": 3000},
    "gtm_strategist":          {"calls": 2,  "tokens_per_call": 5000},
    "financial_modeler":       {"calls": 2,  "tokens_per_call": 5000},
    # Quality (Tier 1 + 2)
    "quality_reviewer":        {"calls": 2,  "tokens_per_call": 5000},
    "devils_advocate":         {"calls": 1,  "tokens_per_call": 4000},
    "consistency_checker":     {"calls": 1,  "tokens_per_call": 3000},
    # Packaging (Tier 2 + 3)
    "doc_formatter":           {"calls": 6,  "tokens_per_call": 3000},
    "planning_agent":          {"calls": 2,  "tokens_per_call": 5000},
}

# Estimated total cost per project (Claude models):
# Tier 1 agents (Opus):    ~$4-7
# Tier 2 agents (Sonnet):  ~$2-4
# Tier 3 agents (Haiku):   ~$0.10-0.30
# TOTAL ESTIMATE:          ~$6-12 per complete project
```
