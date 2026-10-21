"""One Foundry number, complementary implementations from two lineages, one dispatch.

#31 serves (webserver) and builds (portal) owned pages; #34 attributes (attribution) and
ingests journeys (journeys); #50 routes territory (rabbit_hole) and journeys (journeys).
Every operation from both stays reachable through the bridge, the worker, linking,
workflows, teams and the MCP server; the canonical module owns exercise, evidence and any
shared operation name.

Written on #168 against its merged-ops registry (SYSTEMS tuples, ``ops``/``modules``); adapted
in the installed-body merge to the convergence line's one resolver (``SYSTEMS`` canonical name +
``ALTERNATES``, ``implementation_for``, qualified ``impl.op``), which the #169 rule makes canonical.
The properties are the same: every op of both lineages is reachable under the one number, a
shared name goes to the canonical module, unknown ops and systems are refused.
"""
import pytest

from foundry.systems import (ALTERNATES, SYSTEMS, OperationError, implementation_for, implementations, module,
                             operation)

PAIRED = {31: ("webserver", "portal"), 34: ("attribution", "journeys"), 50: ("rabbit_hole", "journeys")}
TABLES = ("QUERY_OPS", "APPLY_OPS")


@pytest.mark.parametrize("system,names", sorted(PAIRED.items()))
def test_every_operation_of_both_lineages_is_reachable(system, names):
    assert (SYSTEMS[system], *ALTERNATES[system]) == names == implementations(system)
    assert module(system).__name__ == f"foundry.systems.{names[0]}"          # contract/evidence module
    for name in names:
        mod = module(system, name)
        others = [module(system, n) for n in names if n != name]
        for table in TABLES:
            for op, fn in (getattr(mod, table, None) or {}).items():
                assert operation(system, table, f"{name}.{op}") is fn       # always reachable by qualified name
                if not any(op in (getattr(o, t, None) or {}) for o in others for t in TABLES):
                    assert implementation_for(system, op) == name           # a unique bare name finds its owner
                    assert operation(system, table, op) is fn


def test_a_shared_operation_name_is_served_by_the_canonical_module():
    """Only #34 'report' is defined by both; attribution (the COMPLETE contract module) serves it."""
    shared = []
    for system, names in PAIRED.items():
        for table in TABLES:
            seen = {}
            for name in names:
                for op in getattr(module(system, name), table, None) or {}:
                    seen.setdefault(op, []).append(name)
            shared += [(system, op) for op, owners in seen.items() if len(owners) > 1]
    assert shared == [(34, "report")]
    assert implementation_for(34, "report") == "attribution"
    assert operation(34, "QUERY_OPS", "report") is module(34).QUERY_OPS["report"]
    assert operation(34, "QUERY_OPS", "journeys.report") is module(34, "journeys").QUERY_OPS["report"]


def test_single_module_systems_and_unknown_ops_behave_as_before():
    assert implementations(36) == (SYSTEMS[36],) and 36 not in ALTERNATES
    assert operation(36, "QUERY_OPS", next(iter(module(36).QUERY_OPS))) is next(iter(module(36).QUERY_OPS.values()))
    with pytest.raises(KeyError):
        operation(31, "QUERY_OPS", "no_such_op")
    assert issubclass(OperationError, KeyError)
    with pytest.raises(KeyError):
        module(26)
