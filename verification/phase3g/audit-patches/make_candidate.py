#!/usr/bin/env python3
"""5K-T1c: build an exact candidate worktree.

Each candidate is a set of EXACT string replacements against the real
`substrate/v5.py` at head b6c9e0c. Nothing is mirrored: the worktree is the
repository, and the only thing that differs is the runtime edit under test.
Every replacement asserts its anchor is present exactly once, so a silent
no-op patch cannot masquerade as a measured result.

usage: make_candidate.py <label> <worktree> <factor>...
factors: instr | reader | writer | direction
"""
import os
import subprocess
import sys

V5 = "substrate/v5.py"

# ---------------------------------------------------------------- instr
# A pure counter. It changes no control flow: it records, at the three
# sites where the runtime asks the legacy projection a DECISION question,
# that the question was asked. Present in every candidate INCLUDING the
# baseline, so "0 legacy reads" is a measured negative with a measured
# positive control beside it.
INSTR = [
    (
        '    "TERMINALS_WITH_UNRECONCILED_CHILDREN",',
        '    "TERMINALS_WITH_UNRECONCILED_CHILDREN",\n'
        '    "LEGACY_TERMINAL_PROJECTION_DECISION_READS",',
    ),
    (
        "        if o is not None and edge_id in o.search_edge_terminals:\n"
        "            # Exact replay of an edge already answered",
        "        if o is not None:\n"
        '            C.incr("LEGACY_TERMINAL_PROJECTION_DECISION_READS")\n'
        "        if o is not None and edge_id in o.search_edge_terminals:\n"
        "            # Exact replay of an edge already answered",
    ),
    (
        '        for edge in sorted(node["children_outstanding"]):\n'
        "            rec = o.search_edge_terminals.get(edge)",
        '        for edge in sorted(node["children_outstanding"]):\n'
        '            C.incr("LEGACY_TERMINAL_PROJECTION_DECISION_READS")\n'
        "            rec = o.search_edge_terminals.get(edge)",
    ),
    (
        "        o = self._organ\n"
        "        if o is not None and edge_id in o.search_edge_terminals:\n"
        "            return\n"
        "        self.deliver_search(key, edge_id, 0.0)",
        "        o = self._organ\n"
        "        if o is not None:\n"
        '            C.incr("LEGACY_TERMINAL_PROJECTION_DECISION_READS")\n'
        "        if o is not None and edge_id in o.search_edge_terminals:\n"
        "            return\n"
        "        self.deliver_search(key, edge_id, 0.0)",
    ),
]

# --------------------------------------------------------------- reader
# MECHANISM 2: decision-authority migration. The three decision sites stop
# treating membership in the legacy projection as proof that an edge has
# been answered, and read the canonical lifecycle's ACCEPTED OUTCOME
# instead. A command is no longer mistaken for an answer.
READER = [
    (
        "        if o is not None:\n"
        '            C.incr("LEGACY_TERMINAL_PROJECTION_DECISION_READS")\n'
        "        if o is not None and edge_id in o.search_edge_terminals:\n"
        "            # Exact replay of an edge already answered",
        "        _lc = (o.search_edge_lifecycle.get(edge_id) or {}) if o is not None else {}\n"
        '        if _lc.get("accepted_outcome") is not None:\n'
        "            # Exact replay of an edge already answered",
    ),
    (
        "            first = o.search_edge_terminals[edge_id][\"outcomes\"][0]\n",
        '            first = _lc["accepted_outcome"]\n',
    ),
    (
        '        for edge in sorted(node["children_outstanding"]):\n'
        '            C.incr("LEGACY_TERMINAL_PROJECTION_DECISION_READS")\n'
        "            rec = o.search_edge_terminals.get(edge)\n"
        '            if rec is None or not rec["outcomes"]:\n'
        "                continue                    # no evidence: it stays open\n"
        '            if edge in node["child_confirmed"]:\n'
        "                continue\n"
        '            first = rec["outcomes"][0]\n',
        '        for edge in sorted(node["children_outstanding"]):\n'
        "            rec = o.search_edge_lifecycle.get(edge)\n"
        '            if rec is None or rec.get("accepted_outcome") is None:\n'
        "                continue                    # no evidence: it stays open\n"
        '            if edge in node["child_confirmed"]:\n'
        "                continue\n"
        '            first = rec["accepted_outcome"]\n',
    ),
    (
        "        o = self._organ\n"
        "        if o is not None:\n"
        '            C.incr("LEGACY_TERMINAL_PROJECTION_DECISION_READS")\n'
        "        if o is not None and edge_id in o.search_edge_terminals:\n"
        "            return\n"
        "        self.deliver_search(key, edge_id, 0.0)",
        "        o = self._organ\n"
        "        _lc = (o.search_edge_lifecycle.get(edge_id) or {}) if o is not None else {}\n"
        '        if _lc.get("accepted_outcome") is not None:\n'
        "            return\n"
        "        self.deliver_search(key, edge_id, 0.0)",
    ),
]

