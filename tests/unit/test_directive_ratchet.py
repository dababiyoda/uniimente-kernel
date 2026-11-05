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


def ratchet(head, world, read_head=None):
    tree = d.read_tree()
    return d.evidence_ratchet_problems(world, (head, world[1], world[2]), tree, read_head or tree)


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
    assert all("nothing it cites changed" in p for p in problems)


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
        "ratchet: S1.A2 was open at the base and is newly retired into S1.A1, which was already met there; retire it "
        "into an open ask, or withdraw it by a founder record"]


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
