"""LLM utility layer - multi-provider support with BYOK.

Supports: Anthropic (Claude), Groq (free - dev default), DeepSeek, OpenAI.
Uses Anthropic SDK for Claude, OpenAI-compatible SDK for Groq/DeepSeek.
"""

import logging
from collections.abc import AsyncGenerator

import anthropic
import httpx
import truststore

from app.config import settings

# Use the OS certificate store (fixes SSL verification on Windows without
# disabling it). Idempotent; affects all ssl.SSLContext created afterwards.
truststore.inject_into_ssl()

logger = logging.getLogger(__name__)

# Provider configurations
PROVIDERS = {
    "google": {
        "tier1": "gemini-flash-latest",
        "tier2": "gemini-flash-latest",
        "tier3": "gemini-2.0-flash",
    },
    "cerebras": {
        "tier1": "gpt-oss-120b",
        "tier2": "gpt-oss-120b",
        "tier3": "gemma-4-31b",
    },
    "anthropic": {
        "tier1": "claude-opus-4-8",
        "tier2": "claude-sonnet-4-6",
        "tier3": "claude-haiku-4-5-20251001",
    },
    "groq": {
        "tier1": "llama-3.3-70b-versatile",
        "tier2": "llama-3.3-70b-versatile",
        "tier3": "llama-3.1-8b-instant",
    },
    "deepseek": {
        "tier1": "deepseek-chat",
        "tier2": "deepseek-chat",
        "tier3": "deepseek-chat",
    },
    # Local models (Ollama) — models are configurable via .env
    "ollama": {
        "tier1": settings.ollama_model_quality,
        "tier2": settings.ollama_model_fast,
        "tier3": settings.ollama_model_fast,
    },
}


def _get_provider_and_key() -> tuple[str, str]:
    """Determine which LLM provider to use based on available keys.
    Priority: Google (1M TPM) > Cerebras (60K TPM, fastest) > Groq (6K TPM) > DeepSeek > Anthropic
    """
    if settings.google_api_key:
        return "google", settings.google_api_key
    if settings.cerebras_api_key:
        return "cerebras", settings.cerebras_api_key
    if settings.groq_api_key:
        return "groq", settings.groq_api_key
    if settings.deepseek_api_key:
        return "deepseek", settings.deepseek_api_key
    if settings.anthropic_api_key:
        return "anthropic", settings.anthropic_api_key
    raise RuntimeError("No LLM API key configured. Set GOOGLE_API_KEY, GROQ_API_KEY, DEEPSEEK_API_KEY, or ANTHROPIC_API_KEY in .env")


def _get_all_providers() -> list[tuple[str, str]]:
    """Return all configured providers in priority order."""
    # Eval/experiment mode: pin every call to one provider (deterministic,
    # rate-limit-free measurement — e.g. LLM_FORCE_PROVIDER=ollama)
    if settings.llm_force_provider:
        forced = settings.llm_force_provider
        key = "ollama" if forced == "ollama" else dict(_configured_providers()).get(forced, "")
        return [(forced, key)]
    providers = _configured_providers()
    if settings.ollama_enabled:
        providers.append(("ollama", "ollama"))  # local fallback, no key needed
    return providers


def _configured_providers() -> list[tuple[str, str]]:
    providers = []
    if settings.google_api_key:
        providers.append(("google", settings.google_api_key))
    if settings.google_api_key_2:
        providers.append(("google", settings.google_api_key_2))
    if settings.cerebras_api_key:
        providers.append(("cerebras", settings.cerebras_api_key))
    if settings.groq_api_key:
        providers.append(("groq", settings.groq_api_key))
    if settings.deepseek_api_key:
        providers.append(("deepseek", settings.deepseek_api_key))
    if settings.anthropic_api_key:
        providers.append(("anthropic", settings.anthropic_api_key))
    return providers


