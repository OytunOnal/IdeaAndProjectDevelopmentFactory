"""Specification-phase agents.

Each agent synthesizes the confirmed brief + research reports into one
specification document. No web search needed — these run on the free
multi-provider LLM chain.
"""

import logging

from app.agents.common import (
    ACTION_CAPABILITY,
    CONSTRUCTIVE_PRINCIPLE,
    DOC_PATHS,
    agent_message,
    apply_discussion_action,
    brief_context,
    current_gate_card,
    current_gate_key,
    docs_context,
    emit_progress,
    extract_adjustments,
    get_doc,
    parse_action,
    prior_adjustments_blocklist,
    reopen_request_shortcut,
    rewrite_request_shortcut,
)
from app.agents.llm import call_llm
from app.agents.state import ProjectState

logger = logging.getLogger(__name__)


SPEC_WRITER_PROMPT = """You are the Product Spec Writer of ProjectFactory. You synthesize the idea brief and research outputs into a comprehensive Product Requirements Document.

Produce a PRD in markdown covering:

1. **Vision & Problem Statement** — grounded in the validated research.
2. **Target Users** — validated personas with priorities.
3. **Feature List (MoSCoW)** — Must/Should/Could/Won't for v1, informed by competitor gaps.
4. **User Stories** — for each MVP feature: "As a [user], I want [action] so that [benefit]" with acceptance criteria (Given/When/Then), priority, and complexity (S/M/L/XL).
5. **MVP Definition** — clear in/out scope boundaries.
6. **Success Metrics & KPIs** — specific, measurable targets.

Incorporate concrete numbers and findings from the research reports. Write clear professional English. Keep it focused — quality over length (max ~1200 words)."""


ARCHITECTURE_PROMPT = """You are the Architecture Designer of ProjectFactory. You design the system architecture based on the PRD and the tech feasibility report.

Produce an architecture document in markdown covering:

1. **System Overview** — high-level architecture with a mermaid diagram, component responsibilities, data flow.
2. **API Design** — key REST endpoints with request/response shapes, auth strategy.
3. **Database Schema** — main entities, relationships, important indexes (as a table or mermaid erDiagram).
4. **Infrastructure** — deployment approach, CI/CD outline, monitoring basics, scaling path.

Design for the stack recommended in the feasibility report. Optimize for MVP speed with a clean foundation for scaling. Max ~1200 words."""


UX_PROMPT = """You are the UX Strategist of ProjectFactory. You define the user experience layer of the project.

Produce a UX specification in markdown covering:

1. **Critical User Flows** — the 2-3 most important journeys (mermaid flowcharts), happy path + key error paths.
2. **Key Screen Specifications** — detailed textual wireframe descriptions (layout, components, content) a developer can implement.
3. **Design System Recommendation** — component library, color/typography direction with rationale, WCAG 2.1 AA notes.
4. **Interaction Patterns** — navigation structure, loading/empty/error states, onboarding flow.

Base decisions on the PRD personas and competitor UX gaps. Max ~1000 words."""


GTM_PROMPT = """You are the GTM Strategist of ProjectFactory. You create the go-to-market strategy.

Produce a GTM document in markdown covering:

1. **Launch Strategy** — pre-launch, launch day, first 3 months.
2. **Acquisition Channels** — top channels with tactics, rough CAC expectations, and priority; grounded in where the target users actually are (per research).
3. **First 1000 Users Plan** — specific, actionable steps with milestones.
4. **Content & Partnership Strategy** — key topics/SEO angles, 2-3 partnership targets.

Be concrete and actionable, not generic. Max ~900 words."""


FINANCIAL_PROMPT = """You are the Financial Modeler of ProjectFactory. You create realistic financial projections and pricing.

Produce a financial model document in markdown covering:

1. **Revenue Model & Pricing** — tiers/commission mechanics, priced against competitors from the research.
2. **12-Month Projection** — quarterly summary table (revenue, costs, net), with stated assumptions (growth, conversion, ARPU, churn).
3. **Unit Economics** — LTV, CAC, LTV/CAC, payback period.
4. **Break-Even Analysis** — fixed/variable costs, break-even user count and timeline.
5. **Funding Assessment** — bootstrap feasibility vs funding need.
6. **Sensitivity** — best/expected/worst case in one table.

Be realistic, not optimistic. Use benchmarks from the research where available. Max ~900 words."""


