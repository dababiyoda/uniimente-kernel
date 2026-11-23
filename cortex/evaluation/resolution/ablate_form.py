"""Ablation (d): NEW with the FORM branch suppressed. A FORM resolution is consumed as a silent wait, as though the
dividend bought its numbers by holding formation back. FORM items must then lose Genesis, which shows NEW's
Genesis openings come through the unchanged path. Declared reporting code, written after the freeze.

    python ablate_form.py --tree TREE --suite FILE --out FILE   (FORM items only; v2 harness)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "v2"))
import harness_v2  # noqa: E402,F401  (applies the v2 instrument)
import harness as H  # noqa: E402

_ENTER = H._enter


def _enter(tree, ablate):
    _ENTER(tree, None)
    import greg.missions as missions
    from greg.cognition import resolution
    original = missions.MissionEngine._resolution_ask

    def suppressed(self, m, s, aid, receipt, now):
        r = resolution.read(receipt)
        if r is not None and r["kind"] == "FORM":
            return {"state": "WAITING", "blocker": m.blocker}
        return original(self, m, s, aid, receipt, now)
    missions.MissionEngine._resolution_ask = suppressed


H._enter = _enter

if __name__ == "__main__":
    args = sys.argv[1:]
    suite = Path(args[args.index("--suite") + 1])
    form = [i for i in json.loads(suite.read_text())["items"] if i["operator"] == "FORM"]
    only = ",".join(i["item_id"] for i in form)
    raise SystemExit(H.main([*args, "--policy", "standard", "--only", only]))
