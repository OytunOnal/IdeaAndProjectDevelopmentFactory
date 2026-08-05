"""Shared helpers for pipeline agents."""

import json
import logging
import re

from app.agents.state import ProjectState
from app.websocket.socket_app import emit_pipeline_update

logger = logging.getLogger(__name__)

# Where each document lives in the file tree (drafts + final export)
DOC_PATHS = {
    "idea_brief": "00_IDEA/idea_brief.md",
    "market_research": "01_RESEARCH/market_research.md",
    "competitor_analysis": "01_RESEARCH/competitor_analysis.md",
    "tech_feasibility": "01_RESEARCH/tech_feasibility.md",
    "research_summary": "01_RESEARCH/research_summary.md",
    "spec_summary": "05_PLANNING/specification_summary.md",
    "prd": "02_PRODUCT/prd.md",
    "ux_design": "03_DESIGN/ux_specification.md",
    "architecture": "04_TECH/architecture.md",
    "gtm_strategy": "05_PLANNING/gtm_strategy.md",
    "financial_model": "05_PLANNING/financial_model.md",
    "implementation_roadmap": "05_PLANNING/development_roadmap.md",
    "quality_feedback": "06_QUALITY/quality_review.md",
    "devils_advocate": "06_QUALITY/devils_advocate.md",
    "consistency_report": "06_QUALITY/consistency_report.md",
}

# Shared principle appended to content-producing agent prompts
CONSTRUCTIVE_PRINCIPLE = """

GUIDING PRINCIPLE: Be realistic AND constructive. Your goal is to shape this project into something buildable and commercially viable. Never dismiss an idea or a user request outright — when something is weak or infeasible as stated, propose the nearest viable version (smaller scope, different segment, different pricing, phased approach) and explain the trade-off. Every problem you raise must come with at least one concrete way to address it.

EVIDENCE RULE: never fabricate data. No invented percentages, user tests, betas, surveys, funnels, or market figures — if a number does not literally appear in your inputs or your own web research, do not cite it; make the case qualitatively instead. A made-up "closed-beta drop-off rate" is worse than no evidence.

FINAL SECTION — end your document with exactly this heading:

## Recommended Adjustments

Under it, list up to 3 NUMBERED, concrete changes to the PROJECT itself that your findings suggest. HIGH BAR: only include a recommendation if it would MATERIALLY improve the project's viability, follows directly from a specific finding in your document, and is NEW — never re-propose an adjustment already made in an earlier document (you may be shown a list of those; treat it as a blocklist). Never pad the list with filler, restatements of what the project already does, or generic advice. Having no recommendation is a perfectly good outcome — in that case write exactly: None — the current direction holds up."""


SPEC_DOC_KEYS = ("prd", "architecture", "ux_design", "gtm_strategy", "financial_model")

