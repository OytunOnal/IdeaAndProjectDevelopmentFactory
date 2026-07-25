from typing import TypedDict


class ProjectState(TypedDict, total=False):
    # Project identity
    project_id: str
    project_name: str
    project_category: str

    # Pipeline control
    current_phase: str
    current_agent: str
    pipeline_status: str

    # BYOK - user's LLM API key for this session
    api_key: str

    # Autonomy settings
    autonomy_level: dict

    # Discovery phase outputs
    idea_brief: dict
    market_research: dict
    competitor_analysis: dict
    tech_feasibility: dict
    brand_identity: dict
    legal_requirements: dict
    research_review_done: bool
    research_approved: bool

    # Specification phase outputs
    prd: str
    architecture: str
    ux_design: str
    user_stories: str
    wireframe_components: dict
    design_system: dict
    gtm_strategy: str
    financial_model: str
    spec_review_done: bool

    # Quality phase outputs
    quality_score: int
    quality_breakdown: dict
    quality_feedback: str
    devils_advocate: str
    consistency_report: str
    quality_review_done: bool

    # Packaging phase outputs
    project_files: dict
    implementation_roadmap: str

    # Decision tracking
    decisions: list
    pending_decision: dict | None

    # Chat messages
    messages: list

    # Metadata
    created_at: str
    updated_at: str
    total_llm_calls: int
    total_tokens_used: int
    estimated_cost: float
