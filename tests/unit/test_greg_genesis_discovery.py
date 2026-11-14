"""Capability Genesis finds an installed tool by its behaviour before it builds (acceptance C.G3, C.G5).

A function the catalog does not list, with a founder-signed contract, is tried against a fixed set of installed
read-only text filters. A filter that answers the contract's public examples and its held-out vectors is acquired
(pinned by hash, licence read) and the original mission resumes on it; the builder is never called. Only when no
installed tool behaves as the contract says does the builder run. Before this, the uncatalogued route went straight
to the builder.
"""
import json

import pytest

from greg import builders, genesis as genesis_mod
from greg.body import Body
from greg.capabilities import installed_binary
from tests.greg_fixtures import Clock, drop, make_body, mission, signed

needs_wc = pytest.mark.skipif(installed_binary("wc") is None, reason="wc is not installed on this host")

FUNCTION = "text.line_count"
LINES = {
    "function": FUNCTION,
    "description": "The number of newline-terminated lines in a text file (a final line without a newline does "
                   "not count).",
    "returns": "an integer", "output_field": "lines",
    "examples": [{"input_text": "alpha\nbeta\n", "expected": 2}, {"input_text": "one line\n", "expected": 1}],
    "held_out": [{"input_text": "", "expected": 0}, {"input_text": "no newline at all", "expected": 0},
                 {"input_text": "a\n\n\nb\n", "expected": 4}, {"input_text": "ñandú\negregore\nx", "expected": 2}],
    "build_budget_usd": 1.0}
BUILT = "def run(text):\n    return text.count('\\n')\n"     # what a builder would write for the same contract


def _spec(data, contract, *, auto_attach=True, expected=3):
    doc = data / "notes.txt"
    doc.write_text("first\nsecond\nthird\n")
    check = {"check_id": "lines-counted", "description": "the notes have a known number of lines",
             "sensor": {"function": contract["function"], "params": {"path": str(doc)}, "target": "fs:notes.txt"},
             "predicate": {"op": "equals", "field": contract["output_field"], "value": expected}}
    spec = mission("m:lines", checks=[check], strategies=[], ceiling="read_only", budget=1.0,
                   capabilities=["fs.read", f"acquired.{contract['function']}.*", f"built.{contract['function']}.*"],
                   auto_attach=auto_attach)
    spec["capability_specs"] = [dict(contract)]
    return spec


def _run(tmp_path, contract, builder, *, ticks=4, **kw):
    home, key, body_id, data = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", _spec(data, contract, **kw)))
    clock = Clock()
    body = Body(home, clock=clock, builder=builder).open()
    body.boot()
    states = []
    for _ in range(ticks):
        clock.advance(30)
        states.append(body.tick()["missions"][0]["state"])
    return home, body, states


def _routes(body):
    return [(e.payload["route"], e.payload["result"]) for e in body.journal.replay("genesis.route")]


@needs_wc
def test_an_uncatalogued_function_is_served_by_an_installed_tool_found_by_behaviour_and_nothing_is_built(tmp_path):
    assert FUNCTION not in genesis_mod.CATALOG
    builder = builders.StaticBuilder(BUILT, identity="would-build")
    home, body, states = _run(tmp_path, LINES, builder)
    j = body.journal
    assert "ACHIEVED" in states                                     # the original mission closes
    assert builder.calls == []                                      # acquired, never built
    assert _routes(body) == [("verified_detached", "none"),
                             ("installed_software", "discovered by behaviour: wc -l {file}")]
    cid = f"acquired.{FUNCTION}.wc"
    discovery = j.replay("genesis.discovery")[-1].payload
    assert discovery["selected"] == cid and discovery["tried"][-1]["result"] == "qualified"
    verified = [e.payload for e in j.replay("genesis.verified")]
    assert len(verified) == 1 and verified[0]["passed"] and verified[0]["report"]["cases"] == 6
    manifest = j.replay("capability.registered")[0].payload["manifest"]
    assert manifest["capability_id"] == cid and manifest["consequence_class"] == "read_only"
    prov = manifest["provenance"]
    assert prov["binary_sha256"] and prov["discovered_by"] == "behaviour against the founder-signed contract"
    assert prov["argv"] == ["{binary}", "-l", "{file}"] and "license" in prov
    assert j.replay("deficit.resolved")[0].payload["resume"] == "original mission"
    receipts = [e.payload for e in j.replay("mission.observed") if e.payload.get("passed")]
    assert receipts and receipts[-1]["check_id"] == "lines-counted"
    assert j.replay("mission.appraised")[-1].payload["checks"]["checks_rederived_from_receipts"] is True
    body.close()

    with Body(home, clock=Clock()) as reopened:                      # the acquired tool survives a restart
        assert reopened.registry.state[cid] == "ATTACHED" and reopened.registry.usable(cid)[0]