# Instruction block that lets discussion agents ACT instead of giving advice
ACTION_CAPABILITY = """

YOU CAN TAKE ACTION. There are no UI forms, menus, or buttons for the user to fill in — never instruct them to click or paste anything. When the user's message is a request rather than a question, do NOT explain how — trigger the work yourself by responding with ONLY a fenced JSON block:

To rewrite one document with specific feedback (also use this when the user asks to apply SOME of a document's Recommended Adjustments — name the items in the feedback). Include "then": "continue" ONLY when the user explicitly wants to skip reviewing the result ("apply and move on", "ekle ve sonrakine geç"). "Re-run this step and continue from there" ("baştan çalıştır ve oradan devam edelim") means they DO want to see the re-run output — use "then": "review":
```json
{"action": "revise", "target": "<one of: market_research|competitor_analysis|tech_feasibility|prd|architecture|ux_design|gtm_strategy|financial_model>", "feedback": "<the concrete change request, self-contained>", "then": "continue|review"}
```

To run an improvement pass across the specs (e.g. fixing quality gaps or consistency issues):
```json
{"action": "improve", "focus": "<what to prioritize>", "targets": ["<optional doc keys to limit the pass>"]}
```

To approve the document currently awaiting approval — use this when the user signals acceptance or wants to move on WITHOUT changing the document (e.g. "looks good", "noted, let's continue", "save these suggestions for later and proceed"):
```json
{"action": "approve", "target": "<doc_key of the document awaiting approval>"}
```

To go BACK to an earlier step of the current phase ("devils advocate adımına geri dönelim", "go back to the PRD") — this reopens that document's approval gate WITHOUT rewriting anything:
```json
{"action": "reopen", "target": "<doc_key>"}
```

IMPORTANT — intent rules (the user may write in any language, often Turkish; judge intent, not keywords):
- "rewrite this" / "redo it" / "tekrar yazar mısın" / "baştan yaz" → revise. If they gave no specifics, use feedback: "Rewrite the document from scratch with substantially higher quality and specificity."
- "go back to X" / "X adımına geri dönelim" → reopen (navigation, NOT a rewrite).
- "looks good" / "let's continue" / "devam edelim" / "sonrakine geç" → approve.
- A request for changes NEVER means approve, and wanting to continue NEVER means revise.
- Pure commentary, praise, or amusement with no decision ("vay be", "wow, harsh 😄", "interesting") is NOT an approval and NOT a request — ask in one short sentence what they'd like to do.
- A strong negative reaction with NO direction ("bu hiç olmamış", "this really isn't it") → do NOT rewrite blindly; ask ONE short question about what specifically falls short.
- BUT a hedged or reluctant message that still names a CONCRETE shortcoming ("tamam da rakip analizi yüzeysel", "fine I guess... though the onboarding feels heavy") → treat the named shortcoming as a change request and revise with it as feedback. Ask only when nothing concrete is named.
- Self-contradictory instructions ("don't change anything, but fix X") → point out the tension in one sentence and ask which they want; take no action yet.
- Conditional decisions ("if X holds, approve; otherwise fix it") → never guess the branch: check X against the documents, report what you found in plain text, and let the user decide.
- When a message requests edits to MULTIPLE documents, set "target" to the document currently awaiting approval (if it is one of them) and fold the other documents' changes into the feedback so nothing is lost.
- If the intent is genuinely ambiguous, ask one short clarifying question in plain text — never approve on an ambiguous message. Only answer in plain text when the user is asking a question.
- If the message is unrelated to this project (small talk, random text, a different topic), take NO action and do not force a connection to the project — reply in one friendly sentence that you're focused on this project and point back to what's currently pending.
- Choosing revise "target": it is the document the change BELONGS to — by default the document currently awaiting approval. NEVER route by topic keywords: a pricing complaint made while the GTM doc is gated targets gtm_strategy, NOT financial_model just because pricing sounds financial. Pick a different document only when the user names it.

Calibration examples (message → action):
- "lgtm 🚀" / "ship it" / "👍" / "onayldım dvm" / "aprove, next pls" → approve (casual, emoji-only, or typo'd approvals are still approvals)
- "se ve muy bien, sigamos adelante" → approve (any language)
- "eline sağlık çok güzel olmuş, devam edelim" → approve (praise WITH an explicit continue)
- "vay be, sert eleştirmiş 😄" / "wow, it really tore the idea apart" → NO action, ask what they'd like to do (praise/commentary WITHOUT a decision is not an approval — the difference from the previous example is the missing "continue")
- "şimdilik onaylama" / "don't approve it yet" → NO action; acknowledge you'll wait
- "tamam da rakip analizi yüzeysel olmuş" → revise (a named shortcoming outweighs the "tamam")"""


def parse_action(text: str) -> dict | None:
    """Extract an {"action": ...} JSON block from a discussion agent's reply."""
    import json as _json

    if "```json" not in text or '"action"' not in text:
        return None
    try:
        start = text.index("```json") + 7
        end = text.index("```", start)
        data = _json.loads(text[start:end].strip())
        if isinstance(data, dict) and data.get("action") in (
            "revise", "improve", "approve", "reopen"
        ):
            return data
    except (ValueError, _json.JSONDecodeError):
        pass
    return None


