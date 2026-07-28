"""Quality-phase agents: score, stress-test, and cross-check the specs."""

import json
import logging

from app.agents.common import (
    DOC_PATHS,
    agent_message,
    docs_context,
    emit_progress,
)
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


# Version of the scoring rubric below. Bump whenever the rubric lines or
# weights change — every stored score is stamped with this, so past scores
# stay attributable to the rubric that produced them instead of being
# silently re-interpreted after an edit.
RUBRIC_VERSION = "2026-07-28.1"

QUALITY_REVIEWER_PROMPT = """You are the Quality Reviewer of ProjectFactory — the independent gatekeeper. Your job is to find problems, not to approve. You did NOT write these documents.

You are also given the Devil's Advocate and Consistency reports — risks left unmitigated and inconsistencies left unfixed MUST be reflected in your scores.

Score the project specifications against this rubric (100 points):

1. **Strategy (20)** — vision clarity (5), market validation with real data (8), competitor analysis depth (7)
2. **Product (30)** — PRD completeness (10), user stories with acceptance criteria (10), MVP scope realism (10)
3. **Design & GTM (20)** — user flows and screens (10), GTM actionability (5), financial realism (5)
4. **Technical (30)** — architecture soundness (12), database/API design (10), risk mitigation (8)

Output in markdown:
- Score per category. For EACH category you must make the score auditable:
  quote the exact rubric line you are applying, then cite the evidence — the
  document key plus the shortest quoted span (max ~25 words) that earned or
  lost the points. Format:
  `- rubric: "<rubric line>" | evidence: <doc_key>: "<quoted span>" | <points awarded> — <one-line reason>`
  A deduction without a cited span does not count; if you cannot point to a
  span, do not deduct for it.
- Specific gaps with severity (critical/major/minor) and a concrete fix for each
- Verdict paragraph

End your response with exactly this fenced JSON block:

```json
{"total": <int>, "breakdown": {"strategy": <int>, "product": <int>, "design_gtm": <int>, "technical": <int>}, "grade": "<A|B|C|D|F>", "verdict": "<PASS|FAIL>", "top_fixes": ["<doc_key>: <fix>", ...]}
```

top_fixes: the 3-5 highest-impact concrete fixes ordered by impact. Each MUST start with the target document key and a colon — one of prd, architecture, ux_design, gtm_strategy, financial_model. Example: "prd: Add acceptance criteria to the five MVP user stories".

Grades: A 90+, B 80-89, C 70-79, D 60-69, F below 60. PASS requires >= 80. Be critical and honest — an inflated score helps no one."""


DEVILS_ADVOCATE_PROMPT = """You are the Devil's Advocate of ProjectFactory. Argue AGAINST this project to expose weaknesses — not to kill it, but to make it stronger.

Challenge, in markdown:

1. **Market Assumptions** — is the market really that big? What could shrink it?
2. **Competitive Threats** — what if an incumbent copies the differentiator? Is the moat real?
3. **Technical Risks** — hardest challenge, single points of failure.
4. **Business Model Risks** — will users actually pay? What evidence exists?
5. **Unvalidated Assumptions** — list every untested assumption, ranked by impact.

Every risk you raise MUST come with at least one concrete mitigation or pivot — never leave the user with "this won't work" and no path forward.

End with an overall risk rating line `RISK: LOW | MEDIUM | HIGH | CRITICAL`, then finish with exactly this heading:

## Recommended Adjustments

Up to 3 NUMBERED project-level changes that would defuse the biggest risks — the user can apply these to the specs with one click, so make them concrete and self-contained. High bar, no filler. If the risks are already adequately mitigated, write exactly: None — the current direction holds up.

Max ~700 words, specific counter-arguments only — no generic caution."""


CONSISTENCY_PROMPT = """You are the Consistency Checker of ProjectFactory. Validate that the project documents are internally consistent.

Check and report in markdown:

1. **Feature consistency** — every MVP feature in the PRD has user stories and architecture support; no orphan features.
2. **Terminology** — same concepts named the same way across documents.
3. **Numbers** — market sizes, prices, timelines, and costs don't contradict between documents.
4. **Scope** — MVP scope is identical in PRD, architecture, and financial assumptions.

Output: a table of inconsistencies (location, severity critical/major/minor, suggested fix). If a category is clean, say so in one line. Max ~500 words.

Finish with exactly this heading:

## Recommended Adjustments

Up to 3 NUMBERED cross-document alignment fixes worth applying to the specs (the user can apply them with one click). If the documents are consistent, write exactly: None — the documents are consistent."""


