"""The directive map ratchets against a base on evidence, not only on blocker classes (review of #249, findings 1-2).

The pin held each open ask's blocker class, so an ask could still be closed with no new evidence: set its coverage
to "covered" and drop its blocker, or lower its required tier, or retire it into an ask that was already met. Each
raised the met count and passed ``directive --against``. ``evidence_ratchet_problems`` refuses all three, and lets
an ask close when something it cites changed in the same change.
"""
from __future__ import annotations

import copy

import pytest

from acceptance import directive as d
from acceptance import rank

ATTACKED = ("S1.A2", "S3.A1", "S5.A1")          # the asks the review closed by editing their coverage


@pytest.fixture(scope="module")
def world():
    return d.defaults()


def ask(doc, ask_id):
    return next(a for s in doc["sections"] for a in s["asks"] if a["id"] == ask_id)


def met(doc, world):
    return {a["id"] for s in d.directive_report(doc, world[1], world[2])["sections"] for a in s["asks"] if a["met"]}


def ratchet(head, world, read_head=None, manifest=None, contract=None, base=None):
    tree = d.read_tree()
    return d.evidence_ratchet_problems(base or world, (head, manifest or world[1], contract or world[2]), tree,
                                       read_head or tree)


def declared_covered(world, ids=ATTACKED):
    head = copy.deepcopy(world[0])
    for aid in ids:
        a = ask(head, aid)
        a["coverage"] = "covered"
        a.pop("blocker", None)
    return head


def test_the_reviewed_asks_are_open_at_the_base_and_the_edit_alone_closes_them(world):
    """The precondition the other tests rely on: without the ratchet, the edit raises met."""
    before, after = met(world[0], world), met(declared_covered(world), world)
    assert not before & set(ATTACKED) and set(ATTACKED) <= after


def test_declaring_coverage_without_new_evidence_is_refused(world):
    problems = ratchet(declared_covered(world), world)
    assert [p.split()[1] for p in problems] == list(ATTACKED)
    assert all("no test file its evidence reaches changed" in p for p in problems)


def test_lowering_the_required_tier_without_new_evidence_is_refused(world):
    """The first open ask that a lowered required tier (and declared coverage) alone turns met: picked from the
    map, so the test follows it."""
    rep = d.directive_report(world[0], world[1], world[2])
    for row in (a for s in rep["sections"] for a in s["asks"]):
        if row["met"] or "retired" in row or row["tier"] in (d.NO_EVIDENCE, d.BLOCKED) \
                or rank(row["tier"]) >= rank(row["required_tier"]):
            continue
        head = copy.deepcopy(world[0])
        ask(head, row["id"]).update(required_tier=row["tier"], coverage="covered")
        if row["id"] in met(head, world):
            break
    else:
        pytest.fail("no open ask in the map is closed by lowering its required tier")
    assert any(p.startswith(f"ratchet: {row['id']} ") for p in ratchet(head, world))


def test_retiring_an_open_ask_into_one_already_met_is_refused(world):
    open_at_base = met(world[0], world)
    assert "S1.A1" in open_at_base and "S1.A2" not in open_at_base
    head = copy.deepcopy(world[0])
    ask(head, "S1.A2")["retired"] = {"superseded_by": "S1.A1"}
    assert "S1.A2" in met(head, world)                                     # what the review reproduced
    assert ratchet(head, world) == [
        "ratchet: S1.A2 was open at the base and is newly retired into S1.A1, which was not an open ask there; retire "
        "it into an ask that was open at the base"]


def test_retiring_into_an_ask_that_was_open_at_the_base_is_allowed(world):
    head = copy.deepcopy(world[0])
    ask(head, "S1.A2")["retired"] = {"superseded_by": "S3.A1"}            # open at the base too
    assert ratchet(head, world) == []


def test_an_ask_closes_when_a_file_it_cites_changed(world):
    head = declared_covered(world, ("S5.A1",))
    cited = ask(head, "S5.A1")["evidence"][0].split("::")[0]
    tree = d.read_tree()

    def changed(path):
        text = tree(path)
        return text + "\n# new test\n" if path == cited else text

    assert ratchet(head, world, changed) == []


def test_an_ask_closes_when_it_cites_a_file_that_is_new_in_this_change(world):
    head = declared_covered(world, ("S5.A1",))
    ask(head, "S5.A1")["evidence"].append("tests/unit/test_brand_new_evidence.py::test_it")
    tree = d.read_tree()
    assert ratchet(head, world, lambda p: "def test_it(): pass\n" if p.endswith("brand_new_evidence.py") else tree(p)) \
        == []


