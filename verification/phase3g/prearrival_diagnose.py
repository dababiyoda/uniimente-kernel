#!/usr/bin/env python3
"""PA-0: reproduce the pre-arrival control condition against the REAL runtime.

No mirrored model. This imports substrate.v5, builds a real organ through the
repository's own fixtures, uses the repository's own test helpers to construct
a real authenticated edge, and drives the real delivery entry points.

The question: what does the runtime ACTUALLY do when a legitimate, correctly
authenticated parent control reaches a receiver that has not yet opened its
canonical node for that SearchKey?
"""
import json
import sys

sys.path.insert(0, "/home/user/uniimente-kernel")
sys.path.insert(0, "/home/user/uniimente-kernel/tests/unit")
sys.path.insert(0, "/home/user/uniimente-kernel/verification/phase3g")

import substrate.v5 as v5                                   # noqa: E402
from substrate.v5 import C, reset                           # noqa: E402
from test_substrate_v5_direction_classification import (    # noqa: E402
    _pair, _open,
)

OUT = {}


def snap(unit, key, edge):
    o = unit._organ
    lc = (o.search_edge_lifecycle.get(edge) or {})
    node = unit.canonical_searches.get(key)
    return {
        "node_exists": node is not None,
        "node_adopted_parent_edge": node["adopted_parent_edge"] if node else None,
        "lifecycle_record_exists": bool(lc),
        "accepted_control": lc.get("accepted_control").kind if lc.get("accepted_control") else None,
        "accepted_outcome": lc.get("accepted_outcome").kind if lc.get("accepted_outcome") else None,
        "projection_entry": edge in o.search_edge_terminals,
        "probe_exists": edge in o.search_edge_probes,
        "edge_terminal_status": (o.search_edges.get(edge) or {}).get("terminal_status"),
    }


def counters(*names):
    return {n: C[n] for n in names}


WATCH = ("ORPHANED_SEARCH_EDGES", "UNAUTHENTICATED_TERMINAL_CONTROLS",
         "UNAUTHENTICATED_SEARCH_DELIVERIES", "UNKNOWN_EDGE_TERMINAL_EMISSIONS",
         "UNAUTHENTICATED_TERMINAL_EMISSIONS", "UNCLASSIFIABLE_TERMINAL_RECORDINGS",
         "SEARCH_CONTROLS_RECORDED", "TERMINAL_ECHOS_SENT",
         "PREMATURE_TERMINATION_SIGNALS", "DUPLICATE_TERMINAL_RESOLUTIONS",
         "CLOSED_CHILD_EDGES", "TERMINALS_WITH_UNRECONCILED_CHILDREN")


# ==================================================================
# CASE 1 — control arrives BEFORE the receiver has any node for the key
# ==================================================================
o, parent, child, ctx, key, seed = _pair()
edge = "e/pa/before"
_open(o, parent, child, key, edge, allocation=6.0)      # sender-owned probe
reset()

OUT["case1_before_delivery"] = {
    "seed": seed, "parent": parent.unit_id, "child": child.unit_id,
    "state": snap(child, key, edge),
}

# The parent commands the edge it legitimately opened. The child has never
# seen a SearchNeed for this key, so it has no canonical node.
child.deliver_terminal(key, edge, "SearchCancelled", refund=6.0,
                       sender=parent.unit_id,
                       from_unit=parent.unit_id, to_unit=child.unit_id)

OUT["case1_after_control"] = {
    "counters": counters(*WATCH),
    "state": snap(child, key, edge),
}

# Now the search legitimately arrives and the node opens.
child.deliver_search(key, edge, 6.0, sender=parent.unit_id)

OUT["case1_after_late_search"] = {
    "counters": counters(*WATCH),
    "state": snap(child, key, edge),
}

# Does the control get another chance once the node exists?
child.deliver_terminal(key, edge, "SearchCancelled", refund=6.0,
                       sender=parent.unit_id,
                       from_unit=parent.unit_id, to_unit=child.unit_id)
OUT["case1_after_control_replayed_post_adoption"] = {
    "counters": counters(*WATCH),
    "state": snap(child, key, edge),
}


# ==================================================================
# CASE 2 — control arrives and the node NEVER opens
# ==================================================================
o2, p2, c2, ctx2, key2, seed2 = _pair()
edge2 = "e/pa/never"
_open(o2, p2, c2, key2, edge2, allocation=6.0)
reset()
c2.deliver_terminal(key2, edge2, "SearchCancelled", refund=6.0,
                    sender=p2.unit_id,
                    from_unit=p2.unit_id, to_unit=c2.unit_id)
OUT["case2_never_adopted"] = {
    "counters": counters(*WATCH),
    "state": snap(c2, key2, edge2),
    "parent_edge_terminal_status": (o2.search_edges.get(edge2) or {}).get("terminal_status"),
}


# ==================================================================
# CASE 3 — FORGED sender, same pre-arrival window
# The gate must refuse this whether or not a node exists.
# ==================================================================
o3, p3, c3, ctx3, key3, seed3 = _pair()
edge3 = "e/pa/forged"
_open(o3, p3, c3, key3, edge3, allocation=6.0)
stranger = next(u for u in o3.units.values()
                if u.unit_id not in (v5.ENV, v5.SINK, p3.unit_id, c3.unit_id))
reset()
c3.deliver_terminal(key3, edge3, "SearchCancelled", refund=6.0,
                    sender=stranger.unit_id,
                    from_unit=stranger.unit_id, to_unit=c3.unit_id)
OUT["case3_forged_sender_prearrival"] = {
    "counters": counters(*WATCH),
    "state": snap(c3, key3, edge3),
}


print(json.dumps(OUT, indent=2, sort_keys=True))