# Which documents belong to which phase's gates (reopen is same-phase only —
# cross-phase rollback would need phase state rewinding)
PHASE_DOC_KEYS = {
    "discovery": ("market_research", "competitor_analysis", "tech_feasibility"),
    "specification": ("prd", "architecture", "ux_design", "gtm_strategy", "financial_model"),
    "quality": ("devils_advocate", "consistency_report"),
}

# How users refer to documents in chat (lowercase substrings, EN + TR)
DOC_ALIASES = {
    "market_research": ("market", "pazar"),
    "competitor_analysis": ("competitor", "rakip"),
    "tech_feasibility": ("tech feasibility", "feasibility", "fizibilite"),
    "prd": ("prd", "spec'", "the spec", "specs"),
    "architecture": ("architecture", "mimari"),
    "ux_design": ("ux",),
    "gtm_strategy": ("gtm", "go-to-market"),
    "financial_model": ("financial", "finans"),
    "devils_advocate": ("devil", "şeytan"),
    "consistency_report": ("consistency", "tutarl"),
}


def _last_user_message(state: ProjectState) -> str:
    for msg in reversed(state.get("messages") or []):
        if msg.get("role") == "user":
            return msg.get("content", "")
    return ""


async def verify_discussion_action(state: ProjectState, action: dict) -> dict | None:
    """Semantic verification of high-stakes discussion actions.

    Design decision (2026-08-05): keyword overrides were rejected — meaning is
    expressed in unbounded ways and pattern lists are both brittle and prone to
    eval-overfitting. Instead we exploit the MEASURED strength of small models:
    they are weak at broad open-ended action parsing but near-frontier on
    narrow, well-specified questions. So before applying a state-changing
    action, we ask one narrow question about it. Local inference makes this
    second call free.
    """
    from app.agents.llm import call_llm

    act = action.get("action")
    user_msg = _last_user_message(state)

    if act == "approve":
        # Narrow yes/no: is this a go-ahead? The policy definition lives here —
        # casual forms COUNT as approvals; only no-decision or negated don't.
        question = (
            f'The user\'s latest message in a project chat:\n"{user_msg}"\n\n'
            "Is this message a go-ahead to approve the current document and "
            "continue NOW? Casual and short forms COUNT as approvals: a bare "
            'thumbs-up emoji, "lgtm", "ship it", typo\'d approvals, and praise '
            'that includes a continue ("çok güzel, devam edelim"). Answer no '
            "ONLY when there is genuinely no go-ahead — pure commentary or "
            'praise with no decision, a question, a conditional ("approve if"), '
            'or a negated approval ("don\'t approve yet"). '
            "Answer with exactly one word: yes or no."
        )
        try:
            reply = await call_llm(
                messages=[{"role": "user", "content": question}],
                model_tier=3, temperature=0.0, max_tokens=10,
                role="verify", think=False,  # narrow question — thinking only adds failure modes
            )
        except Exception:
            return action  # verification unavailable → let the action stand
        if not reply.strip():
            return action  # FAIL OPEN: an empty verdict must not veto the action
        if "yes" not in reply.strip().lower()[:20]:
            logger.info("Approve action rejected by semantic verification")
            return None
        return action

    if act == "revise":
        gate = current_gate_key(state)
        if not gate or action.get("target") == gate:
            return action
        # Narrow multiple-choice: which document does the change belong to?
        keys = ", ".join(DOC_PATHS)
        question = (
            f'The user\'s latest message in a project chat:\n"{user_msg}"\n\n'
            f'A change request must be routed to one document. The document '
            f'currently open for the user\'s review is "{gate}". Which document '
            f"does the user's request refer to? Unless they clearly named a "
            f"different document, the answer is the open one. "
            f"Answer with exactly one key from: {keys}"
        )
        try:
            reply = await call_llm(
                messages=[{"role": "user", "content": question}],
                model_tier=3, temperature=0.0, max_tokens=20,
                role="verify", think=False,
            )
        except Exception:
            return action
        chosen = [k for k in DOC_PATHS if k in reply.strip().lower()]
        if len(chosen) == 1 and chosen[0] != action.get("target"):
            logger.info(
                f"Revise target corrected by verification: {action.get('target')} -> {chosen[0]}"
            )
            return {**action, "target": chosen[0]}
        return action

    return action