def test_citing_old_unchanged_evidence_does_not_close_an_ask(world):
    head = declared_covered(world, ("S5.A1",))
    met_at_base = next(iter(sorted(met(world[0], world))))
    ask(head, "S5.A1")["evidence"] += ask(world[0], met_at_base)["evidence"]    # evidence that was already there
    assert [p.split()[1] for p in ratchet(head, world)] == ["S5.A1"]


def test_an_unchanged_map_and_asks_met_at_the_base_raise_nothing(world):
    assert ratchet(copy.deepcopy(world[0]), world) == []


def test_the_base_map_is_read_from_git_and_a_ref_without_one_reads_none(tmp_path):
    """Read from a repository of its own, so the test holds in a copy of this tree without .git."""
    import subprocess
    repo = tmp_path / "repo"
    paths = [p.relative_to(d.ROOT) for p in (d.DIRECTIVE_MAP, d.MANIFEST, d.CONTRACT)]
    for rel in paths:
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_bytes((d.ROOT / rel).read_bytes())
    git = ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-c", "commit.gpgsign=false"]
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(git + ["-C", str(repo), "add", "-A"], check=True)
    subprocess.run(git + ["-C", str(repo), "commit", "-qm", "map"], check=True)
    assert d.map_at("no-such-ref-for-the-directive-map", repo) is None
    base = d.map_at("HEAD", repo)
    assert base is not None and len(base[0]["sections"]) == d.SECTIONS
    assert d.read_at("HEAD", repo)("no/such/file.py") is None
    assert d.read_at("HEAD", repo)(paths[0].as_posix()) == (d.ROOT / paths[0]).read_text(encoding="utf-8")


def test_the_cli_refuses_what_the_evidence_ratchet_refuses(world, monkeypatch, capsys):
    from acceptance import __main__ as cli
    pin = d.load_map(d.PIN)
    monkeypatch.setattr(d, "pin_at", lambda ref: (pin, None))
    monkeypatch.setattr(d, "map_at", lambda ref: world)
    monkeypatch.setattr(d, "evidence_ratchet_problems", lambda *a, **k: ["ratchet: S5.A1 was open at the base"])
    assert cli.main(["directive", "--against", "base"]) == 2
    assert "ratchet: S5.A1 was open at the base" in capsys.readouterr().out
    monkeypatch.setattr(d, "evidence_ratchet_problems", lambda *a, **k: [])
    assert cli.main(["directive", "--against", "base"]) == 0
    assert "every ask closed since cites new or changed evidence" in capsys.readouterr().out


# -- review of the first ratchet (f3a1df61): each bypass and the false refusal it found --------------------------

def test_declaring_coverage_in_a_mission_requirement_closes_nothing(world):
    """Finding 1: the same claim edit, one level down in missions.json, closed 15 asks with no test changed."""
    manifest, head = copy.deepcopy(world[1]), copy.deepcopy(world[0])
    reqs = {(m["id"], r["id"]): r for m in manifest["missions"] for r in m["requirements"]}
    before = met(world[0], world)
    for s in head["sections"]:
        for a in s["asks"]:
            cited = [e.partition(":")[2] for e in a.get("evidence", []) if e.startswith("mission:")]
            if a["id"] in before or not cited:
                continue
            for ref in cited:
                reqs[tuple(ref.split("."))]["coverage"] = "covered"
            a["coverage"] = "covered"
            a.pop("blocker", None)
    closed = {x["id"] for s in d.directive_report(head, manifest, world[2])["sections"] for x in s["asks"]
              if x["met"]} - before
    assert len(closed) >= 3                                               # the attack does close asks unguarded
    refused = {p.split()[1] for p in ratchet(head, world, manifest=manifest)}
    assert closed <= refused


def test_retiring_into_an_ask_created_in_the_same_change_is_refused(world):
    """Finding 2: a copy of a met ask, added at the head, was an unchecked successor."""
    head = copy.deepcopy(world[0])
    s1 = next(s for s in head["sections"] if s["n"] == 1)
    s1["asks"].append({**copy.deepcopy(ask(head, "S1.A1")), "id": "S1.A9"})
    ask(head, "S1.A2")["retired"] = {"superseded_by": "S1.A9"}
    assert ratchet(head, world) == [
        "ratchet: S1.A2 was open at the base and is newly retired into S1.A9, which was not an open ask there; retire "
        "it into an ask that was open at the base"]


