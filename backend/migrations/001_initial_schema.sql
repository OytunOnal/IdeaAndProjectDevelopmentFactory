-- ProjectFactory Initial Schema
-- Run this in your Supabase SQL Editor

CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT UNIQUE,
    display_name    TEXT,
    avatar_url      TEXT,
    auth_provider   TEXT NOT NULL DEFAULT 'supabase',
    autonomy_settings JSONB DEFAULT '{"strategic": "ask", "technical": "suggest", "content": "delegate", "quality": "ask"}',
    default_models  JSONB DEFAULT '{"tier1": "claude-opus-4-6", "tier2": "claude-sonnet-4-6", "tier3": "claude-haiku-4-5-20251001"}',
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS projects (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    slug            TEXT NOT NULL,
    category        TEXT,
    description     TEXT,
    current_phase   TEXT DEFAULT 'idle',
    pipeline_status TEXT DEFAULT 'idle',
    current_agent   TEXT,
    langgraph_thread_id TEXT,
    idea_brief          JSONB,
    market_research     JSONB,
    competitor_analysis JSONB,
    tech_feasibility    JSONB,
    brand_identity      JSONB,
    legal_requirements  JSONB,
    quality_score       INTEGER,
    quality_breakdown   JSONB,
    quality_feedback    TEXT,
    devils_advocate     TEXT,
    consistency_report  TEXT,
    total_llm_calls     INTEGER DEFAULT 0,
    total_tokens_used   INTEGER DEFAULT 0,
    estimated_cost_usd  DECIMAL(10,4) DEFAULT 0,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, slug)
);

CREATE INDEX IF NOT EXISTS idx_projects_user ON projects(user_id);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(pipeline_status);

CREATE TABLE IF NOT EXISTS project_files (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID REFERENCES projects(id) ON DELETE CASCADE,
    file_path       TEXT NOT NULL,
    file_name       TEXT NOT NULL,
    folder          TEXT NOT NULL,
    content         TEXT NOT NULL,
    content_hash    TEXT,
    generated_by    TEXT,
    version         INTEGER DEFAULT 1,
    status          TEXT DEFAULT 'draft',
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(project_id, file_path)
);

CREATE INDEX IF NOT EXISTS idx_files_project ON project_files(project_id);

CREATE TABLE IF NOT EXISTS decisions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID REFERENCES projects(id) ON DELETE CASCADE,
    agent           TEXT NOT NULL,
    category        TEXT NOT NULL,
    phase           TEXT NOT NULL,
    question        TEXT NOT NULL,
    context         TEXT,
    options         JSONB,
    recommendation  TEXT,
    reasoning       TEXT,
    resolved_by     TEXT NOT NULL,
    chosen_option   TEXT,
    user_input      TEXT,
    created_at      TIMESTAMPTZ DEFAULT now(),
    resolved_at     TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_decisions_project ON decisions(project_id);

CREATE TABLE IF NOT EXISTS pipeline_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID REFERENCES projects(id) ON DELETE CASCADE,
    event_type      TEXT NOT NULL,
    agent           TEXT,
    phase           TEXT,
    data            JSONB,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_events_project ON pipeline_events(project_id);