_REOPEN_REQUEST = re.compile(
    r"(?i)go back to|return to|reopen|geri dön|geri don|adımına dön|adimina don"
)


def reopen_request_shortcut(state: ProjectState) -> dict | None:
    """'Go back to step X' handled deterministically — navigation, not rewrite."""
    messages = state.get("messages") or []
    if not messages or messages[-1].get("role") != "user":
        return None
    msg = messages[-1].get("content", "")
    if not _REOPEN_REQUEST.search(msg):
        return None
    lower = msg.lower()
    matches = [
        key for key, aliases in DOC_ALIASES.items()
        if any(alias in lower for alias in aliases)
    ]
    if len(matches) != 1:
        return None  # no target or ambiguous — let the LLM sort it out
    return apply_discussion_action(state, {"action": "reopen", "target": matches[0]})


# Unambiguous rewrite requests — handled deterministically, no LLM
# classification involved (a weak model once read "tekrar yazar mısın"
# as approval and silently moved on).
_REWRITE_REQUEST = re.compile(
    r"(?i)\brewrite\b|\bredo\b|\bregenerate\b|\bre-?run\b|write (?:it|this) again"
    r"|(?:tekrar|yeniden|baştan|bastan)\s*(?:yaz|çalıştır|calistir|oluştur|olustur|üret|uret)"
)


def rewrite_request_shortcut(state: ProjectState) -> dict | None:
    """If the last user message clearly asks to rewrite the gated document,
    trigger the revision directly — don't gamble on LLM intent parsing."""
    messages = state.get("messages") or []
    if not messages or messages[-1].get("role") != "user":
        return None
    msg = messages[-1].get("content", "")
    if not _REWRITE_REQUEST.search(msg):
        return None
    gate = current_gate_key(state)
    if not gate:
        return None
    # If a DIFFERENT document is named, let the LLM route it instead
    lower = msg.lower()
    for key in DOC_PATHS:
        if key != gate and (key in lower or key.replace("_", " ") in lower):
            return None
    feedback = msg
    if len(msg.strip()) < 60:  # bare "rewrite this" — give the agent a real brief
        feedback = (
            f"{msg}\n\nRewrite the document from scratch with substantially "
            "higher quality, more specificity, and better grounding."
        )
    return apply_discussion_action(
        state, {"action": "revise", "target": gate, "feedback": feedback}
    )


def current_gate_key(state: ProjectState) -> str | None:
    """The doc key currently awaiting approval, if any."""
    card = current_gate_card(state)
    if card and card["id"].startswith("approve-doc:"):
        return card["id"].split(":", 1)[1]
    return None


# Negated-approve guard: local models (measured: qwen3:8b think-off) executed
# the OPPOSITE of "don't approve yet". Critical intents live in code, not in
# prompt-following — same principle as the rewrite/reopen shortcuts.
# Conservative multilingual patterns; "(?<!why\s)" spares "why don't we
# approve it?" which actually means approve.
_NEGATED_APPROVE = re.compile(
    r"(?i)(?:"
    r"\bonaylamay?(?:a[lı]ım|ın)?\b|\bonay verme\b|approve\s*etmey?"  # TR
    r"|(?<!why\s)(?:don'?t|do not|never)\s+(?:\w+\s+){0,2}approve"    # EN
    r"|\bnot\s+approve\b|hold off on approv|wait (?:before|to) approv"
    r"|no (?:lo )?apruebes|no aprobar"                                # ES
    r"|nicht (?:genehmigen|freigeben)"                                # DE
    r")"
)


def _approve_negated(state: ProjectState) -> bool:
    """True if the last user message forbids approving right now."""
    messages = state.get("messages") or []
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return bool(_NEGATED_APPROVE.search(msg.get("content", "")))
    return False


