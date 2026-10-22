"""R2-A (#190's second capability dividend): the confinement tier is one derived, recorded and checked fact.

``workers.confinement_tier`` derives the tier from the isolation evidence GREG itself produced (envelope > landlock >
supervised_unconfined; refused / not_reported when nothing GREG confined ran). The worker's confinement record, the
receipt's worker block and every acceptance record carry it; ``worker.appraise`` derives the tier of its own re-run
and refuses a receipt that claims more than its own evidence supports. These tests exercise recording and claim
checking only: forged receipts are synthetic dictionaries; the real envelope / Landlock paths run as they exist.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from greg import isolation as landlock
from greg import templates, workers
from greg import worker_isolation as isolation
from greg.body import Body, Layout
from tests.greg_fixtures import (Clock, acceptance_confinement, drop, make_body, signed,
                                 skip_required_without_envelope)

SCOPED, UNSCOPED = "scoped to the domain", "unscoped (Landlock ABI < 6)"
ENVELOPE = {"status": "prepared", "filesystem": "os-confined", "mechanism": "bubblewrap", "landlock_abi": None,
            "network_isolated": False}


def _supervised(**landlock_record):
    return {**workers.SUPERVISION, "envelope_refused": "bubblewrap is unavailable on this host",
            **({"landlock": landlock_record} if landlock_record else {})}


@pytest.fixture(autouse=True)
def _no_host_ca_override(monkeypatch):
    for name in isolation._CERT_ENV:     # a host CA outside the supported roots refuses the envelope
        monkeypatch.delenv(name, raising=False)


# -- the derivation, on every evidence shape ----------------------------------------------------------------------

@pytest.mark.parametrize("evidence,expected", [
    (ENVELOPE, ("envelope", None, None)),
    ({**ENVELOPE, "network": "relay-door: x", "network_isolated": True}, ("envelope", None, None)),
    ({**ENVELOPE, "mechanism": "landlock", "landlock_abi": 4}, ("landlock", 4, False)),
    ({**ENVELOPE, "mechanism": "landlock", "landlock_abi": 2}, ("not_reported", None, None)),
    ({**ENVELOPE, "mechanism": "scripted-test-envelope"}, ("not_reported", None, None)),
    ({"mechanism": "bubblewrap"}, ("not_reported", None, None)),                 # not prepared: no envelope applied
    ({**ENVELOPE, "filesystem": "none"}, ("not_reported", None, None)),
    (_supervised(filesystem="landlock", abi=7, signals=SCOPED), ("landlock", 7, True)),
    (_supervised(filesystem="landlock", abi=6, signals=SCOPED), ("landlock", 6, True)),
    (_supervised(filesystem="landlock", abi=5, signals=UNSCOPED), ("landlock", 5, False)),
    (_supervised(filesystem="landlock", abi=7, signals=UNSCOPED), ("landlock", 7, False)),
    (_supervised(filesystem="landlock", abi=5, signals=SCOPED), ("landlock", 5, False)),   # ABI 5 cannot scope
    (_supervised(filesystem="landlock", abi=True, signals=SCOPED), ("supervised_unconfined", None, None)),
    (_supervised(filesystem="landlock", abi=2), ("supervised_unconfined", None, None)),
    (_supervised(filesystem="landlock"), ("supervised_unconfined", None, None)),
    (_supervised(filesystem="none", reason="Landlock ABI None below 3"), ("supervised_unconfined", None, None)),
    (_supervised(), ("supervised_unconfined", None, None)),
    ({"mode": "supervised", "landlock": None}, ("supervised_unconfined", None, None)),
    ({"status": "refused"}, ("refused", None, None)),
    ({"status": "unreviewed", "reason": "x"}, ("refused", None, None)),
    ({"status": "unsupported", "reason": "x"}, ("refused", None, None)),
    ({}, ("not_reported", None, None)),
    (None, ("not_reported", None, None)),
    ("envelope", ("not_reported", None, None)),
])
def test_the_tier_is_derived_from_the_evidence_alone(evidence, expected):
    assert tuple(workers.confinement_tier(evidence).values()) == expected


@pytest.mark.parametrize("record,expected", [
    ({"confinement": "envelope: private filesystem, PID and network namespaces", "landlock": None}, "envelope"),
    ({"confinement": "supervised: ... Landlock-confined", "landlock": {"filesystem": "landlock", "abi": 7,
                                                                       "signals": SCOPED}}, "landlock"),
    ({"confinement": "supervised: ... NOT confined", "landlock": {"filesystem": "none"}}, "supervised_unconfined"),
    ({"confinement": "refused", "landlock": None}, "refused"),
    ({}, "not_reported"),
])
def test_an_acceptance_record_from_before_tiers_derives_its_tier_from_what_greg_wrote_then(record, expected):
    assert workers.confinement_tier(workers._acceptance_evidence(record))["tier"] == expected


def test_the_supervised_worker_record_carries_the_tier_its_landlock_grants_give(tmp_path):
    work = tmp_path / "order" / "repo"
    work.mkdir(parents=True)
    envelope = {"argv": ["true"], "env": {}, "preexec_fn": None, "pass_fds": [], "runtime_root": tmp_path,
                "evidence": _supervised()}
    record = workers._landlock_supervised(envelope, work, sys.executable)["confinement"]
    status = landlock.available()
    if status.get("available"):
        assert (record["tier"], record["landlock_abi"]) == ("landlock", status["abi"])
        assert record["signals_scoped"] is (status["abi"] >= 6)
    else:
        assert record == {**record, "tier": "supervised_unconfined", "landlock_abi": None}
    inside = workers._landlock_supervised({**envelope, "evidence": ENVELOPE}, work, sys.executable)["confinement"]
    assert inside["tier"] == "envelope" and inside["landlock_abi"] is None


def test_each_acceptance_record_carries_the_tier_of_the_run_greg_made(tmp_path, monkeypatch):
    tmp_path = tmp_path / "clone"          # the envelope's runtime goes beside the clone, inside this test's directory
    tmp_path.mkdir()
    [real] = workers.run_tests([["python", "-c", "pass"]], tmp_path, timeout=30, confinement=acceptance_confinement())
    if isolation.host_has_envelope():
        assert real["tier"] == "envelope" and real["isolation"]["mechanism"] == "bubblewrap"

    def no_envelope(*args, **kwargs):
        raise isolation.WorkerIsolationError("bubblewrap unavailable on this host",
                                             evidence={"status": "unsupported", "reason": "bubblewrap unavailable"})
    monkeypatch.setattr(workers, "prepare_worker", no_envelope)
    [refused] = workers.run_tests([["python", "-c", "pass"]], tmp_path, timeout=30, confinement="required")
    assert (refused["tier"], refused["landlock_abi"]) == ("refused", None)
    [fallback] = workers.run_tests([["python", "-c", "pass"]], tmp_path, timeout=30, confinement="supervised")
    if fallback["confinement"] != "refused":                 # a host with no network filter refuses even this
        status = landlock.available()
        expected = ("landlock", status["abi"]) if status.get("available") else ("supervised_unconfined", None)
        assert (fallback["tier"], fallback["landlock_abi"]) == expected
        assert fallback["tier"] == workers.confinement_tier(workers._acceptance_evidence(
            {k: v for k, v in fallback.items() if k != "isolation"}))["tier"]


# -- receipts and the appraiser ------------------------------------------------------------------------------------

def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _repo(root: Path) -> Path:
    repo = root / "proj"
    (repo / "pkg").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "pkg" / "__init__.py").write_text("")
    (repo / "pkg" / "calc.py").write_text("def add(a, b):\n    return a + b\n")
    _git(root, "init", "-q", str(repo))
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A")
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base")
    return repo


AGENT = '''import sys
from pathlib import Path
sys.stdin.read()
Path("pkg/calc.py").write_text("def add(a, b):\\n    return a + b\\n\\n\\ndef sub(a, b):\\n    return a - b\\n")
Path("tests").mkdir(exist_ok=True)
Path("tests/test_calc.py").write_text("from pkg.calc import sub\\n\\n\\ndef test_sub():\\n    assert sub(3, 1) == 2\\n")
print('WORK_REPORT: {"changed": ["pkg/calc.py", "tests/test_calc.py"], "confidence": 0.9}')
'''


def _confined_order(tmp_path, monkeypatch, confinement: str):
    """One real work order: a reviewed headless CLI worker GREG launches itself (envelope, or the supervised
    fallback with Landlock where the host has no envelope), collected and acceptance-run by the real Body."""
    data = tmp_path / "data"
    data.mkdir()
    repo = _repo(data)
    # Inline (-c): the envelope binds the host runtime and the clone, not a script elsewhere on the host.
    monkeypatch.setitem(workers.PROVIDERS, "local-cli", workers.CliAgentWorker(
        "local-cli", [sys.executable, "-c", AGENT], stdin=True, reviewed=True))
    home, key, body_id, _ = make_body(tmp_path, read_roots=[data], worker_confinement=confinement)
    spec = templates.code_change(repo=str(repo), objective="add sub()", order="add-sub", provider="local-cli",
                                 allowed_paths=["pkg/*", "tests/*"], budget_usd=0.5,
                                 workspace_root=Layout(home).workspace)
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        for _ in range(4):
            body.tick()
            clock.advance(60)
    root = Layout(home).workspace / spec["mission_id"].replace(":", "_") / "work-orders" / "add-sub"
    return home, root


def _appraise(home: Path, root: Path, confinement: str, tmp_path: Path) -> dict:
    """``worker.appraise`` standalone (no journal): the receipt is the retained evidence file."""
    from greg.capabilities import BUILTINS, InvocationContext, SecretBroker
    config = json.loads(Layout(home).config.read_text())
    ctx = InvocationContext(workspace=root.parents[1], read_roots=tuple(Path(r) for r in config["read_roots"]),
                            secrets=SecretBroker(tmp_path / "s.json"), manifest=BUILTINS["worker.appraise"][0],
                            worker_confinement=confinement)
    return workers.appraise({"order": "add-sub"}, ctx)


def _host_tier() -> tuple:
    """What this host can give a worker GREG launches: the envelope, else Landlock under ``supervised``, else none."""
    if isolation.host_has_envelope():
        return "envelope", None, None
    status = landlock.available()
    if status.get("available"):
        return "landlock", status["abi"], status["abi"] >= 6
    return "supervised_unconfined", None, None


@pytest.fixture(scope="module")
def order(tmp_path_factory):
    """One real confined run on this host, shared by the claim-checking tests (they edit copies of its receipt)."""
    monkeypatch = pytest.MonkeyPatch()
    tmp = tmp_path_factory.mktemp("tier-order")
    for name in isolation._CERT_ENV:
        monkeypatch.delenv(name, raising=False)
    try:
        home, root = _confined_order(tmp, monkeypatch, acceptance_confinement())
        yield home, root, json.loads((root / "evidence.json").read_text())
    finally:
        monkeypatch.undo()


@pytest.fixture
def receipt(order):
    """Rewrite the retained receipt for one test and restore it after."""
    home, root, original = order
    path = root / "evidence.json"

    def write(mutate) -> None:
        evidence = copy.deepcopy(original)
        mutate(evidence["summary"])
        path.write_text(json.dumps(evidence))
    yield home, root, write
    path.write_text(json.dumps(original))


@pytest.mark.parametrize("confinement", ["required", "supervised"])
def test_a_real_confined_run_records_the_tier_this_host_can_give(tmp_path, monkeypatch, confinement):
    skip_required_without_envelope(confinement)
    home, root = _confined_order(tmp_path, monkeypatch, confinement)
    summary = json.loads((root / "evidence.json").read_text())["summary"]
    assert summary["status"] == "COMPLETED", summary
    tier, abi, scoped = _host_tier()
    worker = summary["worker"]
    assert (worker["tier"], worker["landlock_abi"], worker["signals_scoped"]) == (tier, abi, scoped)
    assert {k: worker["confinement"][k] for k in ("tier", "landlock_abi", "signals_scoped")} == {
        "tier": tier, "landlock_abi": abi, "signals_scoped": scoped}
    assert summary["greg_tests"] and all((t["tier"], t["landlock_abi"]) == (tier, abi) for t in summary["greg_tests"])
    verdict = _appraise(home, root, confinement, tmp_path)
    assert verdict["verdict"] == "ACCEPTED", verdict
    assert verdict["confinement"]["receipt"]["worker"]["tier"] == tier
    assert [t["tier"] for t in verdict["independent_tests"]] == [tier] * len(verdict["independent_tests"])
    assert [t["tier"] for t in verdict["confinement"]["independent_tests"]] == [tier] * len(
        verdict["independent_tests"])


def _forge_supervised(summary, *, landlock_record=None):
    summary["worker"]["isolation"] = _supervised(**(landlock_record or {}))
    summary["worker"]["confinement"] = dict(landlock_record or {"filesystem": "none", "reason": "no Landlock"})


OVERCLAIMS = {
    # receipt says 'envelope' but its isolation evidence is the supervised fallback
    "envelope over a supervised fallback": (
        lambda s: (_forge_supervised(s), s["worker"].update(tier="envelope")), "claims confinement tier 'envelope'"),
    # ... and its confinement record says the bubblewrap envelope
    "envelope record over a supervised fallback": (
        lambda s: (_forge_supervised(s), s["worker"]["confinement"].update(filesystem="bubblewrap envelope")),
        "confinement record claims confinement tier 'envelope'"),
    # 'landlock' with no landlock grants
    "landlock without grants": (
        lambda s: (_forge_supervised(s), s["worker"].update(tier="landlock", landlock_abi=7)),
        "claims confinement tier 'landlock'"),
    # 'landlock' with grants but no ABI
    "landlock without an ABI": (
        lambda s: (_forge_supervised(s, landlock_record={"filesystem": "landlock", "signals": SCOPED}),
                   s["worker"].update(tier="landlock", landlock_abi=7)), "claims confinement tier 'landlock'"),
    # a different ABI than the grants record
    "landlock at another ABI": (
        lambda s: (_forge_supervised(s, landlock_record={"filesystem": "landlock", "abi": 5, "signals": UNSCOPED}),
                   s["worker"].update(tier="landlock", landlock_abi=7)), "claims Landlock ABI 7"),
    # signals scoped claimed with ABI < 6
    "signals scoped below ABI 6": (
        lambda s: (_forge_supervised(s, landlock_record={"filesystem": "landlock", "abi": 5, "signals": UNSCOPED}),
                   s["worker"].update(tier="landlock", landlock_abi=5, signals_scoped=True)),
        "claims signals scoped"),
    # the evidence itself says scoped at ABI < 6
    "evidence scoped below ABI 6": (
        lambda s: _forge_supervised(s, landlock_record={"filesystem": "landlock", "abi": 5, "signals": SCOPED}),
        "cannot scope them"),
    # an acceptance record claims the envelope over a supervised run
    "acceptance envelope over a supervised run": (
        lambda s: [t.update(tier="envelope", isolation={"mode": "supervised", "landlock": None})
                   for t in s["greg_tests"]], "acceptance record 0 claims confinement tier 'envelope'"),
    "an unknown tier": (lambda s: s["worker"].update(tier="microvm"), "unknown confinement tier"),
}


@pytest.mark.parametrize("case", sorted(OVERCLAIMS))
def test_the_appraiser_refuses_a_receipt_that_claims_more_than_its_evidence(receipt, tmp_path, case):
    home, root, write = receipt
    mutate, expected = OVERCLAIMS[case]
    write(mutate)
    verdict = _appraise(home, root, "supervised", tmp_path)
    assert verdict["verdict"] == "REJECTED"
    assert any(expected in f for f in verdict["findings"]), verdict["findings"]


@pytest.mark.parametrize("where", ["worker", "acceptance"])
def test_a_required_body_refuses_a_receipt_below_the_envelope(receipt, tmp_path, where):
    home, root, write = receipt

    def mutate(summary):
        if where == "worker":    # a consistent, honest supervised-with-Landlock receipt: honest, but not allowed
            record = {"filesystem": "landlock", "abi": 7, "signals": SCOPED}
            _forge_supervised(summary, landlock_record=record)
            summary["worker"].update(**workers.confinement_tier(summary["worker"]["isolation"]))
        else:
            for test in summary["greg_tests"]:
                test.update(isolation={"mode": "supervised", "landlock": None}, tier="supervised_unconfined",
                            landlock_abi=None, signals_scoped=None)
    write(mutate)
    verdict = _appraise(home, root, "required", tmp_path)
    assert verdict["verdict"] == "REJECTED"
    assert any("this body requires the envelope" in f for f in verdict["findings"]), verdict["findings"]
    # The same honest receipt is no overclaim: a supervised body does not refuse it for its tier.
    supervised = _appraise(home, root, "supervised", tmp_path)
    assert not any("tier" in f or "requires the envelope" in f for f in supervised["findings"]), supervised


def test_an_old_receipt_without_tiers_still_appraises_from_its_evidence(receipt, tmp_path):
    home, root, write = receipt
    fields = ("tier", "landlock_abi", "signals_scoped")

    def strip(summary):
        for record in (summary["worker"], summary["worker"]["confinement"], *summary["greg_tests"]):
            for name in (*fields, "isolation") if record is not summary["worker"] else fields:
                record.pop(name, None)
    write(strip)
    verdict = _appraise(home, root, acceptance_confinement(), tmp_path)
    assert verdict["verdict"] == "ACCEPTED", verdict
    tier = _host_tier()[0]
    assert verdict["confinement"]["receipt"]["worker"]["tier"] == tier
    assert [t["tier"] for t in verdict["confinement"]["receipt"]["greg_tests"]] == [tier] * len(
        verdict["confinement"]["receipt"]["greg_tests"])


def test_an_old_supervised_landlock_receipt_derives_landlock_and_is_not_refused(receipt, tmp_path):
    home, root, write = receipt

    def old(summary):
        _forge_supervised(summary, landlock_record={"filesystem": "landlock", "abi": 5, "signals": UNSCOPED})
        for name in ("tier", "landlock_abi", "signals_scoped"):
            summary["worker"].pop(name, None)
    write(old)
    verdict = _appraise(home, root, "supervised", tmp_path)
    assert verdict["confinement"]["receipt"]["worker"] == {"tier": "landlock", "landlock_abi": 5,
                                                           "signals_scoped": False}
    assert not any("tier" in f or "scoped" in f for f in verdict["findings"]), verdict["findings"]


class _ClaimingProvider:
    """An in-process test double whose report CLAIMS the bubblewrap envelope: GREG launched nothing it could confine."""
    name = "claiming-test-double"

    def available(self):
        return True, ""

    def run(self, order, cwd):
        (cwd / "tests").mkdir(exist_ok=True)
        (cwd / "pkg" / "calc.py").write_text("def add(a, b):\n    return a + b\n\n\ndef sub(a, b):\n    return a - b\n")
        (cwd / "tests" / "test_calc.py").write_text("from pkg.calc import sub\n\n\ndef test_sub():\n"
                                                    "    assert sub(3, 1) == 2\n")
        return workers.WorkerReport(self.name, self.name, 0, 0.1, 0.01, isolation=dict(ENVELOPE),
                                    confinement={"filesystem": "bubblewrap envelope", "tier": "envelope"})


def test_a_provider_greg_did_not_launch_never_records_the_tier_it_claims(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    repo = _repo(data)
    monkeypatch.setitem(workers.PROVIDERS, "claiming", _ClaimingProvider())
    home, key, body_id, _ = make_body(tmp_path, read_roots=[data], worker_confinement=acceptance_confinement())
    spec = templates.code_change(repo=str(repo), objective="add sub()", order="add-sub", provider="claiming",
                                 allowed_paths=["pkg/*", "tests/*"], budget_usd=0.5,
                                 workspace_root=Layout(home).workspace)
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        for _ in range(3):
            body.tick()
            clock.advance(60)
    root = Layout(home).workspace / spec["mission_id"].replace(":", "_") / "work-orders" / "add-sub"
    worker = json.loads((root / "evidence.json").read_text())["summary"]["worker"]
    assert (worker["tier"], worker["confinement"]["tier"]) == ("not_reported", "not_reported")
