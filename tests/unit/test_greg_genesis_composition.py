"""Capability Genesis composes existing tools before it builds (acceptance C.G4, doctrine rung 2).

When no single installed tool behaves as a founder-signed contract says, Genesis tries two-stage pipelines,
``first {file} | second``: stage 1 is an ATTACHED capability the registry already holds that prints text, or an installed
text template; stage 2 is any discovery template. A pair is qualified exactly as a single tool is (public examples, then
held-out vectors through the serving adapter), pinned by both binaries' hashes and licences, and attached under the usual
rules. Before this, such a contract went to the builder.
"""
import shutil

import pytest

from greg import builders, genesis as genesis_mod
from greg.body import Body
from greg.capabilities import installed_binary
from tests.greg_fixtures import Clock, drop, make_body, mission, signed

needs_tools = pytest.mark.skipif(not all(installed_binary(b) for b in ("sort", "wc", "uniq")),
                                 reason="sort, wc and uniq are needed on this host")

DISTINCT = {
    "function": "text.distinct_line_count",
    "description": "The number of distinct lines in a text file; a final line without a newline counts.",
    "returns": "an integer", "output_field": "distinct",
    "examples": [{"input_text": "b\na\nb\n", "expected": 2}, {"input_text": "one\n", "expected": 1}],
    "held_out": [{"input_text": "", "expected": 0}, {"input_text": "x\nx\nx\n", "expected": 1},
                 {"input_text": "c\nb\na\nc\n", "expected": 3}, {"input_text": "p\nq", "expected": 2}],
    "build_budget_usd": 1.0}
SORTED_UNIQUE = {
    "function": "text.sorted_unique_lines",
    "description": "The distinct lines of a text file, in ascending byte order, as a list of strings.",
    "returns": "a list of strings", "output_field": "lines",
    "examples": [{"input_text": "b\na\nb\n", "expected": ["a", "b"]}, {"input_text": "z\n", "expected": ["z"]}],
    "held_out": [{"input_text": "", "expected": []}, {"input_text": "c\nc\n", "expected": ["c"]},
                 {"input_text": "y\nx\ny\nw\n", "expected": ["w", "x", "y"]}],
    "build_budget_usd": 1.0}
BUILT = "def run(text):\n    return len(set(text.splitlines()))\n"


def _spec(data, contract, mission_id, expected, *, auto_attach=True):
    doc = data / f"{mission_id.replace(':', '_')}.txt"
    doc.write_text("q\np\nq\np\n")
    check = {"check_id": "answered", "description": "the notes give the founder's expected answer",
             "sensor": {"function": contract["function"], "params": {"path": str(doc)}, "target": "fs:notes.txt"},
             "predicate": {"op": "equals", "field": contract["output_field"], "value": expected}}
    spec = mission(mission_id, checks=[check], strategies=[], ceiling="read_only", budget=1.0,
                   capabilities=["fs.read", f"acquired.{contract['function']}.*", f"built.{contract['function']}.*"],
                   auto_attach=auto_attach)
    spec["capability_specs"] = [dict(contract)]
    return spec


def _routes(body, deficit_function=None):
    opened = {e.payload["deficit_id"]: e.payload["function"] for e in body.journal.replay("deficit.opened")}
    return [(e.payload["route"], e.payload["result"]) for e in body.journal.replay("genesis.route")
            if deficit_function is None or opened.get(e.payload["deficit_id"]) == deficit_function]


def _tick(body, clock, n=4):
    states = []
    for _ in range(n):
        clock.advance(30)
        states.append(body.tick()["missions"])
    return states


def _state(states, mission_id):
    return [m["state"] for tick in states for m in tick if m["mission_id"] == mission_id]


@needs_tools
def test_a_contract_no_single_tool_answers_is_served_by_two_existing_tools_composed_and_nothing_is_built(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _spec(data, DISTINCT, "m:distinct", 2)))
    clock = Clock()
    builder = builders.StaticBuilder(BUILT, identity="would-build")
    body = Body(home, clock=clock, builder=builder).open()
    body.boot()
    states = _tick(body, clock)
    assert "ACHIEVED" in _state(states, "m:distinct")
    assert builder.calls == []
    routes = _routes(body)
    assert [r for r, _ in routes] == ["verified_detached", "installed_software"]
    assert routes[1][1] == "composed from existing tools: sort -u -- {file} | wc -l {file}"
    cid = "acquired.text.distinct_line_count.sort-wc"
    manifest = body.journal.replay("capability.registered")[-1].payload["manifest"]
    assert manifest["capability_id"] == cid and manifest["consequence_class"] == "read_only"
    prov = manifest["provenance"]
    stage = prov["companions"]["stage1:sort"]
    assert stage["binary_sha256"] and stage["argv"] == ["{binary}", "-u", "--", "{file}"] and "license" in stage
    assert prov["pipeline"] == ["sort -u -- {file}", "wc -l {file}"] and prov["binary_sha256"]
    verified = [e.payload for e in body.journal.replay("genesis.verified") if e.payload["capability_id"] == cid]
    assert len(verified) == 1 and verified[0]["passed"] and verified[0]["report"]["cases"] == 6
    assert body.journal.replay("deficit.resolved")[0].payload["resume"] == "original mission"
    body.close()
    with Body(home, clock=Clock()) as reopened:                      # the pipeline survives a restart
        assert reopened.registry.state[cid] == "ATTACHED" and reopened.registry.usable(cid)[0]


