"""Quality-phase agents: score, stress-test, and cross-check the specs."""

import json
import logging

from app.agents.common import agent_message, docs_context, emit_progress
from app.agents.llm import call_llm
from app.agents.state import ProjectState

logger = logging.getLogger(__name__)

# Kept compact: free-tier providers reject oversized payloads (Groq 413s
# above ~6k tokens/request), so quality agents see the five spec docs plus
# market research, truncated.
ALL_SPEC_DOCS = [
    "prd", "architecture", "ux_design", "gtm_strategy", "financial_model",
    "market_research",
]


QUALITY_REVIEWER_PROMPT = """You are the Quality Reviewer of ProjectFactory — the independent gatekeeper. Your job is to find problems, not to approve. You did NOT write these documents.

Score the project specifications against this rubric (100 points):

1. **Strategy (20)** — vision clarity (5), market validation with real data (8), competitor analysis depth (7)
2. **Product (30)** — PRD completeness (10), user stories with acceptance criteria (10), MVP scope realism (10)
3. **Design & GTM (20)** — user flows and screens (10), GTM actionability (5), financial realism (5)
4. **Technical (30)** — architecture soundness (12), database/API design (10), risk mitigation (8)

Output in markdown:
- Score per category with 1-2 sentence justification
- Specific gaps with severity (critical/major/minor) and a concrete fix for each
- Verdict paragraph

End your response with exactly this fenced JSON block:

```json
{"total": <int>, "breakdown": {"strategy": <int>, "product": <int>, "design_gtm": <int>, "technical": <int>}, "grade": "<A|B|C|D|F>", "verdict": "<PASS|FAIL>"}
```

Grades: A 90+, B 80-89, C 70-79, D 60-69, F below 60. PASS requires >= 80. Be critical and honest — an inflated score helps no one."""


DEVILS_ADVOCATE_PROMPT = """You are the Devil's Advocate of ProjectFactory. Argue AGAINST this project to expose weaknesses — not to kill it, but to make it stronger.

Challenge, in markdown:

1. **Market Assumptions** — is the market really that big? What could shrink it?
2. **Competitive Threats** — what if an incumbent copies the differentiator? Is the moat real?
3. **Technical Risks** — hardest challenge, single points of failure.
4. **Business Model Risks** — will users actually pay? What evidence exists?
5. **Unvalidated Assumptions** — list every untested assumption, ranked by impact.

End with: recommended actions for the top 3 risks, and an overall risk rating line `RISK: LOW | MEDIUM | HIGH | CRITICAL`. Max ~700 words, specific counter-arguments only — no generic caution."""


CONSISTENCY_PROMPT = """You are the Consistency Checker of ProjectFactory. Validate that the project documents are internally consistent.

Check and report in markdown:

1. **Feature consistency** — every MVP feature in the PRD has user stories and architecture support; no orphan features.
2. **Terminology** — same concepts named the same way across documents.
3. **Numbers** — market sizes, prices, timelines, and costs don't contradict between documents.
4. **Scope** — MVP scope is identical in PRD, architecture, and financial assumptions.

Output: a table of inconsistencies (location, severity critical/major/minor, suggested fix). If a category is clean, say so in one line. Max ~500 words."""


async def quality_reviewer_node(state: ProjectState) -> ProjectState:
    await emit_progress(state, "quality_reviewer", "🔍 Scoring the specifications against the quality rubric...")
    docs = docs_context(state, ALL_SPEC_DOCS, max_chars=3000)

    try:
        response = await call_llm(
            messages=[
                {"role": "system", "content": QUALITY_REVIEWER_PROMPT},
                {"role": "user", "content": docs + "\n\nReview and score this project now."},
            ],
            model_tier=1,
            api_key=state.get("api_key"),
            temperature=0.3,
            max_tokens=4096,
        )
    except Exception as e:
        logger.error(f"quality_reviewer failed: {e}", exc_info=True)
        return {
            **state,
            "messages": agent_message(
                state, "quality_reviewer",
                f"🔍 Quality review failed: {e}. Send any message to retry.",
            ),
            "pipeline_status": "waiting_for_user",
            "current_agent": "quality_reviewer",
        }

    score, breakdown = _extract_score(response)
    feedback = _strip_json_block(response)

    return {
        **state,
        "quality_score": score,
        "quality_breakdown": breakdown or {},
        "quality_feedback": feedback,
        "messages": agent_message(
            state, "quality_reviewer",
            f"🔍 **Quality Review complete** — score: **{score if score is not None else 'n/a'}/100**\n\n{feedback}",
        ),
        "current_agent": "quality_reviewer",
        "pipeline_status": "running",
        "total_llm_calls": state.get("total_llm_calls", 0) + 1,
    }