def apply_discussion_action(state: ProjectState, action: dict) -> dict | None:
    """Turn a discussion agent's action JSON into pipeline state, or None."""
    act = action.get("action")

    if act == "approve" and _approve_negated(state):
        logger.info("Approve action blocked by negation guard")
        return None

    if act == "approve":
        target = action.get("target") or current_gate_key(state)
        if target in DOC_PATHS and get_doc(state, target):
            approved = list(state.get("approved_docs") or [])
            if target not in approved:
                approved.append(target)
            return {
                **state,
                "approved_docs": approved,
                "messages": agent_message(
                    state, "orchestrator",
                    f"✅ {DOC_TITLES.get(target, target)} approved — moving on.",
                ),
                "current_agent": "orchestrator",
                "pipeline_status": "running",
                "pending_decision": None,
            }
        return None

    if act == "reopen":
        target = action.get("target")
        phase = state.get("current_phase")
        if (
            target in PHASE_DOC_KEYS.get(phase, ())
            and get_doc(state, target)
        ):
            approved = [k for k in (state.get("approved_docs") or []) if k != target]
            return {
                **state,
                "approved_docs": approved,
                "messages": agent_message(
                    state, "orchestrator",
                    f"🔁 Reopened the {DOC_TITLES.get(target, target)} — it's in "
                    f"the files panel (`{DOC_PATHS.get(target, '')}`), unchanged. "
                    "Approve it, request changes, or ask to re-run it.",
                ),
                "current_agent": "orchestrator",
                "pipeline_status": "running",
                "pending_decision": doc_gate_card(
                    target, bool(extract_adjustments(get_doc(state, target)))
                ),
            }
        return None

    if act == "revise":
        target = action.get("target")
        feedback = (action.get("feedback") or "").strip()
        if target in DOC_PATHS and get_doc(state, target) and feedback:
            then = "continue" if action.get("then") == "continue" else None
            # Applying the doc's own adjustments? Consume them after the rewrite.
            is_apply = "adjustment" in feedback.lower()
            return {
                **state,
                "revision_target": target,
                "revision_feedback": feedback,
                "revision_is_apply": is_apply,
                "revision_then": then,
                "messages": agent_message(
                    state, "orchestrator",
                    f"✏️ On it — sending your request to the "
                    f"{DOC_TITLES.get(target, target)} owner"
                    + (" (will continue afterwards)" if then else "")
                    + "...",
                ),
                "current_agent": "orchestrator",
                "pipeline_status": "running",
                "pending_decision": None,
            }
        return None

    if act == "improve":
        focus = (action.get("focus") or "").strip()
        targets = [t for t in (action.get("targets") or []) if t in SPEC_DOC_KEYS]

        if state.get("current_phase") == "quality":
            return {
                **state,
                "quality_improve_requested": True,
                "quality_improve_focus": focus or None,
                "quality_improve_targets": targets,
                "messages": agent_message(
                    state, "orchestrator",
                    "🔧 Running an improvement pass"
                    + (f" focused on: {focus}" if focus else "")
                    + (f" (documents: {', '.join(targets)})" if targets else "")
                    + "...",
                ),
                "current_agent": "orchestrator",
                "pipeline_status": "running",
                "pending_decision": None,
            }

        # Outside the quality phase, a single clear target becomes a revision
        if len(targets) == 1 and get_doc(state, targets[0]) and focus:
            return apply_discussion_action(
                state, {"action": "revise", "target": targets[0], "feedback": focus}
            )
        return None

    return None


# Tolerant heading match. Models write the section heading every way
# imaginable: "## Recommended Adjustments", "### recommended adjustments",
# "**Recommended Adjustments:**", numbered ("## 6. Recommended Adjustments"),
# or translated when the whole document comes out in Turkish
# ("## Önerilen Ayarlamalar"). Missing it in either direction is a UX bug:
# a missed heading hides real suggestions; a missed "None" shows dead buttons.
_ADJUSTMENTS_HEADING = re.compile(
    r"(?im)^[ \t]{0,3}(?:#{2,4}[ \t]*|\*\*[ \t]*)?(?:\d+[.)][ \t]*)?"
    r"(?:recommended[ \t]+adjustments?"
    r"|önerilen[ \t]+(?:ayarlamalar|düzenlemeler|değişiklikler|iyileştirmeler)"
    r"|tavsiye[ \t]+edilen[ \t]+(?:ayarlamalar|düzenlemeler|değişiklikler))"
    r"[^\S\n]*[:*]{0,3}[^\S\n]*$"
)


