"""Idea Analyst agent - transforms raw ideas into structured project briefs through conversation."""

import json
import logging
import re

from app.agents.llm import call_llm
from app.agents.state import ProjectState

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the Idea Analyst of ProjectFactory. You transform raw project ideas into structured briefs through a step-by-step conversation.

CRITICAL RULES:
- Ask only ONE question at a time
- Always present concrete options (A, B, C, D) when possible
- User picks an option OR types their own answer
- Keep it short and conversational
- Never dump multiple questions at once

CONVERSATION FLOW (one question per message):
1. Acknowledge the idea warmly (1-2 sentences)
2. Ask about TARGET USERS with options
3. Ask about CORE PROBLEM with options
4. Ask about KEY FEATURES with options
5. Ask about REVENUE MODEL with options
6. Ask about TECH PLATFORM with options
7. Ask about MVP SCOPE with options
8. Present final brief for confirmation

EXAMPLE FORMAT for each message:
"Great choice! Now, how should this make money?

A) Subscription (monthly/yearly plans)
B) Freemium (free basic + paid premium)
C) Commission per transaction
D) Advertising

💡 My recommendation: B (Freemium) - it's the best way to grow a user base quickly while monetizing power users.

You can pick one or more options (e.g. 'A and C'), or write your own answer."

IMPORTANT: Always end with YOUR recommendation and a short reason why. The user can agree or override.

FIELDS TO GATHER (one at a time):
- Problem Statement, Target Users, Value Proposition
- Core Features (3-5 for MVP), Revenue Model
- Category (saas/fintech/mobile/ai_ml/infrastructure/multi_platform)
- Scope: what's IN and OUT for v1

WHEN ALL FIELDS ARE GATHERED, present the complete brief and end with this JSON:

```json
{"action": "present_brief", "brief": {"problem_statement": "...", "target_users": [{"type": "...", "description": "...", "priority": "primary|secondary"}], "value_proposition": "...", "core_features": ["..."], "revenue_model": "...", "domain_category": "...", "scope_in": ["..."], "scope_out": ["..."], "additional_context": "..."}}
```

Only output JSON when presenting the FINAL brief, not while asking questions.
When you present the final brief, output ONLY the JSON block (a one-sentence
lead-in is fine) — do NOT restate the brief in prose. The interface renders
the brief for the user itself."""


async def idea_analyst_node(state: ProjectState) -> ProjectState:
    """Run the Idea Analyst: converse with user, build structured brief."""

    messages = state.get("messages", [])
    api_key = state.get("api_key")

    if not messages:
        return state

    # Build LLM message list
    llm_messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    for msg in messages:
        role = msg.get("role", "user")
        # Map our roles to LLM roles
        if role == "agent":
            llm_messages.append({"role": "assistant", "content": msg["content"]})
        elif role == "user":
            llm_messages.append({"role": "user", "content": msg["content"]})
        # Skip system messages

    # Call LLM
    try:
        response_text = await call_llm(
            messages=llm_messages,
            model_tier=2,
            api_key=api_key,
            temperature=0.7,
            max_tokens=2048,
        )
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        error_msg = {
            "id": f"msg-error-{len(messages)}",
            "role": "agent",
            "agent_id": "idea_analyst",
            "content": f"I encountered an error connecting to the AI model. Please check your API key in settings. Error: {str(e)}",
            "timestamp": "",
        }
        return {
            **state,
            "messages": [*messages, error_msg],
            "pipeline_status": "waiting_for_user",
            "current_agent": "idea_analyst",
        }

    # Check if response contains a brief JSON block
    idea_brief = _extract_brief(response_text)
    if idea_brief:
        # The brief goes to the files panel, not the chat — replace whatever
        # the model wrote with a short pointer note.
        response_text = (
            "📋 **Project brief is ready** — opened in the files panel "
            "(`00_IDEA/idea_brief.md`). Review it, then confirm below or tell "
            "me what to change."
        )

    # Add agent response to messages
    agent_msg = {
        "id": f"msg-agent-{len(messages)}",
        "role": "agent",
        "agent_id": "idea_analyst",
        "content": response_text,
        "timestamp": "",
    }

    new_messages = [*messages, agent_msg]

    if idea_brief:
        # Brief was presented - set as pending confirmation
        return {
            **state,
            "messages": new_messages,
            "idea_brief": {**idea_brief, "confirmed": False},
            "current_agent": "idea_analyst",
            "pipeline_status": "waiting_for_user",
            "pending_decision": {
                "id": "confirm-brief",
                "agent": "idea_analyst",
                "category": "strategic",
                "question": "Does this idea brief look correct?",
                "options": [
                    {"id": "confirm", "label": "Looks good, continue!", "description": "Proceed to research phase"},
                    {"id": "revise", "label": "I want to change something", "description": "Tell me what to modify"},
                ],
                "agent_recommendation": "confirm",
                "agent_reasoning": "The brief captures all key aspects of your idea.",
                "allow_delegate": False,
                "allow_freeform": True,
            },
        }
    else:
        # Still in conversation - waiting for user's next message
        return {
            **state,
            "messages": new_messages,
            "current_agent": "idea_analyst",
            "pipeline_status": "waiting_for_user",
        }


def _extract_brief(text: str) -> dict | None:
    """Extract the idea brief JSON from the agent's response, if present.

    Tolerant on purpose: models fence the JSON as ```json / ``` / ```JSON,
    write "action":"present_brief" without spaces, or skip the fence entirely.
    A missed parse means the whole brief gets dumped into the chat, so we try
    every fenced block first and then a raw top-level object as fallback.
    """
    if "present_brief" not in text:
        return None

    def _check(data) -> dict | None:
        if isinstance(data, dict) and data.get("action") == "present_brief":
            brief = data.get("brief")
            if isinstance(brief, dict) and brief:
                return brief
        return None

    # 1) Any fenced code block containing the marker
    for match in re.finditer(r"```[a-zA-Z]*\s*(.*?)```", text, re.DOTALL):
        block = match.group(1).strip()
        if "present_brief" not in block:
            continue
        try:
            brief = _check(json.loads(block))
            if brief:
                return brief
        except json.JSONDecodeError:
            continue

    # 2) Unfenced fallback: decode from the top-level "{" before "action"
    anchor = text.find('"action"')
    if anchor != -1:
        start = text.rfind("{", 0, anchor)
        if start != -1:
            try:
                data, _ = json.JSONDecoder().raw_decode(text[start:])
                brief = _check(data)
                if brief:
                    return brief
            except json.JSONDecodeError:
                pass

    logger.warning("present_brief marker found but no parseable brief JSON")
    return None