@needs_wc
def test_without_discovery_the_same_mission_pays_for_a_build(tmp_path, monkeypatch):
    """The ablation: the same contract, with the template set emptied, goes to the builder."""
    monkeypatch.setattr(genesis_mod, "DISCOVERY_TEMPLATES", ())
    builder = builders.StaticBuilder(BUILT, identity="would-build")
    _, body, states = _run(tmp_path, LINES, builder)
    assert "ACHIEVED" in states and len(builder.calls) == 1
    assert ("builder", "built and verified") in _routes(body)
    body.close()


@needs_wc
def test_a_tool_that_answers_the_public_examples_but_not_the_held_out_vectors_is_never_acquired(tmp_path):
    """Public examples screen; the held-out vectors decide. wc -l counts newlines, so it misses a final line."""
    contract = dict(LINES, function="text.lines_including_last", output_field="lines",
                    description="The number of lines, counting a final line that has no newline.",
                    held_out=[{"input_text": "no newline at all", "expected": 1},
                              {"input_text": "a\nb", "expected": 2}, {"input_text": "", "expected": 0}])
    builder = builders.StaticBuilder("def run(text):\n    return len(text.splitlines())\n", identity="b")
    _, body, states = _run(tmp_path, contract, builder, expected=3)
    j = body.journal
    rejected = [e.payload for e in j.replay("genesis.verified") if e.payload["capability_id"].startswith("acquired.")]
    assert rejected and not any(v["passed"] for v in rejected)
    assert not any(e.payload["manifest"]["capability_id"].startswith("acquired.")
                   for e in j.replay("capability.registered"))
    tried = {" ".join([t["binary_name"], *t["argv"]]): t["result"] for t in j.replay("genesis.discovery")[0].payload["tried"]}
    assert tried["wc -l {file}"].startswith("matched the public examples, failed")
    assert len(builder.calls) == 1 and "ACHIEVED" in states        # the builder serves what nothing installed does
    body.close()


def test_when_nothing_installed_behaves_as_the_contract_says_the_order_is_search_then_build(tmp_path):
    """C.G5: acquire before build, with the exact route order."""
    from tests.unit.test_greg_genesis_builder import CONTRACT, GOOD
    builder = builders.StaticBuilder(GOOD, identity="b")
    _, body, _ = _run(tmp_path, dict(CONTRACT), builder, expected=0)
    routes = _routes(body)
    assert [r for r, _ in routes] == ["verified_detached", "installed_software", "builder"]
    assert routes[1][1].startswith("no installed tool behaves as the contract says")
    assert routes[2][1] == "built and verified" and len(builder.calls) == 1
    opened = body.journal.replay("deficit.opened")[0].payload
    assert opened["search_order"] == ["attached", "verified_detached", "installed_software", "builder", "founder"]
    body.close()


@pytest.mark.skipif(installed_binary("sha256sum") is None, reason="sha256sum is not installed on this host")
def test_a_catalogued_function_with_a_builder_ready_is_acquired_never_built(tmp_path):
    """C.G5, catalogued half: a signed contract and a willing builder do not make GREG build what it can acquire."""
    import hashlib
    contract = {"function": "hash.sha256", "description": "The SHA-256 digest of one file, as lowercase hex.",
                "returns": "a hex string", "output_field": "sha256",
                "examples": [{"input_text": t, "expected": hashlib.sha256(t.encode()).hexdigest()}
                             for t in ("a", "first\nsecond\nthird\n")],
                "held_out": [{"input_text": t, "expected": hashlib.sha256(t.encode()).hexdigest()}
                             for t in ("", "b", "c\n")], "build_budget_usd": 1.0}
    builder = builders.StaticBuilder("def run(text):\n    import hashlib\n    return hashlib.sha256(text.encode())"
                                     ".hexdigest()\n", identity="would-build")
    expected = hashlib.sha256(b"first\nsecond\nthird\n").hexdigest()
    _, body, states = _run(tmp_path, contract, builder, expected=expected)
    routes = _routes(body)
    assert "ACHIEVED" in states and builder.calls == []
    assert routes == [("verified_detached", "none"), ("installed_software", "acquired")]
    assert body.journal.replay("deficit.resolved")[0].payload["capability_id"].startswith("acquired.hash.sha256.")
    body.close()


