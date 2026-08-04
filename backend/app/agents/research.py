"""Discovery-phase research agents.

Each agent takes the confirmed idea brief, researches its own dimension
(market / competitors / tech), and writes a markdown report into state.

When an Anthropic key is available the agents use Claude's server-side
web_search tool for live, cited data. Without one they fall back to the
generic multi-provider LLM (knowledge-only, clearly flagged in the report).
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
    emit_progress,
    extract_adjustments,
    parse_action,
    prior_adjustments_blocklist,
    reopen_request_shortcut,
    rewrite_request_shortcut,
)
from app.agents.llm import call_anthropic_web_search, call_llm
from app.agents.state import ProjectState
from app.config import settings

logger = logging.getLogger(__name__)

# Model used for web-grounded research. Haiku keeps a full pipeline run cheap;
# bump to claude-sonnet-4-6 for deeper reports.
RESEARCH_MODEL = "claude-haiku-4-5-20251001"
MAX_SEARCHES_PER_AGENT = 5


MARKET_RESEARCHER_PROMPT = """You are the Market Researcher of ProjectFactory. Your job is to validate whether a project idea has a viable market.

Produce a concise market research report in markdown covering:

1. **Market Sizing (TAM/SAM/SOM)** — total, serviceable, and realistically obtainable market. Give numbers with sources; state confidence levels when uncertain.
2. **Market Trends** — growth rate, key drivers, headwinds.
3. **Target Customer Validation** — segments, validated pain points, willingness-to-pay indicators.
4. **Market Timing** — why now, seasonality, regulatory environment.
5. **Verdict** — one paragraph: is this market worth entering? End with a line `VIABILITY: strong | moderate | weak`.

Use web search to find real, current data. Cite sources inline. Keep the whole report under 800 words — dense and specific beats long and generic."""


COMPETITOR_ANALYST_PROMPT = """You are the Competitor Analyst of ProjectFactory. Your job is to map the competitive landscape and identify positioning opportunities.

Produce a concise competitor analysis report in markdown covering:

1. **Direct Competitors** (3-6) — name, what they do, pricing if known, key strength, key weakness.
2. **Indirect Competitors** (2-3) — products solving the same problem differently.
3. **Gap Analysis** — what competitors are NOT doing; where users complain.
4. **Positioning Recommendation** — price positioning, feature positioning, audience positioning.
5. **Differentiation Strategy** — 3 concrete ways to differentiate from the top competitors.

Use web search to find real competitors and recent reviews. Cite sources inline. Keep the report under 800 words."""


TECH_FEASIBILITY_PROMPT = """You are the Tech Feasibility Analyst of ProjectFactory. Your job is to evaluate technology options and recommend the optimal stack.

Produce a concise tech feasibility report in markdown covering:

1. **Requirements Analysis** — functional and non-functional requirements that drive tech decisions.
2. **Technology Alternatives** (2-3 stacks) — components, pros/cons, rough monthly cost, learning curve.
3. **Recommended Stack** — justified choice, assuming a solo developer or small team unless the brief says otherwise.
4. **Technical Risks** — top risks with mitigation; build-vs-buy calls for major components.
5. **MVP Technical Scope** — what is realistically buildable first, and which trade-offs to accept for speed.