async def call_llm(
    messages: list[dict],
    model_tier: int = 2,
    api_key: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> str:
    """Make a non-streaming LLM call with automatic fallback.

    Tries the resolved provider first. On failure (rate limit, no credits, etc.)
    falls back to the next available provider.
    """
    # If user provided a specific key, try that first then fall back
    if api_key and api_key.strip():
        provider, key = _resolve_provider(api_key)
        try:
            return await _call_single(messages, provider, key, model_tier, temperature, max_tokens)
        except Exception as e:
            logger.warning(f"Provider {provider} (user key) failed: {e}. Trying fallbacks...")

    # Try all configured providers with retry on rate limit
    errors = []
    for provider, key in _get_all_providers():
        for attempt in range(2):  # retry once on 429
            try:
                return await _call_single(messages, provider, key, model_tier, temperature, max_tokens)
            except Exception as e:
                err_str = str(e)
                if "429" in err_str and attempt == 0:
                    logger.info(f"Provider {provider} rate limited, retrying in 10s...")
                    import asyncio
                    await asyncio.sleep(10)
                    continue
                logger.warning(f"Provider {provider} failed: {e}. Trying next...")
                errors.append(f"{provider}: {e}")
                break

    raise RuntimeError("All LLM providers failed:\n" + "\n".join(errors))


async def stream_llm(
    messages: list[dict],
    model_tier: int = 2,
    api_key: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> AsyncGenerator[str, None]:
    """Stream LLM response with automatic fallback on failure."""
    if api_key and api_key.strip():
        provider, key = _resolve_provider(api_key)
        try:
            async for chunk in _stream_single(messages, provider, key, model_tier, temperature, max_tokens):
                yield chunk
            return
        except Exception as e:
            logger.warning(f"Stream provider {provider} (user key) failed: {e}. Trying fallbacks...")

    for provider, key in _get_all_providers():
        for attempt in range(2):
            try:
                async for chunk in _stream_single(messages, provider, key, model_tier, temperature, max_tokens):
                    yield chunk
                return
            except Exception as e:
                if "429" in str(e) and attempt == 0:
                    logger.info(f"Stream provider {provider} rate limited, retrying in 10s...")
                    import asyncio
                    await asyncio.sleep(10)
                    continue
                logger.warning(f"Stream provider {provider} failed: {e}. Trying next...")
                break

    raise RuntimeError("All LLM providers failed for streaming.")


async def _call_single(
    messages: list[dict], provider: str, key: str, model_tier: int,
    temperature: float, max_tokens: int,
) -> str:
    model = PROVIDERS[provider][f"tier{model_tier}"]
    if provider == "anthropic":
        return await _call_anthropic(messages, model, key, temperature, max_tokens)
    if provider == "ollama":
        # Native API: the OpenAI-compat endpoint ignores think-control, and
        # Qwen3 then burns the whole token budget inside <think> blocks.
        # Policy: tier1 (quality roles) thinks; tier2/3 (interactive) doesn't.
        # OLLAMA_THINK=on|off overrides for experiments.
        return await _call_ollama_native(
            messages, model, temperature, max_tokens, think=_ollama_think(model_tier)
        )
    base_url = _get_base_url(provider)
    return await _call_openai_compat(messages, model, key, base_url, temperature, max_tokens)


def _ollama_think(model_tier: int) -> bool:
    override = settings.ollama_think.strip().lower()
    if override in ("on", "off"):
        return override == "on"
    return model_tier == 1


async def _call_ollama_native(
    messages: list[dict], model: str,
    temperature: float, max_tokens: int, think: bool,
) -> str:
    """Call Ollama's native /api/chat (supports think on/off, unlike its
    OpenAI-compat endpoint). Local model — generous timeout, no API key."""
    base = settings.ollama_base_url.removesuffix("/v1")
    # Thinking tokens count against num_predict; without headroom the final
    # answer gets truncated away inside the reasoning.
    num_predict = max(max_tokens, 4096) if think else max_tokens
    async with httpx.AsyncClient(timeout=900) as client:
        resp = await client.post(f"{base}/api/chat", json={
            "model": model,
            "messages": messages,
            "think": think,
            "stream": False,
            # num_ctx: Ollama's default context window (~4k) silently truncates
            # long-prompt + thinking runs — measured: 35B report calls returned
            # empty content because thinking never fit. 16k covers the report
            # agents' 12.5k-char doc context with thinking headroom.
            "options": {"temperature": temperature, "num_predict": num_predict,
                        "num_ctx": 16384},
        })
        resp.raise_for_status()
        return resp.json()["message"]["content"]


async def _stream_single(
    messages: list[dict], provider: str, key: str, model_tier: int,
    temperature: float, max_tokens: int,
) -> AsyncGenerator[str, None]:
    model = PROVIDERS[provider][f"tier{model_tier}"]
    if provider == "anthropic":
        async for chunk in _stream_anthropic(messages, model, key, temperature, max_tokens):
            yield chunk
    elif provider == "ollama":
        async for chunk in _stream_ollama_native(
            messages, model, temperature, max_tokens, think=_ollama_think(model_tier)
        ):
            yield chunk
    else:
        base_url = _get_base_url(provider)
        async for chunk in _stream_openai_compat(messages, model, key, base_url, temperature, max_tokens):
            yield chunk


async def _stream_ollama_native(
    messages: list[dict], model: str,
    temperature: float, max_tokens: int, think: bool,
) -> AsyncGenerator[str, None]:
    """Stream from Ollama's native /api/chat (ndjson lines)."""
    import json as _json

    base = settings.ollama_base_url.removesuffix("/v1")
    async with httpx.AsyncClient(timeout=900) as client:
        async with client.stream("POST", f"{base}/api/chat", json={
            "model": model,
            "messages": messages,
            "think": think,
            "stream": True,
            "options": {"temperature": temperature, "num_predict": max_tokens,
                        "num_ctx": 16384},
        }) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                data = _json.loads(line)
                piece = (data.get("message") or {}).get("content", "")
                if piece:
                    yield piece


def _resolve_provider(api_key: str | None) -> tuple[str, str]:
    """Figure out which provider to use from the API key format."""
    if api_key:
        if api_key.startswith("sk-ant-"):
            return "anthropic", api_key
        if api_key.startswith("gsk_"):
            return "groq", api_key
        if api_key.startswith("AIza"):
            return "google", api_key
        if api_key.startswith("csk-"):
            return "cerebras", api_key
        # Generic sk- key: try deepseek
        if settings.deepseek_api_key:
            return "deepseek", api_key
        return "anthropic", api_key  # fallback assumption

    # No key provided, use .env default
    return _get_provider_and_key()


def _get_base_url(provider: str) -> str:
    if provider == "ollama":
        return settings.ollama_base_url
    if provider == "google":
        return "https://generativelanguage.googleapis.com/v1beta/openai"
    if provider == "cerebras":
        return "https://api.cerebras.ai/v1"
    if provider == "groq":
        return "https://api.groq.com/openai/v1"
    if provider == "deepseek":
        return settings.deepseek_base_url or "https://api.deepseek.com"
    return "https://api.openai.com/v1"


# ── Anthropic (Claude) ────────────────────────────────────────────


async def _call_anthropic(
    messages: list[dict], model: str, api_key: str,
    temperature: float, max_tokens: int,
) -> str:
    system_msg, chat_messages = _split_system(messages)
    client = anthropic.AsyncAnthropic(api_key=api_key)

    response = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system_msg,
        messages=chat_messages,
    )
    return response.content[0].text


async def _stream_anthropic(
    messages: list[dict], model: str, api_key: str,
    temperature: float, max_tokens: int,
) -> AsyncGenerator[str, None]:
    system_msg, chat_messages = _split_system(messages)
    client = anthropic.AsyncAnthropic(api_key=api_key)

    async with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system_msg,
        messages=chat_messages,
    ) as stream:
        async for text in stream.text_stream:
            yield text