# --------------------------------------------------------------- writer
# MECHANISM 1: writer cleanup. The CONTROL channel stops writing the legacy
# projection, so `search_edge_terminals` holds accepted OUTCOMES and nothing
# else -- which is what its own readers always assumed it meant.
WRITER = [
    (
        "        o.search_edge_terminals.setdefault(t.edge_id, {\n"
        '            "from_unit": t.from_unit, "to_unit": t.to_unit,\n'
        '            "search_key": t.search_key, "outcomes": []})["outcomes"].append(t)\n'
        '        C.incr("SEARCH_CONTROLS_RECORDED")',
        '        C.incr("SEARCH_CONTROLS_RECORDED")',
    ),
]

# ------------------------------------------------------------ direction
# MECHANISM 3: author-direction classification. `SearchNeedClosed` belongs to
# both kind sets, so kind alone cannot say whether a message is a command or
# an answer. The edge's own probe record can: the unit that OPENED the edge
# commands it, the unit it was opened TO answers it. Classification reads the
# message's AUTHOR (`from_unit`), never the unit that happens to record it.
DIRECTION = [
    (
        "        if t.kind in PARENT_CONTROL_KINDS:\n"
        "            return self._record_control(t)\n"
        "        return self._record_outcome(t)\n"
        "\n"
        "    def _may_emit",
        "        o = self._organ\n"
        "        rec = o.search_edge_probes.get(t.edge_id) if o is not None else None\n"
        "        if rec is not None:\n"
        '            if t.from_unit == rec["to_unit"]:\n'
        "                return self._record_outcome(t)\n"
        '            if t.from_unit == rec["from_unit"]:\n'
        "                return self._record_control(t)\n"
        "        if t.kind in PARENT_CONTROL_KINDS:\n"
        "            return self._record_control(t)\n"
        "        return self._record_outcome(t)\n"
        "\n"
        "    def _may_emit",
    ),
]

FACTORS = {"instr": INSTR, "reader": READER,
           "writer": WRITER, "direction": DIRECTION}


def main():
    label, worktree, factors = sys.argv[1], sys.argv[2], sys.argv[3:]
    subprocess.run(["git", "checkout", "--", V5], cwd=worktree, check=True)
    path = os.path.join(worktree, V5)
    with open(path) as fh:
        src = fh.read()

    for factor in factors:
        for old, new in FACTORS[factor]:
            n = src.count(old)
            if n != 1:
                raise SystemExit(
                    "ANCHOR FAILURE in %s/%s: %d matches for:\n%s"
                    % (label, factor, n, old[:200]))
            src = src.replace(old, new, 1)

    with open(path, "w") as fh:
        fh.write(src)
    subprocess.run([sys.executable, "-c", "import ast,sys;ast.parse(open(sys.argv[1]).read())",
                    path], check=True)
    print("built", label, "factors=", factors)


if __name__ == "__main__":
    main()