@needs_wc
def test_a_found_tool_waits_for_the_founder_when_the_mission_does_not_pre_authorize_attach(tmp_path):
    builder = builders.StaticBuilder(BUILT, identity="b")
    _, body, states = _run(tmp_path, LINES, builder, auto_attach=False, ticks=3)
    cid = f"acquired.{FUNCTION}.wc"
    assert "ACHIEVED" not in states and body.registry.state[cid] == "VERIFIED"
    awaiting = [e.payload for e in body.journal.replay("deficit.awaiting_attach")]
    assert awaiting and awaiting[0]["capability_id"] == cid
    assert builder.calls == []                                      # a match waiting for the founder is not rebuilt
    body.close()


def test_a_search_that_found_nothing_is_not_rerun_while_nothing_installed_changes(tmp_path, monkeypatch):
    """The second resolution of the same deficit reads the recorded search and runs no template."""
    from tests.unit.test_greg_genesis_builder import CONTRACT
    _, body, _ = _run(tmp_path, dict(CONTRACT, build_budget_usd=0.0), None, ticks=2, expected=0)
    found = [e.payload for e in body.journal.replay("genesis.discovery")]
    assert len(found) == 1 and found[0]["selected"] is None
    ran = []
    monkeypatch.setattr(genesis_mod, "_screen", lambda *a, **k: ran.append(a) or "x")
    m = body.engine.book.missions["m:lines"]
    body.genesis.resolve(mission=m, function=CONTRACT["function"], purpose="sensor for lines-counted",
                         now=Clock().now)
    assert ran == []                                                # nothing installed changed: nothing re-run
    again = [r for r in _routes(body) if r[1].startswith("no installed tool behaves as the contract says (searched")]
    assert again
    assert len(body.journal.replay("genesis.discovery")) == 1
    body.close()


@needs_wc
def test_a_tool_the_founder_detached_is_never_rediscovered(tmp_path):
    """Discovery cannot undo the founder's detach by registering the same tool again."""
    builder = builders.StaticBuilder(BUILT, identity="would-build")
    _, body, _ = _run(tmp_path, LINES, builder, ticks=2)
    cid = f"acquired.{FUNCTION}.wc"
    assert body.registry.state[cid] == "ATTACHED"
    body.registry.set_state(cid, "DETACHED")
    verified_before = len(body.journal.replay("genesis.verified"))
    m = body.engine.book.missions["m:lines"]
    got = body.genesis.resolve(mission=m, function=FUNCTION, purpose="sensor for lines-counted", now=Clock().now)
    assert body.registry.state[cid] == "DETACHED"
    assert getattr(got, "capability_id", None) != cid
    tried = body.journal.replay("genesis.discovery")[-1].payload["tried"]
    assert any(t["binary_name"] == "wc" and "DETACHED" in t["result"] for t in tried)
    assert all(e.payload["capability_id"] != cid for e in body.journal.replay("genesis.verified")[verified_before:])
    body.close()


def test_the_template_set_holds_only_read_only_filters_given_one_file():
    allowed = {"wc", "sha256sum", "sha1sum", "sha512sum", "md5sum", "b2sum", "cksum", "sort", "uniq", "tac",
               "head", "tail", "base64"}
    for template in genesis_mod.DISCOVERY_TEMPLATES:
        assert template.binary_name in allowed and template.argv[0] == "{binary}"
        assert template.argv.count("{file}") == 1 and not template.companions
        assert not any(flag in template.argv for flag in ("-o", "--output", "-i", "--in-place"))
        assert template.parse in genesis_mod.PARSERS
    assert json.dumps([t.binary_name for t in genesis_mod.DISCOVERY_TEMPLATES])     # serializable for the record