def extract_adjustments(text: str | None) -> str | None:
    """Pull the Recommended Adjustments section out of a document."""
    if not text:
        return None
    match = _ADJUSTMENTS_HEADING.search(text)
    if not match:
        return None
    rest = text[match.end():]
    # Section ends at the next heading (or end of document)
    next_heading = re.search(r"(?m)^[ \t]{0,3}#{1,4}[ \t]", rest)
    section = (rest[: next_heading.start()] if next_heading else rest).strip()
    # "None" may arrive decorated ("**None** — ...", "- None ...") or in
    # Turkish ("Yok — mevcut yön uygun.")
    normalized = section.lower().lstrip("*_-•>#:().0123456789 \t\n")
    if not section or normalized.startswith(("none", "yok", "hayır")):
        return None
    return section


def consume_adjustments(text: str) -> str:
    """Replace the Recommended Adjustments section with an 'applied' note.

    Called after adjustments are applied in a revision. Without this, the
    revision prompt's mandatory-section rule makes the model re-propose the
    same items, and the approval gate loops forever.
    """
    match = _ADJUSTMENTS_HEADING.search(text)
    if match:
        rest = text[match.end():]
        next_heading = re.search(r"(?m)^[ \t]{0,3}#{1,4}[ \t]", rest)
        tail = rest[next_heading.start():] if next_heading else ""
        text = text[: match.start()].rstrip() + ("\n\n" + tail.strip() if tail else "")
    return (
        text.rstrip()
        + "\n\n## Recommended Adjustments\n\nNone — the accepted adjustments have been applied.\n"
    )


# Note: no fallback generator on purpose. If a document carries no
# Recommended Adjustments section (or says "None"), that means "nothing
# worth suggesting" — the gate simply shows no apply buttons. Forcing
# suggestions into existence produced filler recommendations.

DOC_TITLES = {
    "idea_brief": "Idea Brief",
    "research_summary": "Research Summary",
    "spec_summary": "Specification Summary",
    "market_research": "Market Research",
    "competitor_analysis": "Competitor Analysis",
    "tech_feasibility": "Tech Feasibility",
    "prd": "Product Requirements Document (PRD)",
    "architecture": "System Architecture",
    "ux_design": "UX Specification",
    "gtm_strategy": "Go-to-Market Strategy",
    "financial_model": "Financial Model",
    "quality_feedback": "Quality Review",
    "devils_advocate": "Devil's Advocate Report",
    "consistency_report": "Consistency Report",
    "implementation_roadmap": "Implementation Roadmap",
}


def get_doc(state: ProjectState, key: str) -> str | None:
    """Return a document's text whether it's stored as str or research dict."""
    value = state.get(key)
    if isinstance(value, dict):
        return value.get("report")
    return value or None


def docs_context(state: ProjectState, keys: list[str], max_chars: int = 12000) -> str:
    """Concatenate the requested documents as markdown context for a prompt.

    Each document's Recommended Adjustments section is stripped first —
    downstream agents were parroting earlier documents' suggestions as
    their own.
    """
    parts = []
    for key in keys:
        doc = get_doc(state, key)
        if doc:
            doc = strip_adjustments_section(doc)
            parts.append(f"## {DOC_TITLES.get(key, key)}\n\n{doc[:max_chars]}")
    return "\n\n---\n\n".join(parts)


