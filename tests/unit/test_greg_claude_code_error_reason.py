"""error_* results from the Claude Code CLI carry their reason in ``errors`` and no ``result`` key.

Shape read from the installed CLI 2.1.300: subtype error_max_budget_usd / error_max_turns / error_during_execution
emit ``errors: [...]``; only subtype "success" carries ``result``. No real CLI or paid service is invoked.
"""
import json
import subprocess
from types import SimpleNamespace as NS

import pytest

from greg import builders, models


def _error_report(subtype, errors, cost):
    # key order as the CLI's result builder spreads it: common fields, then the variant, then type/duration/uuid
    return json.dumps({"duration_api_ms": 1200, "stop_reason": None, "session_id": "s-1", "total_cost_usd": cost,
                       "usage": {}, "modelUsage": {}, "permission_denials": [], "terminal_reason": "budget_exhausted",
                       "is_error": True, "num_turns": 1, "subtype": subtype, "errors": errors,
                       "type": "result", "duration_ms": 1300, "uuid": "u-1"})


CASES = [
    ("error_max_budget_usd", ["Reached maximum budget ($0.4)"], "Reached maximum budget"),
    ("error_max_budget_usd", ["Session cost is not a number (a usage or pricing fault upstream); refusing to "
                              "continue under --max-budget-usd 0.4"], "Session cost is not a number"),
    ("error_max_turns", ["Reached maximum number of turns (1)"], "maximum number of turns"),
    ("error_during_execution", ["boom: the session failed"], "boom"),
]


@pytest.mark.parametrize("subtype,errors,reason", CASES)
def test_route_keeps_the_cli_error_reason(subtype, errors, reason):
    out = NS(returncode=1, stdout=_error_report(subtype, errors, 0.4), stderr="")
    router = models.ModelRouter([models.ClaudeCodeRoute(binary="/bin/true", runner=lambda *a, **k: out)])
    with pytest.raises(models.RouteError):
        router.complete("s", "u", budget_usd=1.0)
    why = router.last["tried"][0]["why"]
    assert reason in why, why                      # fd45060: 'Claude Code reported an error (exit 1): None'
    assert router.last["cost_usd"] == pytest.approx(0.4)


@pytest.mark.parametrize("subtype,errors,reason", CASES)
def test_genesis_builder_keeps_the_cli_error_reason(subtype, errors, reason):
    request = {"function": "text.count_words", "description": "count the words", "examples": []}

    def runner(argv, **kw):
        return subprocess.CompletedProcess(argv, 1, _error_report(subtype, errors, 0.4), "")
    with pytest.raises(builders.BuildError) as info:
        builders.ClaudeCodeBuilder("/usr/bin/claude", max_budget_usd=0.4, runner=runner).build(request)
    assert info.value.cost_usd == 0.4
    assert reason in str(info.value), str(info.value)   # fd45060: '... (exit 1): None'; 2cf4bdc kept the text