Use web search for current pricing and ecosystem maturity where it matters. Keep the report under 800 words."""


_AGENTS = {
    "market_researcher": {
        "prompt": MARKET_RESEARCHER_PROMPT + CONSTRUCTIVE_PRINCIPLE,
        "output_key": "market_research",
        "title": "Market Research",
        "emoji": "📊",
    },
    "competitor_analyst": {
        "prompt": COMPETITOR_ANALYST_PROMPT + CONSTRUCTIVE_PRINCIPLE,
        "output_key": "competitor_analysis",
        "title": "Competitor Analysis",
        "emoji": "🥊",
    },
    "tech_feasibility": {
        "prompt": TECH_FEASIBILITY_PROMPT + CONSTRUCTIVE_PRINCIPLE,
        "output_key": "tech_feasibility",
        "title": "Tech Feasibility",
        "emoji": "🛠️",
    },
}


def _resolve_anthropic_key(state: ProjectState) -> str | None:
    """Prefer the user's own Anthropic key (BYOK), else the server's."""
    user_key = (state.get("api_key") or "").strip()
    if user_key.startswith("sk-ant-"):
        return user_key
    if settings.anthropic_api_key:
        return settings.anthropic_api_key
    return None


async def _run_research_agent(state: ProjectState, agent_id: str) -> ProjectState:
    """Shared runner: research one dimension, store report + chat message."""
    spec = _AGENTS[agent_id]
    await emit_progress(
        state, agent_id,
        f"{spec['emoji']} {spec['title']} in progress — searching the web, this can take a minute...",
    )
    context = brief_context(state)
    user_content = (
        f"{context}\n\nResearch this project idea now and produce your report."
        + prior_adjustments_blocklist(state)
    )

    anthropic_key = _resolve_anthropic_key(state)
    sources: list[str] = []
    web_grounded = False

    try:
        if anthropic_key:
            report, sources = await call_anthropic_web_search(
                system=spec["prompt"],
                user_content=user_content,
                api_key=anthropic_key,
                model=RESEARCH_MODEL,
                max_searches=MAX_SEARCHES_PER_AGENT,
            )
            web_grounded = True
        else:
            # Fallback: no Anthropic key → knowledge-only report via free providers
            report = await call_llm(
                messages=[
                    {"role": "system", "content": spec["prompt"]},
                    {
                        "role": "user",
                        "content": user_content
                        + "\n\nNote: web search is unavailable in this session. "
                        "Base the report on your general knowledge and clearly mark "
                        "figures as estimates.",
                    },
                ],
                model_tier=2,
                api_key=state.get("api_key"),
                temperature=0.5,
                max_tokens=4096,
            )
    except Exception as e:
        logger.error(f"{agent_id} failed: {e}", exc_info=True)
        messages = list(state.get("messages", []))
        messages.append({
            "id": f"msg-error-{len(messages)}",
            "role": "agent",
            "agent_id": agent_id,
            "content": f"{spec['emoji']} {spec['title']} failed: {e}. "
            "You can retry by sending any message.",
            "timestamp": "",
        })
        return {
            **state,
            "messages": messages,
            "pipeline_status": "waiting_for_user",
            "current_agent": agent_id,
        }

    result = {
        "report": report,
        "sources": sources,
        "web_grounded": web_grounded,
        "completed": True,
    }

    source_note = f" ({len(sources)} cited sources)" if sources else ""
    path = DOC_PATHS.get(spec["output_key"], "")
    chat_note = (
        f"{spec['emoji']} **{spec['title']} complete**{source_note} — "
        f"opened in the files panel (`{path}`)."
    )
    adjustments = extract_adjustments(report)
    if adjustments:
        chat_note += f"\n\n**Recommended adjustments:**\n{adjustments}"

    return {
        **state,
        spec["output_key"]: result,
        "messages": agent_message(state, agent_id, chat_note),
        "current_agent": agent_id,
        "pipeline_status": "running",
        "total_llm_calls": state.get("total_llm_calls", 0) + 1,
    }


async def market_researcher_node(state: ProjectState) -> ProjectState:
    return await _run_research_agent(state, "market_researcher")


async def competitor_analyst_node(state: ProjectState) -> ProjectState:
    return await _run_research_agent(state, "competitor_analyst")


async def tech_feasibility_node(state: ProjectState) -> ProjectState:
    return await _run_research_agent(state, "tech_feasibility")


async def research_discussion_node(state: ProjectState) -> ProjectState:
    """Answer user questions about the research before they approve it."""
    # Clear navigation/rewrite requests → handled deterministically,
    # skipping LLM intent parsing
    shortcut = reopen_request_shortcut(state) or rewrite_request_shortcut(state)
    if shortcut:
        return shortcut
    reports = "\n\n---\n\n".join(
        f"## {spec['title']}\n\n{state.get(spec['output_key'], {}).get('report', 'N/A')}"
        for spec in _AGENTS.values()
    )
    gate_key = current_gate_key(state)
    gate_note = (
        f"\n\nDocument currently awaiting the user's approval: {gate_key}"
        if gate_key
        else ""
    )
    system = (
        "You are the Orchestrator of ProjectFactory. The user has questions about "
        "the completed research before approving it. Answer them concisely and "
        "concretely, grounded in the reports below. Be constructive: if the user "
        "is worried about a finding, suggest how the project could adapt (smaller "
        "scope, different segment, different positioning)."
        + ACTION_CAPABILITY
        + gate_note
        + "\n\n" + reports
    )

    llm_messages = [{"role": "system", "content": system}]
    for msg in state.get("messages", [])[-10:]:
        role = msg.get("role")
        if role == "agent":
            llm_messages.append({"role": "assistant", "content": msg["content"]})
        elif role == "user":
            llm_messages.append({"role": "user", "content": msg["content"]})

    try:
        answer = await call_llm(
            messages=llm_messages,
            model_tier=2,
            api_key=state.get("api_key"),
            temperature=0.1,  # intent-bearing call — keep it near-deterministic
            max_tokens=1536,
        )
    except Exception as e:
        logger.error(f"Research discussion failed: {e}")
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
    pending = current_gate_card(state)
    if pending is None and state.get("research_review_done") and not state.get("research_approved"):
        pending = {
            "id": "approve-research",
            "agent": "orchestrator",
            "category": "strategic",
            "question": "Ready to proceed to the specification phase?",
            "options": [
                {
                    "id": "confirm",
                    "label": "Approve research, continue",
                    "description": "Move on to PRD and architecture specification",
                },
                {
                    "id": "revise",
                    "label": "Keep discussing",
                    "description": "Ask more questions about the findings",
                },
            ],
            "agent_recommendation": "confirm",
            "agent_reasoning": "All three research dimensions are covered.",
            "allow_delegate": True,
            "allow_freeform": True,
        }

    return {
        **state,
        "messages": agent_message(state, "orchestrator", answer),
        "current_agent": "orchestrator",
        "pipeline_status": "waiting_for_user",
        "pending_decision": pending,
    }


async def research_review_node(state: ProjectState) -> ProjectState:
    """Synthesize the three research reports and ask the user to approve."""
    await emit_progress(
        state, "orchestrator", "🧭 Synthesizing the three research reports..."
    )
    summary_prompt = (
        "You are the Orchestrator of ProjectFactory. Three research reports are "
        "complete. Write a short executive summary (max 250 words) that combines "
        "them: overall viability, biggest opportunity, biggest risk, and your "
        "recommendation on whether to proceed to the specification phase."
    )
    reports = "\n\n---\n\n".join(
        f"## {spec['title']}\n\n{state.get(spec['output_key'], {}).get('report', 'N/A')}"
        for spec in _AGENTS.values()
    )

    try:
        summary = await call_llm(
            messages=[
                {"role": "system", "content": summary_prompt},
                {"role": "user", "content": reports},
            ],
            model_tier=2,
            api_key=state.get("api_key"),
            temperature=0.5,
            max_tokens=1024,
        )
    except Exception as e:
        logger.error(f"Research review summary failed: {e}")
        summary = "Research phase complete — see the three reports above."

    messages = list(state.get("messages", []))
    messages.append({
        "id": f"msg-agent-{len(messages)}",
        "role": "agent",
        "agent_id": "orchestrator",
        "content": (
            "🧭 **Research phase complete** — executive summary opened in the "
            f"files panel (`{DOC_PATHS['research_summary']}`)."
        ),
        "timestamp": "",
    })

    return {
        **state,
        "research_summary": summary,
        "messages": messages,
        "current_agent": "orchestrator",
        "pipeline_status": "waiting_for_user",
        "research_review_done": True,
        "pending_decision": {
            "id": "approve-research",
            "agent": "orchestrator",
            "category": "strategic",
            "question": "Research is complete. Proceed to the specification phase?",
            "options": [
                {
                    "id": "confirm",
                    "label": "Approve research, continue",
                    "description": "Move on to PRD and architecture specification",
                },
                {
                    "id": "revise",
                    "label": "Discuss the findings first",
                    "description": "Ask questions or request deeper research",
                },
            ],
            "agent_recommendation": "confirm",
            "agent_reasoning": "All three research dimensions are covered.",
            "allow_delegate": True,
            "allow_freeform": True,
        },
    }