def test_withdrawing_an_open_ask_by_a_record_is_refused(world):
    """Finding 3: a record retirement left the head report, so the residual could be emptied by any intent file."""
    head = copy.deepcopy(world[0])
    record = "docs/intent/INTENT-20261030-BUILD-BEFORE-DEVICE-RUN.json#Continue building"
    open_ids = [a for a in sorted(set(i for s in head["sections"] for i in (x["id"] for x in s["asks"]))
                                  - met(world[0], world))][:5]
    for aid in open_ids:
        ask(head, aid)["retired"] = {"record": record}
    problems = ratchet(head, world)
    assert [p.split()[1] for p in problems] == open_ids
    assert all("withdrawing an obligation is the founder's decision at merge" in p for p in problems)


def test_re_pointing_a_retirement_at_a_met_ask_is_refused(world):
    """Finding 4: an ask already retired at the base skipped the successor check when its successor changed."""
    base = copy.deepcopy(world[0])
    ask(base, "S1.A2")["retired"] = {"superseded_by": "S3.A1"}            # open successor at the base
    head = copy.deepcopy(base)
    ask(head, "S1.A2")["retired"] = {"superseded_by": "S1.A1"}            # re-pointed at a met one
    problems = ratchet(head, world, base=(base, world[1], world[2]))
    assert [p.split()[1] for p in problems] == ["S1.A2"]
    assert ratchet(copy.deepcopy(base), world, base=(base, world[1], world[2])) == []


def test_reinstating_a_withdrawn_ask_closes_nothing_without_new_evidence(world):
    """Finding 5: an ask withdrawn at the base was absent there, so reinstated and met it went unchecked."""
    base = copy.deepcopy(world[0])
    ask(base, "S5.A1")["retired"] = {"record": "docs/intent/INTENT-20261030-BUILD-BEFORE-DEVICE-RUN.json#x"}
    head = declared_covered(world, ("S5.A1",))
    assert [p.split()[1] for p in ratchet(head, world, base=(base, world[1], world[2]))] == ["S5.A1"]


def test_an_ask_that_cites_only_a_contract_function_closes_on_its_requirements_tests(world):
    """Finding 6 (a false refusal): a contract function's evidence is requirement ids; their tests are followed."""
    rep = d.directive_report(world[0], world[1], world[2])
    open_ids = {a["id"] for s in rep["sections"] for a in s["asks"] if not a["met"]}
    functions = {f["id"]: f for f in world[2]["functions"]}
    for s in world[0]["sections"]:
        for a in s["asks"]:
            refs = a.get("evidence", [])
            if a["id"] in open_ids and refs and all(r.startswith("contract:") for r in refs) and "retired" not in a:
                break
        else:
            continue
        break
    else:
        pytest.skip("no open ask cites only contract functions")
    files = d.evidence_files(a, world[1], world[2])
    assert files, "a contract function's requirements name test files"
    assert all(f.startswith("tests/") for f in files)
    tree = d.read_tree()
    head, manifest = copy.deepcopy(world[0]), copy.deepcopy(world[1])
    reqs = {(m["id"], r["id"]): r for m in manifest["missions"] for r in m["requirements"]}
    for ref in (r.partition(":")[2] for r in a["evidence"]):
        for req_ref in functions[ref]["evidence"]:
            reqs[tuple(req_ref.split("."))]["coverage"] = "covered"     # the reviewer's reproduction
    ask(head, a["id"]).update(coverage="covered", required_tier="IMPLEMENTED")
    ask(head, a["id"]).pop("blocker", None)
    assert a["id"] in {x["id"] for s in d.directive_report(head, manifest, world[2])["sections"] for x in s["asks"]
                       if x["met"]}
    assert [p.split()[1] for p in ratchet(head, world, manifest=manifest)] == [a["id"]]   # no test changed
    assert ratchet(head, world, lambda p: tree(p) + "\n# new\n" if p == files[0] else tree(p),
                   manifest=manifest) == []                                              # one did


def test_a_base_map_this_schema_cannot_read_is_reported_not_raised(world):
    """Finding 7: a base on an older schema raised a traceback."""
    base = copy.deepcopy(world[0])
    del ask(base, "S1.A1")["coverage"]
    problems = ratchet(copy.deepcopy(world[0]), world, base=(base, world[1], world[2]))
    assert len(problems) == 1 and problems[0].startswith("ratchet: the base map cannot be read by this tree's "
                                                          "directive schema (KeyError")


def test_every_file_an_asks_evidence_reaches_is_a_test_file(world):
    for s in world[0]["sections"]:
        for a in s["asks"]:
            assert all(f.startswith("tests/") and "::" not in f for f in d.evidence_files(a, world[1], world[2]))
