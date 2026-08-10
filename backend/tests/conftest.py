"""Shared test configuration.

Tests must not inherit the developer's .env feature flags: DA_DECOMPOSED=true
in a dev .env routed the pipeline-flow tests into the decomposed DA path,
whose LLM calls bypass the per-module mocks and hit real providers (measured:
the suite hung on 900s Ollama timeouts). Default every test to the monolithic
path; the integration tests opt in explicitly via monkeypatch.
"""

import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def _isolate_feature_flags(monkeypatch):
    monkeypatch.setattr(settings, "da_decomposed", False)
