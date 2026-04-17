"""
Shared pytest fixtures for the Energy Compliance Hub test suite.

Isolation strategy
------------------
The app imports several external services at *module* load time:
  - databricks.sdk (WorkspaceClient in config.py)
  - mlflow (decorators in llm.py)
  - openai (OpenAI client in llm.py)

We patch those before the app module is imported so that every test
starts from a clean, fully mocked baseline.  The patches are applied
in conftest at session scope so they survive across the whole test run.
"""

import sys
import types
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ── 1. Stub out heavyweight / network-bound modules before any app import ─────

def _make_databricks_stub() -> types.ModuleType:
    """Return a minimal stub for databricks.sdk so config.py can be imported."""
    sdk = types.ModuleType("databricks.sdk")
    workspace_client = MagicMock()
    workspace_client.return_value.config.host = "https://fake-workspace.azuredatabricks.net"
    workspace_client.return_value.config.authenticate.return_value = {
        "Authorization": "Bearer fake-token"
    }
    sdk.WorkspaceClient = workspace_client

    # Make the package hierarchy importable:  databricks.sdk
    databricks_pkg = types.ModuleType("databricks")
    databricks_pkg.sdk = sdk
    sys.modules.setdefault("databricks", databricks_pkg)
    sys.modules.setdefault("databricks.sdk", sdk)
    return sdk


def _make_mlflow_stub() -> types.ModuleType:
    """Return a minimal stub for mlflow that turns decorators into no-ops."""
    mlflow_mod = types.ModuleType("mlflow")

    def _noop_trace(name: str | None = None, **kwargs):
        """@mlflow.trace — just pass the function through unchanged."""
        def decorator(fn):
            return fn
        return decorator

    mlflow_mod.trace = _noop_trace
    mlflow_mod.update_current_trace = MagicMock()
    sys.modules.setdefault("mlflow", mlflow_mod)
    return mlflow_mod


def _make_openai_stub() -> types.ModuleType:
    """Return a stub openai module.  Actual call-level mocking happens per test."""
    openai_mod = types.ModuleType("openai")

    class _FakeOpenAI:
        def __init__(self, *args, **kwargs):
            self.chat = MagicMock()

    openai_mod.OpenAI = _FakeOpenAI
    sys.modules.setdefault("openai", openai_mod)
    return openai_mod


# Apply all stubs once, before the app is ever imported.
_make_databricks_stub()
_make_mlflow_stub()
_make_openai_stub()


# ── 2. Import the app (only after stubs are in place) ─────────────────────────

# The app lives under   /tmp/energy-regulatory-intelligence/app/
# Add it to sys.path so that "from server.xxx import ..." resolves correctly.
import os

_APP_DIR = os.path.join(os.path.dirname(__file__), "..", "app")
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)

from app import app  # noqa: E402  (import after sys.path manipulation)


# ── 3. Shared LLM mock helper ─────────────────────────────────────────────────

def _make_llm_chat_mock(response_text: str = "Mocked LLM response."):
    """
    Build a MagicMock that mimics client.chat.completions.create().
    Returns a mock suitable for patching server.llm._get_openai_client.
    """
    choice = MagicMock()
    choice.message.content = response_text
    completion = MagicMock()
    completion.choices = [choice]

    client = MagicMock()
    client.chat.completions.create.return_value = completion
    return client


# ── 4. Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def mock_llm_client():
    """
    Session-scoped mock that patches server.llm._get_openai_client for the
    entire test run so no test ever reaches the Databricks LLM endpoint.
    """
    fake_client = _make_llm_chat_mock()
    with patch("server.llm._get_openai_client", return_value=fake_client):
        yield fake_client


@pytest.fixture(scope="session")
def client(mock_llm_client) -> Generator[TestClient, None, None]:
    """
    Synchronous TestClient wrapping the FastAPI app.

    Uses requests under the hood (no event loop required).  Suitable for all
    non-streaming GET/POST endpoints.
    """
    with TestClient(app, raise_server_exceptions=True) as tc:
        yield tc


@pytest.fixture(scope="session")
async def async_client(mock_llm_client):
    """
    Async HTTPX client for endpoints that require an asyncio event loop
    (SSE streaming endpoints, async route handlers).
    """
    import httpx

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac


@pytest.fixture()
def mock_impact_llm(monkeypatch):
    """
    Function-scoped mock for /api/impact-analysis — returns a realistic
    JSON structure so the endpoint's json.loads succeeds without calling
    the real LLM.
    """
    fake_payload = (
        '{"impact_summary": "Mocked impact summary.", '
        '"risk_level": "High", '
        '"affected_obligations": [], '
        '"new_obligations": [], '
        '"recommendations": ["Action 1", "Action 2"]}'
    )
    choice = MagicMock()
    choice.message.content = fake_payload
    completion = MagicMock()
    completion.choices = [choice]

    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = completion

    # Patch at the llm module level so routes.py picks it up
    with patch("server.llm._get_openai_client", return_value=fake_client):
        yield fake_client


@pytest.fixture()
def mock_extract_llm(monkeypatch):
    """
    Function-scoped mock for /api/extract-obligations — returns a valid
    JSON array so the endpoint's json.loads succeeds.
    """
    fake_payload = (
        '[{"obligation_name": "Test obligation", '
        '"regulatory_body": "AER", '
        '"category": "Market", '
        '"risk_rating": "High", '
        '"penalty_max_aud": 1000000, '
        '"frequency": "annual", '
        '"description": "A test obligation.", '
        '"key_requirements": "comply", '
        '"source_legislation": "Test Act s.1"}]'
    )
    choice = MagicMock()
    choice.message.content = fake_payload
    completion = MagicMock()
    completion.choices = [choice]

    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = completion

    with patch("server.llm._get_openai_client", return_value=fake_client):
        yield fake_client