@needs_tools
def test_without_composition_the_same_mission_pays_for_a_build(tmp_path, monkeypatch):
    """The ablation: the same contract, with pipelines disabled, goes to the builder."""
    monkeypatch.setattr(genesis_mod.Genesis, "_pipeline_search", lambda self, *a, **k: False)
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _spec(data, DISTINCT, "m:distinct", 2)))
    clock = Clock()
    builder = builders.StaticBuilder(BUILT, identity="would-build")
    body = Body(home, clock=clock, builder=builder).open()
    body.boot()
    states = _tick(body, clock)
    assert "ACHIEVED" in _state(states, "m:distinct") and len(builder.calls) == 1
    assert ("builder", "built and verified") in _routes(body)
    body.close()


@needs_tools
def test_an_attached_capability_is_reused_as_stage_one_and_the_route_names_what_it_examined(tmp_path):
    """A capability formed for one mission feeds another: the registry, not a hand-written list, is searched first."""
    home, key, body_id, data = make_body(tmp_path)
    clock = Clock()
    body = Body(home, clock=clock, builder=None).open()
    body.boot()
    drop(home, signed(key, body_id, "MISSION", _spec(data, SORTED_UNIQUE, "m:sorted", ["p", "q"])))
    assert "ACHIEVED" in _state(_tick(body, clock), "m:sorted")
    first = "acquired.text.sorted_unique_lines.sort"
    assert body.registry.state[first] == "ATTACHED"
    drop(home, signed(key, body_id, "MISSION", _spec(data, DISTINCT, "m:distinct", 2)))
    assert "ACHIEVED" in _state(_tick(body, clock), "m:distinct")
    routes = _routes(body, "text.distinct_line_count")
    assert routes[-1] == ("installed_software", "composed from existing tools: sort -u -- {file} | wc -l {file} "
                                                f"(stage 1 reuses attached {first})")
    discovery = [e.payload for e in body.journal.replay("genesis.discovery")
                 if e.payload["function"] == "text.distinct_line_count"][-1]
    assert {"capability_id": first, "state": "ATTACHED", "usable": "stage 1"} in discovery["registry_examined"]
    assert any(e["capability_id"] == "fs.read" and e["usable"] != "stage 1" for e in discovery["registry_examined"])
    stage = body.registry.manifests["acquired.text.distinct_line_count.sort-wc"].provenance["companions"]["stage1:sort"]
    assert stage["source"] == first
    body.close()


@needs_tools
def test_a_pipeline_that_answers_the_public_examples_but_not_the_held_out_vectors_is_never_acquired(tmp_path):
    """Case-insensitive distinct lines: sort -u | wc -l answers both public examples and misses 'A' and 'a'."""
    contract = dict(DISTINCT, function="text.distinct_lines_any_case",
                    description="The number of distinct lines in a text file, ignoring letter case.",
                    examples=[{"input_text": "a\nb\na\n", "expected": 2}, {"input_text": "x\n", "expected": 1}],
                    held_out=[{"input_text": "A\na\n", "expected": 1}, {"input_text": "", "expected": 0},
                              {"input_text": "Q\nq\nr\n", "expected": 2}])
    built = "def run(text):\n    return len({l.lower() for l in text.splitlines()})\n"
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _spec(data, contract, "m:anycase", 2)))
    clock = Clock()
    builder = builders.StaticBuilder(built, identity="b")
    body = Body(home, clock=clock, builder=builder).open()
    body.boot()
    states = _tick(body, clock)
    rejected = [e.payload for e in body.journal.replay("genesis.verified")
                if e.payload["capability_id"].startswith("acquired.")]
    assert rejected and not any(v["passed"] for v in rejected)
    assert not any(e.payload["manifest"]["capability_id"].startswith("acquired.")
                   for e in body.journal.replay("capability.registered"))
    assert len(builder.calls) == 1 and "ACHIEVED" in _state(states, "m:anycase")
    body.close()