async def quality_reviewer_node(state: ProjectState) -> ProjectState:
    await emit_progress(state, "quality_reviewer", "🔍 Scoring the specifications against the quality rubric...")
    # The reviewer runs LAST in the phase, with the adversarial and
    # consistency findings in view — the score reflects them.
    docs = docs_context(
        state, [*ALL_SPEC_DOCS, "devils_advocate", "consistency_report"],
        max_chars=6000,
    )

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

    score, breakdown, top_fixes = _extract_score(response)
    feedback = _strip_json_block(response)
    history = list(state.get("quality_score_history") or [])
    if score is not None:
        history.append(score)

    # Stamp the rubric version on the stored score and the report itself,
    # so a later rubric edit can't silently re-rate already-scored packages.
    # Stamped in code, not requested from the model — the model can't forget it.
    breakdown = {**(breakdown or {}), "rubric_version": RUBRIC_VERSION}
    feedback += f"\n\n---\n\n*Scored against rubric version `{RUBRIC_VERSION}`.*"

    return {
        **state,
        "quality_score": score,
        "quality_breakdown": breakdown,
        "quality_top_fixes": top_fixes,
        "quality_score_history": history,
        "quality_feedback": feedback,
        "messages": agent_message(
            state, "quality_reviewer",
            f"🔍 **Quality Review complete** — score: "
            f"**{score if score is not None else 'n/a'}/100**. Full review with "
            f"per-gap fixes in `{DOC_PATHS['quality_feedback']}`.",
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
        "messages": agent_message(
            state, agent_id,
            f"{emoji} **{title} ready** — see `{DOC_PATHS.get(output_key, '')}` "
            "in the files panel.",
        ),
        "current_agent": agent_id,
        "pipeline_status": "running",
        "total_llm_calls": state.get("total_llm_calls", 0) + 1,
    }


async def quality_review_node(state: ProjectState) -> ProjectState:
    """Present the quality verdict. Below 80, recommend improving, not packaging."""
    score = state.get("quality_score")
    score_text = f"{score}/100" if score is not None else "n/a"
    history = state.get("quality_score_history") or []
    if len(history) > 1:
        score_text += f" (previous: {' → '.join(str(s) for s in history[:-1])})"
    passing = score is not None and score >= 80

    top_fixes = state.get("quality_top_fixes") or []
    fixes_list = "\n".join(f"{i}. {f}" for i, f in enumerate(top_fixes, 1))

    if passing:
        chat_note = (
            f"🧭 Quality phase complete — **{score_text}** (PASS). The Devil's "
            "Advocate and Consistency reports are in the files panel. Ready to package."
        )
        if fixes_list:
            chat_note += (
                "\n\nOptional — these would raise the score further:\n" + fixes_list
            )
        chat_note += (
            "\n\nChoosing *Improve the specs* also applies the Devil's Advocate "
            "mitigations and consistency fixes."
        )
        reasoning = "The specs meet the 80-point quality bar."
        recommendation = "confirm"
    else:
        chat_note = (
            f"🧭 Quality phase complete — **{score_text}**, below the 80-point bar."
        )
        if fixes_list:
            chat_note += (
                "\n\n**To raise the score, these are the highest-impact fixes:**\n"
                + fixes_list
                + "\n\n*Improve the specs* applies these plus the Devil's Advocate "
                "mitigations and consistency fixes; or type your own priority in "
                "the chat. Full gap analysis: `06_QUALITY/quality_review.md`."
            )
        else:
            chat_note += (
                " The review lists concrete gaps (see `06_QUALITY/quality_review.md`). "
                "*Improve the specs* applies them together with the Devil's Advocate "
                "mitigations and consistency fixes."
            )
        reasoning = "Packaging at this score would bake the gaps into the final documents."
        recommendation = "improve"

    return {
        **state,
        "messages": agent_message(state, "orchestrator", chat_note),
        "current_agent": "orchestrator",
        "pipeline_status": "running",
        "quality_review_done": True,
        "pending_decision": {
            "id": "approve-quality",
            "agent": "orchestrator",
            "category": "quality",
            "question": f"Quality score: {score_text}. How should we proceed?",
            "options": [
                {
                    "id": "improve",
                    "label": "Improve the specs" + ("" if passing else " (recommended)"),
                    "description": "Apply the quality gaps, Devil's Advocate mitigations "
                    "and consistency fixes, then re-score",
                },
                {
                    "id": "confirm",
                    "label": "Package the project" + (" (recommended)" if passing else " anyway"),
                    "description": "Generate the final document set and roadmap",
                },
                {
                    "id": "revise",
                    "label": "Discuss the findings first",
                    "description": "Ask about the quality gaps or risks",
                },
            ],
            "agent_recommendation": recommendation,
            "agent_reasoning": reasoning,
            "allow_delegate": True,
            "allow_freeform": True,
        },
    }


def _extract_score(text: str) -> tuple[int | None, dict | None, list[str]]:
    """Parse the trailing fenced JSON score block from the reviewer's output."""
    try:
        if "```json" in text:
            start = text.rindex("```json") + 7
            end = text.index("```", start)
            data = json.loads(text[start:end].strip())
            total = data.get("total")
            if isinstance(total, int):
                fixes = data.get("top_fixes")
                fixes = [str(f) for f in fixes] if isinstance(fixes, list) else []
                return total, {
                    **data.get("breakdown", {}),
                    "grade": data.get("grade"),
                    "verdict": data.get("verdict"),
                }, fixes
    except (ValueError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to parse quality score JSON: {e}")
    return None, None, []


def _strip_json_block(text: str) -> str:
    """Remove the trailing fenced JSON block from the displayed feedback."""
    if "```json" not in text:
        return text.strip()
    start = text.rindex("```json")
    end = text.find("```", start + 7)
    if end == -1:
        return text[:start].strip()
    return (text[:start] + text[end + 3:]).strip()
