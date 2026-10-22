"""A Claude Code CLI run whose cost is unknown must not be booked as $0 (claude-cli-parse #1).

The installed CLI halts under --max-budget-usd (which GREG always passes) when its session cost is NaN after a
billed API call: P0(cap) = cap !== undefined && !(cost < cap) is true for NaN, the result is subtype
error_max_budget_usd with is_error true and exit 1, and total_cost_usd is NaN, which JSON.stringify prints as null.
These fakes return exactly that. No real CLI, network or paid service is used.
Place at tests/unit/test_cli_unknown_cost_booking.py; run: python -m pytest tests/unit/test_cli_unknown_cost_booking.py -q -p no:cacheprovider
"""
import json
import subprocess

from greg import builders, models, workers

NAN_HALT = {"type": "result", "subtype": "error_max_budget_usd", "is_error": True, "num_turns": 1,
            "stop_reason": "end_turn", "total_cost_usd": None,
            "usage": {"input_tokens": 52000, "output_tokens": 3000},
            "errors": ["Session cost is not a number (a usage or pricing fault upstream); refusing to continue "
                       "under --max-budget-usd 0.50"]}


class CLI:
    """subprocess.run stand-in: records each --max-budget-usd and prints the NaN-cost halt."""

    def __init__(self):
        self.caps = []

    def __call__(self, argv, **kw):
        self.caps.append(float(argv[argv.index("--max-budget-usd") + 1]))
        return subprocess.CompletedProcess(argv, 1, json.dumps(NAN_HALT) + "\n", "")


class Seen:
    name, provider = "seen", "test"

    def __init__(self):
        self.budgets = []

    def complete(self, system, user, *, budget_usd=None):
        self.budgets.append(budget_usd)
        return {"text": "answer", "cost_usd": 0.10, "served_model": "seen"}


def test_the_router_bounds_the_next_route_by_an_unknown_cost_cli_run():
    cli, seen = CLI(), Seen()
    router = models.ModelRouter([models.ClaudeCodeRoute(binary="/bin/true", max_budget_usd=0.50, runner=cli), seen])
    result = router.complete("s", "u", budget_usd=1.0)
    assert cli.caps == [0.50]
    # workers.worker_spend, for the same evidence (a run with no reported spend): the whole cap, never zero
    assert workers.worker_spend(None, 0.50)["charge_usd"] == 0.50
    assert seen.budgets[0] <= 0.50 + 1e-9        # fd45060: 1.0 -- the CLI run was booked at $0
    assert result["cost_usd"] >= 0.50 + 0.10 - 1e-9


def test_genesis_never_commissions_cli_runs_whose_caps_exceed_the_signed_build_budget(tmp_path):
    from tests.greg_fixtures import Clock, drop, make_body, signed
    from tests.unit.test_greg_genesis_builder import FUNCTION, _mission, _run

    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _mission(data)))        # build_budget_usd 1.0
    cli = CLI()
    builder = builders.ClaudeCodeBuilder("/usr/bin/claude", max_budget_usd=1.0, runner=cli)
    body, states = _run(home, builder, ticks=2)
    assert cli.caps == [1.0] and not body.journal.replay("genesis.built")
    # the same deficit resolved again (as test_a_withheld_build_attempt_is_booked_against_the_signed_build_budget
    # does): the first run may have spent its whole 1.00 cap, so nothing of the signed 1.0 is known to remain
    body.genesis.resolve(mission=body.engine.book.missions["m:runbook"], function=FUNCTION, purpose="again",
                         now=Clock()())
    unbuilt = [e.payload.get("cost_usd") for e in body.journal.replay("genesis.unbuilt")]
    body.close()
    assert sum(cli.caps) <= 1.0 + 1e-9, (cli.caps, unbuilt)    # fd45060: [1.0, 1.0] -- 2.00 of caps on a 1.0 budget
