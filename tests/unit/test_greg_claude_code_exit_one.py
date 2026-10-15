"""The Claude Code CLI exits 1 on every is_error result and still prints it (second review of PR #184, 12 and 13).

Observed by the reviewers with the installed Claude Code 2.1.300: an API error, an exhausted --max-budget-usd and a
model refusal each exit 1 with the JSON result on stdout, carrying total_cost_usd, and a refusal carries
stop_reason "refusal" with no policy wording. The route and the Genesis builder read the exit status first, so:

- a billed failure was booked at $0, and the router handed the next route the whole budget again;
- a refusal was a generic failure, and the router asked the next vendor the same prompt.

These fakes return what the real CLI returns. No real CLI or paid service is invoked.
"""
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
        return {"text": "answer", "cost_usd": 0.10, "served_model": "seen"}


def _cli(returncode, **result):
    return NS(returncode=returncode, stdout=json.dumps(result), stderr="")


def test_a_billed_cli_error_that_exits_one_is_booked_before_the_next_route():
    out = _cli(1, is_error=True, result="API Error: 400 bad request", total_cost_usd=0.37, terminal_reason="api_error")
    seen = Seen()
    result = models.ModelRouter([models.ClaudeCodeRoute(binary="/bin/true", runner=lambda *a, **k: out), seen]) \
        .complete("s", "u", budget_usd=1.0)
    assert seen.budgets == [pytest.approx(0.63)] and result["cost_usd"] == pytest.approx(0.47)


def test_a_cli_refusal_that_exits_one_is_final_billed_and_never_shopped():
    out = _cli(1, is_error=True, stop_reason="refusal", total_cost_usd=0.0036,
               result="API Error: the model's safeguards flagged this message")
    seen = Seen()
    router = models.ModelRouter([models.ClaudeCodeRoute(binary="/bin/true", runner=lambda *a, **k: out), seen])
    with pytest.raises(models.Refusal) as info:
        router.complete("s", "u", budget_usd=1.0)
    assert info.value.kind == models.SAFETY_REFUSAL and info.value.cost_usd == pytest.approx(0.0036)
    assert seen.budgets == []                                  # the next vendor is never asked the same prompt
    assert router.last["cost_usd"] == pytest.approx(0.0036)


def test_an_exit_without_a_report_is_still_a_plain_failure():
    out = NS(returncode=2, stdout="", stderr="claude: unknown option")
    with pytest.raises(models.RouteError) as info:
        models.ClaudeCodeRoute(binary="/bin/true", runner=lambda *a, **k: out).complete("s", "u", budget_usd=1.0)
    assert not isinstance(info.value, models.Refusal) and info.value.kind == models.UNKNOWN
    assert info.value.cost_usd is None


def test_the_genesis_builder_books_a_billed_cli_error_that_exits_one():
    request = {"function": "text.count_words", "description": "count the words", "examples": []}

    def runner(argv, **kw):
        return subprocess.CompletedProcess(argv, 1, json.dumps({"is_error": True, "subtype": "error_max_budget_usd",
                                                                "result": "budget exceeded", "total_cost_usd": 0.4}), "")
    with pytest.raises(builders.BuildError) as info:
        builders.ClaudeCodeBuilder("/usr/bin/claude", max_budget_usd=0.4, runner=runner).build(request)
    assert info.value.cost_usd == 0.4 and "exit 1" in str(info.value)