SPEC_AGENTS = {
    "spec_writer": {
        "prompt": SPEC_WRITER_PROMPT + CONSTRUCTIVE_PRINCIPLE,
        "output_key": "prd",
        "context": ["market_research", "competitor_analysis", "tech_feasibility"],
        "title": "Product Requirements Document",
        "emoji": "📝",
        "tier": 1,
    },
    "architecture_designer": {
        "prompt": ARCHITECTURE_PROMPT + CONSTRUCTIVE_PRINCIPLE,
        "output_key": "architecture",
        "context": ["prd", "tech_feasibility"],
        "title": "System Architecture",
        "emoji": "🏗️",
        "tier": 1,
    },
    "ux_strategist": {
        "prompt": UX_PROMPT + CONSTRUCTIVE_PRINCIPLE,
        "output_key": "ux_design",
        "context": ["prd", "competitor_analysis"],
        "title": "UX Specification",
        "emoji": "🎨",
        "tier": 2,
    },
    "gtm_strategist": {
        "prompt": GTM_PROMPT + CONSTRUCTIVE_PRINCIPLE,
        "output_key": "gtm_strategy",
        "context": ["prd", "market_research", "competitor_analysis"],
        "title": "Go-to-Market Strategy",
        "emoji": "🚀",
        "tier": 2,
    },
    "financial_modeler": {
        "prompt": FINANCIAL_PROMPT + CONSTRUCTIVE_PRINCIPLE,
        "output_key": "financial_model",
        "context": ["prd", "market_research", "gtm_strategy"],
        "title": "Financial Model",
        "emoji": "💰",
        "tier": 2,
    },
}


async def _run_spec_agent(state: ProjectState, agent_id: str) -> ProjectState:
    """Shared runner: write one specification document from brief + context docs."""
    spec = SPEC_AGENTS[agent_id]
    await emit_progress(
        state, agent_id, f"{spec['emoji']} Writing the {spec['title']}..."
    )

    context = brief_context(state)
    docs = docs_context(state, spec["context"])
    user_content = (
        f"{context}\n\n---\n\n{docs}\n\n---\n\n"
        f"Write the {spec['title']} for this project now."
        + prior_adjustments_blocklist(state)
    )

    try:
        document = await call_llm(
            messages=[
                {"role": "system", "content": spec["prompt"]},
                {"role": "user", "content": user_content},
            ],
            model_tier=spec["tier"],
            api_key=state.get("api_key"),
            temperature=0.5,
            max_tokens=6144,
        )
    except Exception as e:
        logger.error(f"{agent_id} failed: {e}", exc_info=True)
        return {
            **state,
            "messages": agent_message(
                state, agent_id,
                f"{spec['emoji']} {spec['title']} failed: {e}. Send any message to retry.",
            ),
            "pipeline_status": "waiting_for_user",
            "current_agent": agent_id,
        }

    path = DOC_PATHS.get(spec["output_key"], "")
    chat_note = (
        f"{spec['emoji']} **{spec['title']} complete** — opened in the files "
        f"panel (`{path}`)."
    )
    adjustments = extract_adjustments(document)
    if adjustments:
        chat_note += f"\n\n**Recommended adjustments:**\n{adjustments}"

    return {
        **state,
        spec["output_key"]: document,
        "messages": agent_message(state, agent_id, chat_note),
        "current_agent": agent_id,
        "pipeline_status": "running",
        "total_llm_calls": state.get("total_llm_calls", 0) + 1,
    }


async def spec_writer_node(state: ProjectState) -> ProjectState:
    return await _run_spec_agent(state, "spec_writer")


async def architecture_designer_node(state: ProjectState) -> ProjectState:
    return await _run_spec_agent(state, "architecture_designer")


async def ux_strategist_node(state: ProjectState) -> ProjectState:
    return await _run_spec_agent(state, "ux_strategist")


async def gtm_strategist_node(state: ProjectState) -> ProjectState:
    return await _run_spec_agent(state, "gtm_strategist")


async def financial_modeler_node(state: ProjectState) -> ProjectState:
    return await _run_spec_agent(state, "financial_modeler")


def _approval_card(question: str, decision_id: str) -> dict:
    return {
        "id": decision_id,
        "agent": "orchestrator",
        "category": "strategic",
        "question": question,
        "options": [
            {
                "id": "confirm",
                "label": "Approve, continue",
                "description": "Proceed to the next phase",
            },
            {
                "id": "revise",
                "label": "Discuss first",
                "description": "Ask questions about the documents",
            },
        ],
        "agent_recommendation": "confirm",
        "agent_reasoning": "All documents for this phase are complete.",
        "allow_delegate": True,
        "allow_freeform": True,
    }