def strip_adjustments_section(text: str) -> str:
    """Remove the Recommended Adjustments section from a document."""
    match = _ADJUSTMENTS_HEADING.search(text)
    if not match:
        return text
    rest = text[match.end():]
    next_heading = re.search(r"(?m)^[ \t]{0,3}#{1,4}[ \t]", rest)
    tail = rest[next_heading.start():] if next_heading else ""
    return (text[: match.start()].rstrip() + ("\n\n" + tail.lstrip() if tail else "")).strip()


def record_applied_adjustments(state: ProjectState, source_key: str) -> list:
    """Return applied_adjustments with the source doc's current items added."""
    applied = list(state.get("applied_adjustments") or [])
    adj = extract_adjustments(get_doc(state, source_key))
    if adj:
        entry = f"From {DOC_TITLES.get(source_key, source_key)}:\n{adj}"
        if entry not in applied:
            applied.append(entry)
    return applied


def prior_adjustments_blocklist(state: ProjectState) -> str:
    """A prompt block listing adjustments already proposed and already applied."""
    parts = []

    items = []
    for key in DOC_PATHS:
        adj = extract_adjustments(get_doc(state, key))
        if adj:
            items.append(f"From {DOC_TITLES.get(key, key)}:\n{adj}")
    if items:
        parts.append(
            "ADJUSTMENTS ALREADY PROPOSED to the user in earlier documents — "
            "this is a BLOCKLIST. Do not propose these again in any wording; "
            "only materially NEW adjustments are allowed:\n\n"
            + "\n\n".join(items)
        )

    applied = state.get("applied_adjustments") or []
    if applied:
        parts.append(
            "ADJUSTMENTS ALREADY APPLIED to the project — these are DONE. "
            "Never re-propose them or trivial variations of them; treat the "
            "concerns behind them as addressed unless the documents clearly "
            "show otherwise:\n\n" + "\n\n".join(applied[-12:])
        )

    if not parts:
        return ""
    return "\n\n" + "\n\n".join(parts)


def format_brief(brief: dict) -> str:
    """Render the structured idea brief as readable markdown."""
    users = ", ".join(
        f"{u.get('type', '?')} ({u.get('priority', '')})"
        for u in brief.get("target_users", [])
    )
    features = "\n".join(f"- {f}" for f in brief.get("core_features", []))
    scope_in = ", ".join(brief.get("scope_in", []))
    scope_out = ", ".join(brief.get("scope_out", []))

    return (
        f"**Problem:** {brief.get('problem_statement', '—')}\n\n"
        f"**Target users:** {users or '—'}\n\n"
        f"**Value proposition:** {brief.get('value_proposition', '—')}\n\n"
        f"**Core features:**\n{features or '—'}\n\n"
        f"**Revenue model:** {brief.get('revenue_model', '—')}\n\n"
        f"**Category:** {brief.get('domain_category', '—')}\n\n"
        f"**In scope (v1):** {scope_in or '—'}\n\n"
        f"**Out of scope (v1):** {scope_out or '—'}"
        + (
            f"\n\n**Additional context:** {brief['additional_context']}"
            if brief.get("additional_context")
            else ""
        )
    )


def brief_context(state: ProjectState) -> str:
    """Render the confirmed idea brief as prompt context."""
    brief = state.get("idea_brief", {})
    clean = {k: v for k, v in brief.items() if k != "confirmed"}
    return (
        f"Project name: {state.get('project_name', 'Untitled')}\n\n"
        f"Confirmed idea brief:\n```json\n{json.dumps(clean, indent=2, ensure_ascii=False)}\n```"
    )


def agent_message(state: ProjectState, agent_id: str, content: str) -> list:
    """Return the message list with a new agent message appended."""
    messages = list(state.get("messages", []))
    messages.append({
        "id": f"msg-agent-{len(messages)}",
        "role": "agent",
        "agent_id": agent_id,
        "content": content,
        "timestamp": "",
    })
    return messages


