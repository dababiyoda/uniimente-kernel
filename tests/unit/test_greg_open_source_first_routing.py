"""INTENT-20260930-open-source-first applied to the one GREG model router.

The founder's 2026-09-30 direction: normal AI routing must not select a paid provider
merely because an API key exists. Before this correction ``available_routes`` fell back
to ``["anthropic", "openai", "claude-code"]`` whenever no founder selection existed, so a
stored key or an installed Claude Code CLI silently turned on paid cognition.
"""
from types import SimpleNamespace as NS

import pytest

from greg import models, planner
from greg.body import Body, init_body


class EveryKey:
    """A credential store that would hand out a key for every paid provider."""
    def __init__(self):
        self.resolved = []

    def resolve(self, name, declared):
        self.resolved.append(name)
        return "sk-would-bill"


@pytest.fixture
def paid_routes_would_work(monkeypatch):
    """Every paid adapter would construct successfully; record any construction."""
    built = []

    def recorder(provider):
        def make(*args, **kwargs):
            built.append(provider)
            return NS(provider=provider, name=provider, complete=lambda *a, **k: {"text": "billed"})
        return make

    monkeypatch.setattr(models, "AnthropicRoute", recorder("anthropic"))
    monkeypatch.setattr(models, "OpenAIRoute", recorder("openai"))
    monkeypatch.setattr(models, "ClaudeCodeRoute", recorder("claude-code"))
    monkeypatch.setattr(models.shutil, "which", lambda name: "/usr/local/bin/" + name)   # Claude Code "installed"
    return built


@pytest.mark.parametrize("config", [None, {}, {"anthropic_model": "claude-opus-5"}])
def test_keys_and_an_installed_cli_select_no_route_without_a_founder_selection(paid_routes_would_work, config):
    secrets = EveryKey()
    routes, unavailable = models.available_routes(secrets, config=config)
    assert routes == [] and unavailable == {}
    assert paid_routes_would_work == [] and secrets.resolved == []   # no key was even read
    assert planner.default_transport(secrets, config=config) is None


def test_a_paid_route_is_used_only_when_the_founder_selection_names_it(paid_routes_would_work):
    secrets = EveryKey()
    routes, _ = models.available_routes(secrets, config={"order": ["openai"]})
    assert [r.provider for r in routes] == ["openai"] and paid_routes_would_work == ["openai"]
    assert secrets.resolved == ["openai_api_key"]                      # only the named route's handle


def test_default_order_names_no_paid_route():
    assert models.DEFAULT_ROUTE_ORDER == ()
    assert models.PAID_ROUTE_NAMES == {"anthropic", "openai", "claude-code"}
    assert models.PAID_ROUTE_NAMES <= models.MODEL_ROUTE_NAMES


def test_a_new_body_without_a_local_model_has_no_model_cognition(tmp_path, paid_routes_would_work):
    home = tmp_path / "home"
    init_body(home, read_roots=[str(tmp_path)])
    body = Body(home).open()
    try:
        selected = models.effective_route_config(body.config.get("models"), body.journal)
    finally:
        body.close()
    assert "order" not in selected
    assert planner.default_transport(EveryKey(), config=selected) is None
    proposal = planner.propose("invent something no template covers", NS(), transport=None)
    assert proposal["status"] == "NO_ROUTE" and "paid route is used only" in proposal["enable_model_route"]
    assert paid_routes_would_work == []