async def devils_advocate_node(state: ProjectState) -> ProjectState:
    return await _run_report_agent(
        state, "devils_advocate", DEVILS_ADVOCATE_PROMPT,
        "devils_advocate", "Devil's Advocate Report", "😈",
    )


async def consistency_checker_node(state: ProjectState) -> ProjectState:
    return await _run_report_agent(
        state, "consistency_checker", CONSISTENCY_PROMPT,
        "consistency_report", "Consistency Report", "🧩",
    )


async def _run_report_agent(
    state: ProjectState, agent_id: str, prompt: str,
    output_key: str, title: str, emoji: str,
) -> ProjectState:
    await emit_progress(state, agent_id, f"{emoji} Writing the {title}...")
    docs = docs_context(state, ALL_SPEC_DOCS, max_chars=2500)

    try:
        report = await call_llm(
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": docs + f"\n\nWrite the {title} now."},
            ],
            model_tier=2,
            api_key=state.get("api_key"),
            temperature=0.4,
            max_tokens=3072,
        )
    except Exception as e:
        logger.error(f"{agent_id} failed: {e}", exc_info=True)
        return {
            **state,
            "messages": agent_message(
                state, agent_id, f"{emoji} {title} failed: {e}. Send any message to retry.",
            ),
            "pipeline_status": "waiting_for_user",
            "current_agent": agent_id,
        }

    return {
        **state,
        output_key: report,
        "messages": agent_message(state, agent_id, f"{emoji} **{title}**\n\n{report}"),
        "current_agent": agent_id,
        "pipeline_status": "running",
        "total_llm_calls": state.get("total_llm_calls", 0) + 1,
    }


async def quality_review_node(state: ProjectState) -> ProjectState:
    """Present the quality verdict and ask to proceed to packaging."""
    score = state.get("quality_score")
    score_text = f"{score}/100" if score is not None else "n/a"

    return {
        **state,
        "messages": agent_message(
            state, "orchestrator",
            f"🧭 Quality phase complete. Overall score: **{score_text}**. "
            "The Devil's Advocate and Consistency reports are above — review them "
            "before packaging.",
        ),
        "current_agent": "orchestrator",
        "pipeline_status": "running",
        "quality_review_done": True,
        "pending_decision": {
            "id": "approve-quality",
            "agent": "orchestrator",
            "category": "quality",
            "question": f"Quality review is done (score: {score_text}). Package the final documents?",
            "options": [
                {
                    "id": "confirm",
                    "label": "Package the project",
                    "description": "Generate the final document set and roadmap",
                },
                {
                    "id": "revise",
                    "label": "Discuss the findings first",
                    "description": "Ask about the quality gaps or risks",
                },
            ],
            "agent_recommendation": "confirm",
            "agent_reasoning": "All quality checks have run; gaps are documented.",
            "allow_delegate": True,
            "allow_freeform": True,
        },
    }


def _extract_score(text: str) -> tuple[int | None, dict | None]:
    """Parse the trailing fenced JSON score block from the reviewer's output."""
    try:
        if "```json" in text:
            start = text.rindex("```json") + 7
            end = text.index("```", start)
            data = json.loads(text[start:end].strip())
            total = data.get("total")
            if isinstance(total, int):
                return total, {
                    **data.get("breakdown", {}),
                    "grade": data.get("grade"),
                    "verdict": data.get("verdict"),
                }
    except (ValueError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to parse quality score JSON: {e}")
    return None, None


def _strip_json_block(text: str) -> str:
    """Remove the trailing fenced JSON block from the displayed feedback."""
    if "```json" not in text:
        return text.strip()
    start = text.rindex("```json")
    end = text.find("```", start + 7)
    if end == -1:
        return text[:start].strip()
    return (text[:start] + text[end + 3:]).strip()
