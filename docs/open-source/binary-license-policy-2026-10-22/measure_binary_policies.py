"""Re-run the binary-license policy measurement on a body: every executable in /usr/bin, assessed by GREG's
DEP-5 reader (greg.licensing.system_binary), tallied under each candidate policy. Read-only; prints JSON.
Usage: PYTHONPATH=. python docs/open-source/binary-license-policy-2026-10-22/measure_binary_policies.py"""
import collections
import json
import os

from greg import genesis, licensing


class _Manifest:
    def __init__(self, assessment):
        self.capability_id, self.provider = "acquired.x.y", "installed:/usr/bin/x"
        self.provenance = {"license_assessment": assessment}


def main():
    catalog = sorted({c.binary_name for f in genesis.CATALOG.values() if f.get("kind") != "package"
                      for c in f.get("candidates", ())})
    rows = []
    for name in sorted(os.listdir("/usr/bin")):
        path = os.path.join("/usr/bin", name)
        if not (os.path.isfile(path) and os.access(path, os.X_OK) and not os.path.islink(path)):
            continue
        a = licensing.system_binary(path)
        rows.append({"binary": name, "verdict": a["verdict"] if a else "UNDETERMINABLE",
                     "held_current": bool(a) and not licensing.attach_check(_Manifest(a), "P0")[0],
                     "held_p4c": not licensing.attach_check(_Manifest(a), "P4c")[0]})
    cleared = {"CLEARED", "CLEARED_WITH_OBLIGATIONS"}
    print(json.dumps({"binaries": len(rows), "verdicts": collections.Counter(r["verdict"] for r in rows),
                      "P0_current_hold_known_uncleared": sum(r["held_current"] for r in rows),
                      "P1_fail_closed": sum(r["verdict"] not in cleared for r in rows),
                      "P2_catalog_allowlist_then_fail_closed": sum(r["verdict"] not in cleared and r["binary"] not in catalog
                                                                   for r in rows),
                      "P4c_use_context_hold": sum(r["held_p4c"] for r in rows),
                      "catalog_p4c_held": sorted(r["binary"] for r in rows if r["binary"] in catalog and r["held_p4c"]),
                      "catalog": {r["binary"]: r["verdict"] for r in rows if r["binary"] in catalog}}, indent=1))


if __name__ == "__main__":
    main()
