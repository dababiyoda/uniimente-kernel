#!/usr/bin/env python3
"""POSITIVE CONTROL for the two regressed cases.

Neither assertion is rewritten and neither is weakened. Each keeps its exact
predicate; only the PLACE it reads is redirected from the legacy projection
`search_edge_terminals` to the canonical control channel
`search_edge_lifecycle[edge]["accepted_control"]`.

If the cases then pass under the 5G runtime, the fact they assert still
exists and only their reading location was stale. If they still fail, 5G
destroyed the fact and the assertions are valid invariants. The two answers
are incompatible, which is what makes this decisive.
"""
import os
import subprocess
import sys

T = "tests/unit/test_substrate_v5_single_flight_live_path.py"

EDITS = [
    # --- test_an_exact_proposal_replay_settles_only_once
    (
        '    commits = [x for x in o.search_edge_terminals.get(kids[0], {}).get(\n'
        '        "outcomes", []) if _kind(x) == "SearchCommitted"]\n',
        '    _ac = (o.search_edge_lifecycle.get(kids[0]) or {}).get("accepted_control")\n'
        '    commits = [x for x in ([_ac] if _ac is not None else [])\n'
        '               if _kind(x) == "SearchCommitted"]\n',
    ),
    (
        '    terminals = {k: list(v["outcomes"]) for k, v in o.search_edge_terminals.items()}\n',
        '    terminals = {k: [v["accepted_control"], v["accepted_outcome"]]\n'
        '                 for k, v in o.search_edge_lifecycle.items()}\n',
    ),
    (
        '    assert {k: list(v["outcomes"])\n'
        '            for k, v in o.search_edge_terminals.items()} == terminals, (\n'
        '        "replay produced additional terminal outcomes")\n',
        '    assert {k: [v["accepted_control"], v["accepted_outcome"]]\n'
        '            for k, v in o.search_edge_lifecycle.items()} == terminals, (\n'
        '        "replay produced additional terminal outcomes")\n',
    ),
    # --- test_two_competing_proposals_race_through_real_child_edges
    (
        '    win_outs = o.search_edge_terminals.get(win_edge, {}).get("outcomes", [])\n'
        '    lose_outs = o.search_edge_terminals.get(lose_edge, {}).get("outcomes", [])\n',
        '    _wc = (o.search_edge_lifecycle.get(win_edge) or {}).get("accepted_control")\n'
        '    _lc = (o.search_edge_lifecycle.get(lose_edge) or {}).get("accepted_control")\n'
        '    win_outs = [_wc] if _wc is not None else []\n'
        '    lose_outs = [_lc] if _lc is not None else []\n',
    ),
    (
        '    for eid, rec in o.search_edge_terminals.items():\n'
        '        if rec["from_unit"] != j.unit_id:\n'
        '            continue\n',
        '    for eid, rec in o.search_edge_lifecycle.items():\n'
        '        _emitted = rec.get("accepted_control")\n'
        '        if _emitted is None or _emitted.from_unit != j.unit_id:\n'
        '            continue\n',
    ),
]


def main():
    worktree = sys.argv[1]
    path = os.path.join(worktree, T)
    subprocess.run(["git", "checkout", "--", T], cwd=worktree, check=True)
    with open(path) as fh:
        src = fh.read()
    for old, new in EDITS:
        n = src.count(old)
        if n != 1:
            raise SystemExit("ANCHOR FAILURE: %d matches for:\n%s" % (n, old[:200]))
        src = src.replace(old, new, 1)
    with open(path, "w") as fh:
        fh.write(src)
    print("probe applied to", worktree)


if __name__ == "__main__":
    main()
