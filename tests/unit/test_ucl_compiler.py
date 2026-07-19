"""Layer 1 tests: UCL parser + compiler (Executable Constitution)."""
import os
import pytest

from compiler.ucl_parser import parse, UCLSyntaxError
from compiler.ucl_compiler import compile_constitution, CompilationError, POLICY_DIMENSIONS

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------- parser ----------------

def test_parser_reads_all_constitution_files():
    for f in ("constitution.ucl", "sovereignty.ucl", "participant-rights.ucl",
              "amendment-policy.ucl", "shutdown-policy.ucl"):
        blocks = parse(open(os.path.join(ROOT, "constitution", f)).read())
        assert blocks, f"{f} produced no blocks"


def test_parser_handles_labels_nested_lists_and_comments():
    blocks = parse('''
// comment
widget "labeled" {
    field = "value"
    count = 3
    ratio = 1.5
    flag = true
    nothing = null
    items = ["a", "b",
             "c"]
    inner { x = 1 }
    inner { x = 2 }
}
''')
    w = blocks[0]
    assert w.type == "widget" and w.label == "labeled"
    assert w.fields["count"] == 3 and w.fields["ratio"] == 1.5
    assert w.fields["flag"] is True and w.fields["nothing"] is None
    assert w.fields["items"] == ["a", "b", "c"]
    assert len(w.children("inner")) == 2


def test_parser_fails_closed_on_malformed_input():
    with pytest.raises(UCLSyntaxError):
        parse('block "x" { field = "unclosed')
    with pytest.raises(UCLSyntaxError):
        parse('block { field = [1, 2 }')
    with pytest.raises(UCLSyntaxError):
        parse('block { = 3 }')


def test_parser_no_side_effects():
    # UCL is declarative: parsing the same text twice yields equal trees, no I/O.
    t = 'a { b = "c" }'
    assert str(parse(t)) == str(parse(t))


# ---------------- compiler ----------------

@pytest.fixture(scope="module")
def compiled():
    return compile_constitution(ROOT)


def test_compilation_is_deterministic(compiled):
    again = compile_constitution(ROOT)
    assert compiled.constitution_hash == again.constitution_hash
    assert compiled.to_json() == again.to_json()


def test_constitution_hash_anchors(compiled):
    assert compiled.constitution_hash.startswith("sha256:")
    assert len(compiled.constitution_hash) == 7 + 64


def test_all_ten_policy_dimensions_are_named(compiled):
    assert POLICY_DIMENSIONS == ("principal", "action", "resource", "context", "legal_principal",
                                 "evidence", "budget", "consequence_class", "capability", "expiration")


def test_sovereignty_hierarchy_ranks(compiled):
    r = compiled.sovereignty_ranks
    assert r["law_safety_rights"] == 1
    assert r["alfonso_reserved_authority"] == 2
    assert r["constitution"] == 3
    assert r["individual_tasks"] == 10
    assert len(r) == 10


def test_uniimente_is_never_a_legal_principal(compiled):
    assert "UNIIMENTE" in compiled.prohibited_principals
    assert "UNIIMENTE" not in compiled.legal_principals
    assert "alfonso_lopez" in compiled.legal_principals


def test_absolute_prohibitions_compiled(compiled):
    prohibited = {m for m, req in compiled.reserved_matters.items() if req == []}
    assert {"unlawful_conduct", "physical_harm",
            "expansion_of_uniimentes_own_sovereignty"} <= prohibited


def test_non_delegable_matters_have_rules(compiled):
    rule_ids = {r.rule_id for r in compiled.rules}
    for matter in compiled.non_delegable:
        assert (f"prohibit:{matter}" in rule_ids) or (f"reserved:{matter}" in rule_ids), matter


def test_deny_by_default_is_first_law(compiled):
    assert compiled.rules[0].rule_id == "deny_by_default"
    assert compiled.rules[0].decision == "deny_always"


def test_relationship_tuples_no_self_grant(compiled):
    agent_never = [t["object"] for t in compiled.relationship_tuples
                   if t["grantee"] == "agent" and t["relation"] == "may_never"]
    assert "self_authorize" in agent_never
    assert "amend_constitution_or_charter" in agent_never
    cc_never = [t["object"] for t in compiled.relationship_tuples
                if t["grantee"] == "constitutional_controller" and t["relation"] == "may_never"]
    assert "block_or_delay_shutdown" in cc_never


def test_grant_contract_matches_doctrine(compiled):
    gc = compiled.grant_contract
    assert gc["child_grants"] == "strict_subset_of_parent"
    assert set(gc["initial_stage"]) == {"simulate", "shadow"}
    assert gc["commit_time_revalidation"] == "mandatory"
    assert gc["expiry"] == "mandatory"


def test_invariants_include_constitutional_guarantees(compiled):
    inv = " ".join(compiled.invariants)
    for needle in ("deny_by_default", "no_self_grant", "no_agent_amendment",
                   "commit_revalidation", "never_uniimente_principal"):
        assert needle in inv


def test_kill_conditions_present(compiled):
    assert "self_authorization" in compiled.kill_conditions
    assert "cathedral" in compiled.kill_conditions


def test_compiler_fails_closed_on_contradiction(tmp_path):
    # authority matrix ranks diverging from sovereignty hierarchy must refuse compilation
    import shutil, yaml
    shutil.copytree(os.path.join(ROOT, "constitution"), tmp_path / "constitution")
    shutil.copytree(os.path.join(ROOT, "authority"), tmp_path / "authority")
    matrix_path = tmp_path / "authority" / "authority-matrix.yaml"
    matrix = yaml.safe_load(matrix_path.read_text())
    matrix["ranks"][10] = "wrong_name"  # corrupt the rank mapping
    matrix_path.write_text(yaml.safe_dump(matrix))
    with pytest.raises(CompilationError):
        compile_constitution(str(tmp_path))
