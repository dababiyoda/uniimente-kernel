"""pytest plugin: record every collected item's outcome for the acceptance harness.

Loaded only by ``python -m acceptance run`` (``-p acceptance._plugin``); writes ``{nodeid: {outcome, reason}}``
to the file named by ACCEPTANCE_OUTCOMES. A failure in setup or teardown is an error, a skip keeps its reason,
and a later phase can only make an item's outcome worse, never better.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

_SEVERITY = {"passed": 0, "skipped": 1, "failed": 2, "error": 3}
_results: dict[str, dict] = {}


def pytest_collection_modifyitems(items):
    for item in items:
        _results.setdefault(item.nodeid, {"outcome": "error", "reason": "collected but never reported"})


def pytest_runtest_logreport(report):
    if report.when == "call" or report.outcome != "passed":
        outcome = report.outcome
        if report.failed and report.when != "call":
            outcome = "error"
        reason = ""
        if report.skipped and isinstance(report.longrepr, tuple):
            reason = str(report.longrepr[2])
        elif report.failed:
            lines = (report.longreprtext or "").strip().splitlines()
            reason = lines[-1] if lines else "failed"
        prior = _results.get(report.nodeid)
        if prior and prior["reason"] != "collected but never reported" and \
                _SEVERITY[prior["outcome"]] >= _SEVERITY[outcome]:
            return
        _results[report.nodeid] = {"outcome": outcome, "reason": str(reason)[:400]}


def pytest_sessionfinish(session):
    target = os.environ.get("ACCEPTANCE_OUTCOMES")
    if target:
        Path(target).write_text(json.dumps(_results, indent=1, sort_keys=True))