async def spec_review_node(state: ProjectState) -> ProjectState:
    """Summarize the five specification documents and ask for approval."""
    await emit_progress(state, "orchestrator", "🧭 Summarizing the specification documents...")

    doc_keys = ["prd", "architecture", "ux_design", "gtm_strategy", "financial_model"]
    excerpts = docs_context(state, doc_keys, max_chars=1500)

    try:
        summary = await call_llm(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are the Orchestrator of ProjectFactory. Five specification "
                        "documents are complete (you see excerpts). Write a short executive "
                        "summary (max 200 words): what was specified, the recommended stack, "
                        "the pricing direction, and anything the user should double-check."
                    ),
                },
                {"role": "user", "content": excerpts},
            ],
            model_tier=2,
            api_key=state.get("api_key"),
            temperature=0.5,
            max_tokens=1024,
        )
    except Exception as e:
        logger.error(f"Spec review summary failed: {e}")
        summary = "All five specification documents are complete — see above."

    return {
        **state,
        "spec_summary": summary,
        "messages": agent_message(
            state, "orchestrator",
            "🧭 **Specification phase complete** — executive summary opened in "
            f"the files panel (`{DOC_PATHS['spec_summary']}`).",
        ),
        "current_agent": "orchestrator",
        "pipeline_status": "running",
        "spec_review_done": True,
        "pending_decision": _approval_card(
            "Specifications are complete. Proceed to the quality review phase?",
            "approve-spec",
        ),
    }


async def review_discussion_node(state: ProjectState) -> ProjectState:
    """Answer user questions about the produced documents (spec/quality/completed)."""
    # Clear navigation/rewrite requests → handled deterministically,
    # skipping LLM intent parsing
    shortcut = reopen_request_shortcut(state) or rewrite_request_shortcut(state)
    if shortcut:
        return shortcut
    doc_keys = [
        "market_research", "competitor_analysis", "tech_feasibility",
        "prd", "architecture", "ux_design", "gtm_strategy", "financial_model",
        "quality_feedback", "devils_advocate", "consistency_report",
        "implementation_roadmap",
    ]
    grounding = docs_context(state, doc_keys, max_chars=1500)
    gate_key = current_gate_key(state)
    gate_note = (
        f"\n\nDocument currently awaiting the user's approval: {gate_key}"
        if gate_key
        else ""
    )
    system = (
        "You are the Orchestrator of ProjectFactory. Answer the user's questions "
        "concisely, grounded in the project documents below. Be constructive: "
        "when the user raises a concern, propose how the project could adapt "
        "rather than defending the documents."
        + ACTION_CAPABILITY
        + gate_note
        + "\n\n" + grounding
    )

    llm_messages = [{"role": "system", "content": system}]
    for msg in state.get("messages", [])[-8:]:
        role = msg.get("role")
        if role == "agent":
            llm_messages.append({"role": "assistant", "content": msg["content"][:2000]})
        elif role == "user":
            llm_messages.append({"role": "user", "content": msg["content"]})

    try:
        answer = await call_llm(
            messages=llm_messages,
            model_tier=2,
            api_key=state.get("api_key"),
            temperature=0.1,  # intent-bearing call — keep it near-deterministic
            max_tokens=1536,
            role="discussion",  # per-role routing (LOCAL_MIGRATION_PLAN.md)
        )
    except Exception as e:
        logger.error(f"Review discussion failed: {e}")
        answer = f"I couldn't reach the AI model: {e}"

    # The agent may respond with an action instead of an answer
    action = parse_action(answer)
    if action:
        applied = apply_discussion_action(state, action)
        if applied:
            return applied
        answer = (
            "I couldn't map that request to a document action — tell me which "
            "document should change and what the change is."
        )

    # Re-present whichever approval card is currently relevant
    phase = state.get("current_phase")
    pending = current_gate_card(state)
    if pending is None:
        if phase == "specification" and state.get("spec_review_done"):
            pending = _approval_card(
                "Ready to proceed to the quality review phase?", "approve-spec"
            )
        elif phase == "quality" and state.get("quality_review_done"):
            pending = _approval_card(
                "Ready to proceed to the packaging phase?", "approve-quality"
            )

    return {
        **state,
        "messages": agent_message(state, "orchestrator", answer),
        "current_agent": "orchestrator",
        "pipeline_status": "waiting_for_user",
        "pending_decision": pending,
    }


# get_doc re-exported for orchestrator convenience
__all__ = [
    "spec_writer_node", "architecture_designer_node", "ux_strategist_node",
    "gtm_strategist_node", "financial_modeler_node", "spec_review_node",
    "review_discussion_node", "get_doc",
]
