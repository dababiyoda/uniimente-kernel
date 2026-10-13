"""One Foundry number, complementary implementations from two lineages, one dispatch.

#31 serves (webserver) and builds (portal) owned pages; #34 attributes (attribution) and
ingests journeys (journeys); #50 routes territory (rabbit_hole) and journeys (journeys).
Every operation from both stays reachable through the bridge, the worker, linking,
workflows, teams and the MCP server; the primary module owns exercise, evidence and any
shared operation name.
"""
import pytest

from foundry.systems import SYSTEMS, module, module_for, modules, ops

PAIRED = {31: ("webserver", "portal"), 34: ("attribution", "journeys"), 50: ("rabbit_hole", "journeys")}


@pytest.mark.parametrize("system,names", sorted(PAIRED.items()))
def test_every_operation_of_both_lineages_is_reachable(system, names):
    assert SYSTEMS[system] == names
    assert module(system).__name__ == f"foundry.systems.{names[0]}"          # contract/evidence module
    assert [m.__name__.rsplit(".", 1)[1] for m in modules(system)] == list(names)
    for table in ("QUERY_OPS", "APPLY_OPS"):
        merged = ops(system, table)
        for mod in modules(system):
            for op in getattr(mod, table, None) or {}:
                assert op in merged
                assert module_for(system, table, op) in modules(system)


def test_a_shared_operation_name_is_served_by_the_primary_module():
    """Only #34 'report' is defined by both; attribution (the COMPLETE contract module) serves it."""
    shared = []
    for system in PAIRED:
        for table in ("QUERY_OPS", "APPLY_OPS"):
            seen = {}
            for mod in modules(system):
                for op in getattr(mod, table, None) or {}:
                    seen.setdefault(op, []).append(mod.__name__)
            shared += [(system, op) for op, owners in seen.items() if len(owners) > 1]
    assert shared == [(34, "report")]
    assert module_for(34, "QUERY_OPS", "report").__name__ == "foundry.systems.attribution"
    assert ops(34, "QUERY_OPS")["report"] is module(34).QUERY_OPS["report"]


def test_single_module_systems_and_unknown_ops_behave_as_before():
    assert modules(36) == [module(36)] and ops(36, "QUERY_OPS") == dict(module(36).QUERY_OPS)
    with pytest.raises(KeyError):
        module_for(31, "QUERY_OPS", "no_such_op")
    with pytest.raises(KeyError):
        module(26)
