"""Claude Code CLI with verbose on in the founder's settings: `-p --output-format json` prints a JSON array of every
message, with the result object last. The exit status is still 1 on is_error. Fakes only: no real CLI, no network."""
import json
import subprocess
from types import SimpleNamespace as NS

import pytest

from greg import builders, models


class Seen:
    name = "seen"
    provider = "test"

    def __init__(self):
        self.budgets = []

    def complete(self, system, user, *, budget_usd=None):
        self.budgets.append(budget_usd)
        return {"text": "other vendor", "cost_usd": 0.10, "served_model": "seen"}


def _array(returncode, **result):
    messages = [{"type": "system", "subtype": "init", "session_id": "s"},
                {"type": "assistant", "message": {"content": [{"type": "text", "text": str(result.get("result"))}]}},
                {"type": "result", **result}]
    return NS(returncode=returncode, stdout=json.dumps(messages) + "\n", stderr="")


def test_verbose_success_returns_the_cli_answer_and_books_its_cost():
    out = _array(0, subtype="success", is_error=False, result="the answer", stop_reason="end_turn",
                 total_cost_usd=0.30)
    answer = models.ClaudeCodeRoute(binary="/bin/true", runner=lambda *a, **k: out).complete("s", "u", budget_usd=1.0)
    assert answer["text"] == "the answer" and answer["cost_usd"] == pytest.approx(0.30)


def test_verbose_success_through_the_router_is_not_handed_to_the_next_vendor_unbooked():
    out = _array(0, subtype="success", is_error=False, result="the answer", stop_reason="end_turn",
                 total_cost_usd=0.30)
    seen = Seen()
    result = models.ModelRouter([models.ClaudeCodeRoute(binary="/bin/true", runner=lambda *a, **k: out), seen]) \
        .complete("s", "u", budget_usd=1.0)
    assert result["route"] == "claude-code" and seen.budgets == []
    assert result["cost_usd"] == pytest.approx(0.30)


def test_verbose_refusal_exit_one_is_final_and_billed():
    out = _array(1, subtype="success", is_error=True, stop_reason="refusal", total_cost_usd=0.0036,
                 result="API Error: Claude Code is unable to respond to this request")
    seen = Seen()
    router = models.ModelRouter([models.ClaudeCodeRoute(binary="/bin/true", runner=lambda *a, **k: out), seen])
    with pytest.raises(models.Refusal) as info:
        router.complete("s", "u", budget_usd=1.0)
    assert seen.budgets == [] and info.value.cost_usd == pytest.approx(0.0036)


def test_verbose_builder_error_carries_its_cost():
    request = {"function": "text.count_words", "description": "count the words", "examples": []}

    def runner(argv, **kw):
        out = _array(1, subtype="error_max_budget_usd", is_error=True, errors=["budget"], total_cost_usd=0.4)
        return subprocess.CompletedProcess(argv, out.returncode, out.stdout, "")
    with pytest.raises(builders.BuildError) as info:
        builders.ClaudeCodeBuilder("/usr/bin/claude", max_budget_usd=0.4, runner=runner).build(request)
    assert info.value.cost_usd == 0.4


def test_object_output_control_still_books():
    out = NS(returncode=0, stdout=json.dumps({"type": "result", "is_error": False, "result": "ok",
                                              "total_cost_usd": 0.30}), stderr="")
    answer = models.ClaudeCodeRoute(binary="/bin/true", runner=lambda *a, **k: out).complete("s", "u", budget_usd=1.0)
    assert answer["cost_usd"] == pytest.approx(0.30)
