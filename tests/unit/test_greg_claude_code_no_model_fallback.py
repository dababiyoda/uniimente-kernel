"""The Claude Code CLI must not re-run a refused prompt on another model (third review of PR #184; pre-existing).

Read from the installed Claude Code 2.1.300 bundle, not run: fj(){return!a.CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK&&!kG()}
and kG(){return a.CLAUDE_CODE_NO_MODEL_FALLBACK===!0}. On a fallback_request with no dialog host (-p) the main loop keeps
"retry_fallback", switches mainLoopModel to the fallback model and re-runs the turn; the -p report is then a success, so
the route's stop_reason == "refusal" check never fires. Fakes only: no real CLI, network or paid service.
"""
import json
import os
from types import SimpleNamespace as NS

import pytest

from greg import models

OFF = ("CLAUDE_CODE_NO_MODEL_FALLBACK", "CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK")
OK = {"type": "result", "subtype": "success", "is_error": False, "stop_reason": "end_turn", "result": "ok",
      "total_cost_usd": 0.01}


def _fallback_off(env):
    return any(str(env.get(k, "")).strip().lower() in ("1", "true", "yes", "on") for k in OFF)


class Never:
    name = provider = "never"

    def complete(self, system, user, *, budget_usd=None):
        raise AssertionError("the next route must never be asked")


@pytest.fixture
def clean_env(monkeypatch):
    for key in OFF:
        monkeypatch.delenv(key, raising=False)


def test_the_cli_run_directly_has_its_model_fallback_off(clean_env):
    seen = {}

    def runner(argv, **kw):
        seen["env"] = kw.get("env") if kw.get("env") is not None else dict(os.environ)   # no env= inherits ours
        return NS(returncode=0, stdout=json.dumps(OK), stderr="")
    models.ClaudeCodeRoute(binary="/bin/true", runner=runner).complete("s", "u", budget_usd=1.0)
    assert _fallback_off(seen["env"]), "the CLI may re-run a refusal on another model"


def test_the_cli_behind_the_relay_door_has_its_model_fallback_off(clean_env, monkeypatch):
    import foundry.systems.relay_door as relay_door

    class Door:
        def __init__(self, relay, identity):
            self.fd = 0

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False
    monkeypatch.setattr(models, "_namespace", lambda scratch, readonly=(): [])
    monkeypatch.setattr(models, "_scoped_relay", lambda relay, identity, host: relay)
    monkeypatch.setattr(relay_door, "Door", Door)
    monkeypatch.setattr(relay_door, "door_argv", lambda python, fd, argv: list(argv))
    seen = {}

    def runner(argv, **kw):
        seen["env"] = kw["env"]
        return NS(returncode=0, stdout=json.dumps(OK), stderr="")
    models.ClaudeCodeRoute(binary="/bin/true", runner=runner, egress=object()).complete("s", "u", budget_usd=1.0)
    assert _fallback_off(seen["env"]), "the confined CLI may re-run a refusal on another model"


def test_an_answer_the_cli_reports_another_model_wrote_is_never_the_selected_models(clean_env):
    # What -p prints after the CLI's refusal fallback: a success, billed for the refused attempt and the re-run.
    report = {**OK, "result": "written by the fallback model", "total_cost_usd": 0.21,
              "modelUsage": {"claude-fable-5-1": {"inputTokens": 900, "outputTokens": 0, "costUSD": 0.01},
                             "claude-opus-4-8": {"inputTokens": 900, "outputTokens": 700, "costUSD": 0.20}}}
    route = models.ClaudeCodeRoute(binary="/bin/true", model="claude-fable-5-1",
                                   runner=lambda *a, **k: NS(returncode=0, stdout=json.dumps(report), stderr=""))
    router = models.ModelRouter([route, Never()])
    try:
        result = router.complete("s", "u", budget_usd=1.0)
    except (models.ModelSubstitution, models.Refusal) as exc:
        assert exc.cost_usd == pytest.approx(0.21)              # withheld or declined, but booked
    else:
        assert result["substituted"] is True or result["served_model"] != "claude-fable-5-1", result