@needs_tools
def test_a_pipeline_whose_stage_one_binary_changes_is_quarantined_at_restart(tmp_path, monkeypatch):
    """Both binaries are pinned: a changed stage 1 alone quarantines the pipeline, and it no longer serves."""
    tools = tmp_path / "tools"
    tools.mkdir()
    copies = {name: shutil.copy2(installed_binary(name), tools / name) for name in ("sort", "wc", "uniq")}
    real = genesis_mod.installed_binary
    monkeypatch.setattr(genesis_mod, "installed_binary", lambda name: str(copies[name]) if name in copies else real(name))
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _spec(data, DISTINCT, "m:distinct", 2)))
    clock = Clock()
    body = Body(home, clock=clock, builder=None).open()
    body.boot()
    assert "ACHIEVED" in _state(_tick(body, clock), "m:distinct")
    cid = "acquired.text.distinct_line_count.sort-wc"
    assert body.registry.state[cid] == "ATTACHED"
    body.close()
    with open(copies["sort"], "ab") as handle:                     # stage 1 only; stage 2 (wc) is unchanged
        handle.write(b"\0")
    with Body(home, clock=Clock()) as reopened:
        assert reopened.registry.state[cid] == "QUARANTINED"
        notes = [e.payload for e in reopened.journal.replay("capability.state") if e.payload["capability_id"] == cid]
        assert notes[-1]["why"] == "a pipeline binary missing or changed since verification"


@needs_tools
def test_the_final_line_wc_alone_misses_is_counted_by_composing_sort_before_it(tmp_path):
    """wc -l alone fails this contract's held-out vectors (test_greg_genesis_discovery); sort ends the last line."""
    contract = {"function": "text.lines_including_last", "output_field": "lines",
                "description": "The number of lines, counting a final line that has no newline.",
                "returns": "an integer", "build_budget_usd": 1.0,
                "examples": [{"input_text": "alpha\nbeta\n", "expected": 2}, {"input_text": "one line\n", "expected": 1}],
                "held_out": [{"input_text": "no newline at all", "expected": 1},
                             {"input_text": "a\nb", "expected": 2}, {"input_text": "", "expected": 0}]}
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _spec(data, contract, "m:last", 4)))
    clock = Clock()
    builder = builders.StaticBuilder("def run(text):\n    return len(text.splitlines())\n", identity="b")
    body = Body(home, clock=clock, builder=builder).open()
    body.boot()
    assert "ACHIEVED" in _state(_tick(body, clock), "m:last") and builder.calls == []
    assert _routes(body)[-1] == ("installed_software", "composed from existing tools: sort -- {file} | wc -l {file}")
    single = [e.payload for e in body.journal.replay("genesis.verified")
              if e.payload["capability_id"] == "acquired.text.lines_including_last.wc"]
    assert single and not single[0]["passed"]                     # the single tool was tried first and refused
    body.close()


def test_only_text_producing_templates_can_feed_a_pipeline():
    firsts = [t for t in genesis_mod.DISCOVERY_TEMPLATES if t.parse in genesis_mod.PIPELINE_STAGE1_PARSES]
    assert firsts and all(t.argv.count("{file}") == 1 and not t.companions for t in firsts)
    assert not any(t.parse in ("first_int", "first_hex_token") for t in firsts)


def test_a_tool_whose_output_can_never_equal_the_contract_is_not_run_and_the_record_says_why(tmp_path, monkeypatch):
    """A digest is never an integer: for an integer contract, sha256sum and the text filters are not spawned at all,
    as single tools or as stage 2, and the discovery record names the reason. Numbers stay comparable across int and
    float."""
    assert genesis_mod._could_equal("first_int", 2) and genesis_mod._could_equal("first_int", 2.0)
    assert not genesis_mod._could_equal("first_hex_token", 2) and not genesis_mod._could_equal("lines", "a")
    assert genesis_mod._could_equal("an unknown parse", object())
    spawned = []
    real = genesis_mod._run_bounded
    monkeypatch.setattr(genesis_mod, "_run_bounded",
                        lambda argv, *a, **k: spawned.append(argv[0]) or real(argv, *a, **k))
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _spec(data, DISTINCT, "m:distinct", 2)))
    clock = Clock()
    body = Body(home, clock=clock, builder=builders.StaticBuilder(BUILT, identity="would-build")).open()
    body.boot()
    assert "ACHIEVED" in _state(_tick(body, clock), "m:distinct")
    tried = body.journal.replay("genesis.discovery")[-1].payload["tried"]
    pruned = {t["binary_name"] for t in tried if "can never equal" in str(t.get("result"))}
    assert {"sha256sum", "base64", "sort", "head"} <= pruned and "wc" not in pruned
    assert not [a for a in spawned if any(n in a for n in ("sha1sum", "sha256sum", "sha512sum", "md5sum", "b2sum"))]
    body.close()