async def call_anthropic_web_search(
    system: str,
    user_content: str,
    api_key: str,
    model: str = "claude-haiku-4-5-20251001",
    max_searches: int = 5,
    max_tokens: int = 8192,
    temperature: float = 0.5,
) -> tuple[str, list[str]]:
    """Call Claude with the server-side web_search tool enabled.

    Claude runs searches on Anthropic's infrastructure and grounds its answer
    in live results. Returns (report_text, cited_source_urls).
    """
    client = anthropic.AsyncAnthropic(api_key=api_key)

    response = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=[{"role": "user", "content": user_content}],
        tools=[{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": max_searches,
        }],
    )

    # Collect the text blocks and any cited source URLs
    text_parts: list[str] = []
    sources: list[str] = []
    for block in response.content:
        if block.type == "text":
            text_parts.append(block.text)
            for citation in getattr(block, "citations", None) or []:
                url = getattr(citation, "url", None)
                if url and url not in sources:
                    sources.append(url)

    return "".join(text_parts), sources


# ── OpenAI-compatible (Groq, DeepSeek) ────────────────────────────


async def _call_openai_compat(
    messages: list[dict], model: str, api_key: str, base_url: str,
    temperature: float, max_tokens: int,
) -> str:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": messages,  # OpenAI format accepts system role directly
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(f"{base_url}/chat/completions", json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


async def _stream_openai_compat(
    messages: list[dict], model: str, api_key: str, base_url: str,
    temperature: float, max_tokens: int,
) -> AsyncGenerator[str, None]:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }

    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream("POST", f"{base_url}/chat/completions", json=payload, headers=headers) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: ") and line != "data: [DONE]":
                    import json
                    try:
                        chunk = json.loads(line[6:])
                        delta = chunk["choices"][0].get("delta", {})
                        if delta.get("content"):
                            yield delta["content"]
                    except (json.JSONDecodeError, KeyError, IndexError):
                        pass


# ── Helpers ────────────────────────────────────────────────────────


def _split_system(messages: list[dict]) -> tuple[str, list[dict]]:
    """Split system message from chat messages (for Anthropic API format)."""
    system_msg = ""
    chat_messages = []
    for msg in messages:
        if msg["role"] == "system":
            system_msg = msg["content"]
        else:
            chat_messages.append({"role": msg["role"], "content": msg["content"]})
    return system_msg, chat_messages
