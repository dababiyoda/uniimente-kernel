"""The construction branch of settlement (not exercised by any test the builder ran): a founder rejection of a
construction's verified answer."""
import json, sys, tempfile, os
from pathlib import Path
from greg.cognition import compiler, settlement
from greg import corrections
from tests.greg_fixtures import signed, make_body, Clock
from tests.unit.test_greg_construction_settlement import answered_portfolio, construction_id
from tests.unit.test_greg_recombine import ticks
d = Path(tempfile.mkdtemp(prefix="rc-", dir=os.environ.get("RC_TMP", "/tmp")))
body, clock = answered_portfolio(d)
try:
    j, cid = body.journal, construction_id(body)
    def show(n, v): print(f"{n}: {json.dumps(v, default=str)}", flush=True)
    show("counts0", {k: list(v) for k, v in compiler._settled_counts(j).items()})
    [closure] = [e for e in j.replay("mission.achieved")]
    # the fixture's founder key lives in the body home; sign with it
    import tests.greg_fixtures as fx
    home = body.layout.home
    key = None
    for name in ("founder.key", "founder_key.pem"):
        pass
    show("closure evidence n", len(closure.payload["evidence"]))
    # write the critique row as the tribunal would after a signed command (the signing key of answered_portfolio is not returned)
    j.record("critique.recorded", {"critique_id": "crit-probe", "target_event_id": closure.event_id, "verdict": "reject",
                                   "evidence_type": "founder_judgment", "text": "wrong portfolio"}, key="crit-probe")
    ticks(body, clock, 2)
    show("causes", [(e.payload["class"], e.payload["root"]["check_id"]) for e in j.replay("evidence.invalidated")])
    show("counts after the rejection", {k: list(v) for k, v in compiler._settled_counts(j).items()})
    show("construction outcomes", [(o["method"] == cid, o["correct"]) for o in settlement.measured_outcomes(j)])
    show("settled rows", [(e.payload.get("invalidated"), (e.payload.get("reason") or "")[:50]) for e in j.replay("cognition.settled")])
    try:
        show("awaiting_realization", [{k: r.get(k) for k in ("mission_id", "check_id", "method")} for r in settlement.awaiting_realization(j)])
    except Exception as exc:
        show("awaiting_realization", f"{type(exc).__name__}: {exc}")
finally:
    body.__exit__(None, None, None)
