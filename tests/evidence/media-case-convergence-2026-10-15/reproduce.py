"""Reproduce: a paraphrase that changes its source's meaning passes GREG's evidence binding and the DALEOBANKS check."""
import json, sys, tempfile
from pathlib import Path
sys.path.insert(0, ".")
from greg import daleobanks_bridge as bridge
from greg.capabilities import BUILTINS, InvocationContext, SecretBroker
from greg.cognition.contracts import digest
from greg.cognition.cortex import reason, registry_view

SOURCE = "A pilot at two depots found the new routing method may reduce delays by 12%. It did not lower fuel costs."
CASES = {
    "faithful": ("A two-depot pilot found the routing method may cut delays by 12%.",
                 "A pilot at two depots found the new routing method may reduce delays by 12%"),
    "hedge dropped": ("The routing method cuts delays by 12%.", "the new routing method may reduce delays by 12%"),
    "negation removed": ("It lowered fuel costs.", "It did not lower fuel costs."),
    "scope widened": ("All depots saw delays fall by 12%.", "found the new routing method may reduce delays by 12%"),
    "direction reversed": ("The method increased delays by 12%.", "the new routing method may reduce delays by 12%"),
}
daleobanks = Path(sys.argv[1])
src = {"id": "s1", "text": SOURCE, "digest": digest(SOURCE), "provenance": "synthetic pilot summary",
       "quality": "secondary", "expires_at": "2050-01-01T00:00:00Z"}
for name, (claim, quote) in CASES.items():
    r = reason({"problem_id": f"repro-{name}", "operation": "bind_evidence",
                "data": {"claim": claim, "sources": [src],
                         "bindings": [{"source_id": "s1", "quote": quote, "relationship": "supports"}]}},
               registry=registry_view())
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "source.txt").write_text(SOURCE)
        (tmp / "draft.txt").write_text(claim)
        ctx = InvocationContext(workspace=tmp / "ws", read_roots=(tmp, daleobanks), secrets=SecretBroker(tmp / "s.json"),
                                manifest=BUILTINS["daleobanks.verify"][0], mission_id="m:repro", grant_id="g")
        v = bridge.verify({"daleobanks_root": str(daleobanks), "draft": str(tmp / "draft.txt"),
                           "source": str(tmp / "source.txt"), "python": sys.executable, "max_chars": 280}, ctx)
    print(f"{name:20} | evidence family: {r['abstention_state']:8} {r['output']} | daleobanks.verify: {v['verdict']} {v['findings']}")
