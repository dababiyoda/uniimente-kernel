#!/usr/bin/env python3
"""Non-reconstructability by AMBIGUITY SET, not by counting populated fields.

PR #59 reported "3 information bits", which was a count of non-None fields, not
an information measure. The honest test is: how many materially different
predecessor graphs are compatible with the motif? If many, the motif cannot
identify the predecessor.

Also measures CUMULATIVE leakage: whether motifs accumulated across episodes
narrow the ambiguity set toward one graph.
"""
from __future__ import annotations
import itertools, json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from substrate.causal import CausalMotif, certificate_for, signature_from_failure

ROLES = ("ingest", "decide", "emit")
CAPS = ("a", "b", "c", "d")
TOPOS = ("pipeline", "fan_out_vote", "supervised_pair")
VERIFY = ("readback", "dual_read", "checksum_quorum")
ALLOC = ("static", "elastic")

def universe():
    """All graphs an observer might consider. Deliberately enumerable."""
    out = []
    for caps in itertools.product(CAPS, repeat=3):
        for topo in TOPOS:
            for v in VERIFY:
                for al in ALLOC:
                    out.append({"capabilities": [f"{r}.{c}" for r, c in zip(ROLES, caps)],
                                "control_topology": topo, "verification": v,
                                "resource_allocation": al})
    return out

def compatible(graph, motif):
    role_counts = {}
    for cap in graph["capabilities"]:
        r = cap.split(".")[0]; role_counts[r] = role_counts.get(r, 0) + 1
    return motif.matches_local(
        role=motif.role,
        upstream_count=1 if graph["control_topology"] == "pipeline" else 2,
        redundancy=max(0, role_counts.get(motif.role, 0) - 1),
        verification_class=("single_read" if graph["verification"] in ("readback", "single_read")
                            else "redundant_read"),
        shares_resource=graph["resource_allocation"] == "static")

def main():
    U = universe()
    pred = {"capabilities": ["ingest.a", "decide.a", "emit.a"],
            "control_topology": "pipeline", "verification": "readback",
            "resource_allocation": "static"}
    sig = signature_from_failure(topology=pred, failed_role="emit")
    cert = certificate_for(sig, scope="fn")
    motif = cert.prohibited_motifs[0]

    single = [g for g in U if compatible(g, motif)]
    # Cumulative: three episodes, three different failed roles.
    motifs = [certificate_for(signature_from_failure(topology=pred, failed_role=r),
                              scope="fn").prohibited_motifs[0] for r in ROLES]
    cumulative = [g for g in U if all(compatible(g, m) for m in motifs)]

    res = {
      "universe_size": len(U),
      "single_motif": {"compatible_predecessor_graphs": len(single),
                       "exact_predecessor_uniquely_identifiable": len(single) == 1,
                       "threshold": 16, "meets_threshold": len(single) >= 16},
      "cumulative_three_motifs": {
          "compatible_predecessor_graphs": len(cumulative),
          "exact_predecessor_uniquely_identifiable": len(cumulative) == 1,
          "meets_threshold": len(cumulative) >= 16},
      "note": ("Ambiguity-set measure replaces the earlier 'information_bits' "
               "count of populated fields, which was not an information measure."),
    }
    pathlib.Path(__file__).parent.joinpath("MOTIF_AMBIGUITY.json").write_text(
        json.dumps(res, indent=2) + "\n")
    print(json.dumps(res, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