def doc_gate_card(key: str, has_adjustments: bool = False) -> dict:
    """Approval card shown after a document is produced or revised."""
    title = DOC_TITLES.get(key, key)
    path = DOC_PATHS.get(key, key)

    question = f"{title} is ready — review it in the files panel ({path})."
    options = [
        {
            "id": "confirm",
            "label": "Approve as-is",
            "description": "Accept this document and move on",
        },
    ]
    if has_adjustments and key in ("devils_advocate", "consistency_report"):
        # Report recommendations are applied to the SPEC documents, after
        # which consistency re-checks them — "review again" would have
        # nothing of THIS report to show, so it's a single honest option.
        question += (
            " Its numbered recommendations target the spec documents — apply "
            "them and continue, or apply and stay at this step to re-check. "
            "To apply only some, type in the chat (e.g. 'apply 1 and 3')."
        )
        options.append({
            "id": "apply",
            "label": "Apply to the specs & continue",
            "description": "Integrate these recommendations into the spec documents; "
            "consistency re-checks them next",
        })
        if key == "devils_advocate":
            options.append({
                "id": "apply_recheck",
                "label": "Apply & re-run this check",
                "description": "Integrate into the specs, then re-run the adversarial "
                "analysis on the updated documents — stay at this step",
            })
    elif has_adjustments:
        question += (
            " It ends with numbered Recommended Adjustments — apply them and "
            "keep moving, apply and re-review, or approve as-is. To apply only "
            "some, type in the chat (e.g. 'apply 1 and 3')."
        )
        options.append({
            "id": "apply",
            "label": "Apply adjustments & continue",
            "description": "Integrate the recommendations and move on — no extra review round",
        })
        options.append({
            "id": "apply_review",
            "label": "Apply adjustments & review again",
            "description": "Integrate the recommendations, then show me the result",
        })
    options.append({
        "id": "revise",
        "label": "Request changes",
        "description": "Describe what should be different — the agent will rewrite it",
    })

    return {
        "id": f"approve-doc:{key}",
        "agent": "orchestrator",
        "category": "strategic",
        "question": question,
        "options": options,
        "agent_recommendation": "apply" if has_adjustments else "confirm",
        "agent_reasoning": (
            "The adjustments come from the document's own findings."
            if has_adjustments
            else "Review the document before the pipeline builds on it."
        ),
        "allow_delegate": True,
        "allow_freeform": True,
    }


def current_gate_card(state: ProjectState) -> dict | None:
    """The approval card that should be open right now, given pipeline state.

    Used by discussion agents to re-present the correct card after answering
    a question. Returns None when nothing needs approval (e.g. completed).
    """
    phase = state.get("current_phase")
    approved = state.get("approved_docs") or []

    if phase == "discovery":
        for key in ("market_research", "competitor_analysis", "tech_feasibility"):
            doc = state.get(key)
            if isinstance(doc, dict) and doc.get("completed") and key not in approved:
                return doc_gate_card(key, bool(extract_adjustments(get_doc(state, key))))
        return None  # research_review builds its own phase card

    if phase == "specification":
        for key in ("prd", "architecture", "ux_design", "gtm_strategy", "financial_model"):
            if state.get(key) and key not in approved:
                return doc_gate_card(key, bool(extract_adjustments(get_doc(state, key))))
        return None

    if phase == "quality":
        for key in ("devils_advocate", "consistency_report"):
            if get_doc(state, key) and key not in approved:
                return doc_gate_card(key, bool(extract_adjustments(get_doc(state, key))))
        return None

    return None


async def emit_progress(state: ProjectState, agent_id: str, note: str) -> None:
    """Push a live 'working on it' update to WebSocket clients.

    The transient message is NOT stored in state — the final pipeline
    response replaces it with the real output.
    """
    project_id = state.get("project_id")
    if not project_id:
        return
    transient = {
        "id": f"msg-progress-{agent_id}",
        "role": "agent",
        "agent_id": agent_id,
        "content": note,
        "timestamp": "",
    }
    try:
        await emit_pipeline_update(project_id, {
            **state,
            "messages": [*state.get("messages", []), transient],
            "current_agent": agent_id,
            "pipeline_status": "running",
        })
    except Exception:  # never let progress reporting break the pipeline
        logger.debug("Progress emit failed", exc_info=True)
