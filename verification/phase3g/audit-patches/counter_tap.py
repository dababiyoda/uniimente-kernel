"""A pytest plugin that OBSERVES counter increments and changes nothing.

`reset()` clears counters in place many times per suite, so reading `C` at the
end reports almost nothing. This wraps `Counters.incr` to accumulate a
parallel total that no test resets. It adds no branch to the runtime and
alters no value the runtime reads: the wrapper calls the original and then
records. If it changed behaviour the suite totals would move, which is itself
checked by the parity gates.
"""
import json
import os

from substrate import v5

TOTALS = {}
_orig = v5.Counters.incr


def _tapped(self, name, n=1):
    _orig(self, name, n)
    TOTALS[name] = TOTALS.get(name, 0) + n


v5.Counters.incr = _tapped


def pytest_sessionfinish(session, exitstatus):
    path = os.environ.get("COUNTER_TAP_OUT")
    if not path:
        return
    with open(path, "w") as fh:
        json.dump({k: v for k, v in sorted(TOTALS.items()) if v},
                  fh, indent=2, sort_keys=True)
