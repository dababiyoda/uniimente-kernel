"""organ.exchange / organ.status: the signed organ exchange as governed mission capabilities.

The refusal tests need no organ checkout. The live exchange runs real DALEOBANKS and
WealthMachineIntelligence code in their own interpreters and is skipped unless all four of
UNIIMENTE_DALEOBANKS_ROOT, UNIIMENTE_DALEOBANKS_PYTHON, UNIIMENTE_WEALTHMACHINE_ROOT and
UNIIMENTE_WEALTHMACHINE_PYTHON name them (CI: the one-machine workflow sets them).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from adapters import bridge_transport as bt
from events.spine import EventSpine
from greg import organ_bridge, organs
from greg.capabilities import BUILTINS, CapabilityError, InvocationContext
from greg.journal import Journal
from provenance.ledger import EvidenceLedger

ORGAN_ENV = ("UNIIMENTE_DALEOBANKS_ROOT", "UNIIMENTE_DALEOBANKS_PYTHON", "UNIIMENTE_WEALTHMACHINE_ROOT",
             "UNIIMENTE_WEALTHMACHINE_PYTHON")
SEED = ("Financial independence is not selfish. It is protection from systems that profit from dependency. "
        "Maybe a budgeting checklist or workshop could help people start.")


def live_organs():
    if not all(os.environ.get(k) for k in ORGAN_ENV):
        why = "organ checkouts not configured (" + ", ".join(ORGAN_ENV) + ")"
        if os.environ.get("UNIIMENTE_REQUIRE_ORGANS") == "1":   # the CI gate: a skip would be a silent pass
            pytest.fail(why)
        pytest.skip(why)
    return {"daleobanks_root": os.environ["UNIIMENTE_DALEOBANKS_ROOT"],
            "daleobanks_python": os.environ["UNIIMENTE_DALEOBANKS_PYTHON"],
            "wealthmachine_root": os.environ["UNIIMENTE_WEALTHMACHINE_ROOT"],
            "wealthmachine_python": os.environ["UNIIMENTE_WEALTHMACHINE_PYTHON"]}


def organ_roots(params: dict) -> tuple:
    """Read roots covering the organ checkouts and their interpreters' directories."""
    return tuple(Path(params[k]).resolve() for k in ("daleobanks_root", "wealthmachine_root")) + \
        tuple(Path(params[k]).parent for k in ("daleobanks_python", "wealthmachine_python"))


@pytest.fixture
def journal(tmp_path):
    return Journal(EventSpine(EvidenceLedger("sha256:" + "1" * 64, path=str(tmp_path / "l.jsonl"))),
                   actor="spiffe://uniimente.internal/test/organs")


def ctx(tmp_path, journal, *, roots=(), mission_id="m:organ-test", capability="organ.exchange"):
    manifest, _ = BUILTINS[capability]
    return InvocationContext(workspace=tmp_path / "w", read_roots=tuple(Path(r) for r in roots), secrets=None,
                             manifest=manifest, journal=journal, mission_id=mission_id)


def fake_checkouts(tmp_path):
    dale, wmi = tmp_path / "dale", tmp_path / "wmi"
    (dale / "services").mkdir(parents=True)
    (dale / "services" / "idea_refinery.py").write_text("")
    (wmi / "src" / "services").mkdir(parents=True)
    (wmi / "src" / "services" / "opportunity_intake.py").write_text("")
    return {"daleobanks_root": str(dale), "wealthmachine_root": str(wmi),
            "daleobanks_python": "/usr/bin/python3", "wealthmachine_python": "/usr/bin/python3", "seed": SEED}


def test_manifests_are_registered_and_bounded():
    exchange, _ = BUILTINS["organ.exchange"]
    status, _ = BUILTINS["organ.status"]
    assert exchange.consequence_class == "internal_write" and exchange.target_prefix == "organ:"
    assert exchange.network == "none" and exchange.filesystem == "workspace-write"
    assert status.consequence_class == "read_only" and status.retry_safe


@pytest.mark.parametrize("change, why", [
    ({"seed": ""}, "seed"), ({"seed": "x" * 2001}, "seed"),
    ({"daleobanks_root": "/etc"}, "outside permitted roots"),
    ({"daleobanks_python": "python3"}, "absolute"),
])
def test_exchange_refuses_out_of_scope_or_malformed_requests(tmp_path, journal, change, why):
    params = fake_checkouts(tmp_path)
    with pytest.raises(CapabilityError, match=why):
        organs.exchange({**params, **change}, ctx(tmp_path, journal, roots=(tmp_path, Path("/usr/bin"))))


def test_interpreter_outside_read_roots_is_refused(tmp_path, journal):
    with pytest.raises(CapabilityError, match="outside permitted roots"):
        organs.exchange(fake_checkouts(tmp_path), ctx(tmp_path, journal, roots=(tmp_path,)))


def test_exchange_belongs_to_one_mission(tmp_path, journal):
    with pytest.raises(CapabilityError, match="one mission"):
        organs.exchange(fake_checkouts(tmp_path), ctx(tmp_path, journal, roots=(tmp_path,), mission_id=""))


def test_trace_is_stable_per_mission_and_seed():
    assert organs.trace_for("m:a", "s") == organs.trace_for("m:a", "s") != organs.trace_for("m:b", "s")


def test_status_reports_nothing_before_any_exchange(tmp_path, journal):
    out = organs.status({}, ctx(tmp_path, journal, capability="organ.status"))
    assert out == {"organs_observed": [], "messages": 0, "transport_verified": False, "trace_ids": [],
                   "verdict": None, "appraisals": 0, "bound_to_receipts": [], "founder_reconciled": False,
                   "unbound_facts_ignored": 0}


def register(journal, mission_id):
    journal.record("mission.registered", {"mission_id": mission_id, "spec": {"strategies": [
        {"action_id": "organs", "capability": "organ.exchange"}]}}, key=[mission_id, "registered"])


def finish(journal, mission_id, output=None, *, status="DONE", reconciled=False, action_id="organs", attempt=0,
           capability="organ.exchange"):
    """What the engine records after the Gate: a DONE action and its receipt, or (``reconciled``) the
    UNCERTAIN dispatch and the founder's reconciliation of that same attempt."""
    base = {"mission_id": mission_id, "action_id": action_id, "attempt": attempt, "capability": capability}
    if reconciled:
        journal.record("mission.action", {**base, "status": "UNCERTAIN", "receipt": None},
                       key=[mission_id, action_id, attempt])
    receipt = None if reconciled else journal.ledger.append("receipt", {"result": {"output": output}}).hash
    journal.record("mission.action", {**base, "status": status, "receipt": receipt,
                                      "route": "founder_reconciliation" if reconciled else None},
                   key=[mission_id, action_id, attempt, status, receipt or "reconciled"])


def bridge_message(journal, mission_id, body=b'{"id": "p1"}'):
    headers = bt.build_headers(body, identity="daleobanks", schema_version="1.1", idempotency_key="p1",
                               trace_id="trace-" + mission_id)
    return organ_bridge.record_exchange(journal, mission_id=mission_id, headers=headers, body=body,
                                        nonce_cache=bt.NonceCache(), expected_sender="daleobanks",
                                        expected_operation="opportunity.evaluate")


def test_status_reads_only_this_missions_facts(tmp_path, journal, monkeypatch):
    monkeypatch.setenv(bt.SIGNING_KEY_ENV, "k" * 64)
    register(journal, "m:other")
    seen = bridge_message(journal, "m:other")
    finish(journal, "m:other", {"packet_sha256": seen["content_sha256"], "assessment_sha256": "a" * 64})
    mine = organs.status({}, ctx(tmp_path, journal, capability="organ.status"))
    theirs = organs.status({}, ctx(tmp_path, journal, capability="organ.status", mission_id="m:other"))
    assert mine["messages"] == 0 and theirs["messages"] == 1 and theirs["transport_verified"] is True


def test_facts_from_an_exchange_that_never_completed_do_not_count(tmp_path, journal, monkeypatch):
    """Attack (review finding): the body dies after the adapter recorded organ facts and a REPRODUCED
    appraisal but before the Gate's receipt; the founder reconciles the dispatch as not executed.
    Those facts must not satisfy organ.status or the sandbox metric."""
    monkeypatch.setenv(bt.SIGNING_KEY_ENV, "k" * 64)
    mid = "m:organ-test"
    register(journal, mid)
    seen = bridge_message(journal, mid)
    judged = {"trace_id": "t", "packet_sha256": seen["content_sha256"], "assessment_sha256": "a" * 64,
              "redo_sha256": "r" * 64}
    organ_bridge.record_appraisal(journal, mission_id=mid, appraiser="kernel-organ-appraiser",
                                  reproduced={"go_no_go": True}, invariants={"x": True}, exchange=judged)
    finish(journal, mid, status="RECONCILED_NOT_EXECUTED", reconciled=True)
    out = organs.status({}, ctx(tmp_path, journal, capability="organ.status"))
    assert out["verdict"] is None and out["messages"] == 0 and out["unbound_facts_ignored"] == 2
    finish(journal, mid, {"packet_sha256": seen["content_sha256"], "assessment_sha256": "a" * 64})
    out = organs.status({}, ctx(tmp_path, journal, capability="organ.status"))
    assert out["verdict"] == "REPRODUCED" and out["messages"] == 1 and len(out["bound_to_receipts"]) == 1


def test_a_founder_reconciled_executed_dispatch_vouches_for_its_facts(tmp_path, journal, monkeypatch):
    monkeypatch.setenv(bt.SIGNING_KEY_ENV, "k" * 64)
    mid = "m:organ-test"
    register(journal, mid)
    bridge_message(journal, mid)
    finish(journal, mid, reconciled=True)          # the founder said it executed: the founder's authority
    out = organs.status({}, ctx(tmp_path, journal, capability="organ.status"))
    assert out["messages"] == 1 and out["founder_reconciled"] is True


def test_appraisals_of_different_exchanges_never_collapse(journal):
    """A REFUTED, a REPRODUCED and a differing REFUTED are three facts, each naming its exchange."""
    mid = "m:organ-test"
    verdicts = []
    for i, ok in enumerate((False, True, False)):
        judged = {"trace_id": "t", "packet_sha256": f"{i}" * 64, "assessment_sha256": "a" * 64,
                  "redo_sha256": "r" * 64}
        verdicts.append(organ_bridge.record_appraisal(journal, mission_id=mid, appraiser="k",
                                                      reproduced={"go_no_go": ok}, invariants={}, exchange=judged))
    recorded = [e.payload for e in journal.replay("organ.appraised")]
    assert [r["verdict"] for r in recorded] == ["REFUTED", "REPRODUCED", "REFUTED"]
    assert all(r["exchange"]["packet_sha256"] for r in recorded)


def git_checkouts(tmp_path):
    """fake_checkouts committed to git, so the exchange can snapshot each organ's HEAD."""
    params = fake_checkouts(tmp_path)
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "GIT_CONFIG_NOSYSTEM": "1"}
    for root in (params["daleobanks_root"], params["wealthmachine_root"]):
        for cmd in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "c"]):
            subprocess.run(["git", "-C", root, *cmd], check=True, capture_output=True, env=env)
    return params


PACKET = '{"id": "p1", "schema_version": "1.1", "created_at": "2026-10-14T00:00:00Z"}'


def message(trace, identity="daleobanks"):
    return {"body": PACKET, "headers": {bt.H_TRACE: trace, "X-Schema-Version": "1.1", "identity": identity}}


def test_an_organ_that_rewrites_the_other_organs_code_is_refused(tmp_path, journal, monkeypatch):
    """Attack (review finding): organ processes share the body's UID and filesystem, so the DALEOBANKS
    stage rewrites WealthMachine's code and both WealthMachine runs would execute it, making
    REPRODUCED meaningless. Expected: the WealthMachine snapshot digest no longer matches; refused
    before WealthMachine runs and before anything is recorded."""
    params = git_checkouts(tmp_path)
    calls = []

    def stage(python, cwd, code, *args, stdin=None, env, timeout, confine=None, stop_check=None):
        calls.append(cwd.name)
        (cwd.parent / "wealthmachine" / "src" / "services" / "opportunity_intake.py").write_text("FORGED = 1\n")
        return message(organs.trace_for("m:organ-test", SEED))

    monkeypatch.setattr(organs, "_stage", stage)
    with pytest.raises(CapabilityError, match="snapshot changed while DALEOBANKS ran"):
        organs.exchange(params, ctx(tmp_path, journal, roots=(tmp_path, Path("/usr/bin"))))
    assert calls == ["daleobanks"] and journal.replay("organ.") == []
    assert (Path(params["wealthmachine_root"]) / "src/services/opportunity_intake.py").read_text() == ""


def test_an_organ_that_signs_another_trace_is_refused_before_recording(tmp_path, journal, monkeypatch):
    params = git_checkouts(tmp_path)
    monkeypatch.setattr(organs, "_stage", lambda *a, **k: message("trace-elsewhere"))
    with pytest.raises(CapabilityError, match="not the assigned"):
        organs.exchange(params, ctx(tmp_path, journal, roots=(tmp_path, Path("/usr/bin"))))
    assert journal.replay("organ.") == []


def test_the_snapshot_runs_head_and_reports_uncommitted_edits(tmp_path):
    params = git_checkouts(tmp_path)
    wmi = Path(params["wealthmachine_root"])
    (wmi / "src/services/opportunity_intake.py").write_text("UNCOMMITTED = 1\n")
    snap = organs._snapshot(wmi, tmp_path / "snap")
    assert snap["uncommitted_changes_ignored"] is True
    assert (snap["path"] / "src/services/opportunity_intake.py").read_text() == ""
    assert snap["head"] == organs._head(wmi)



def require_landlock():
    """Landlock is what makes an organ stage's confinement true. Where it is required (CI's Landlock and
    one-machine jobs) its absence fails the test: a skip there would be a silent pass."""
    from greg import isolation
    support = isolation.available()
    if not support.get("available"):
        if "1" in (os.environ.get("GREG_REQUIRE_LANDLOCK"), os.environ.get("UNIIMENTE_REQUIRE_ORGANS")):
            pytest.fail(f"Landlock is required here and unavailable: {support}")
        pytest.skip("Landlock unavailable on this host")

NETWORK_PROBE = "import socket\ntry:\n    socket.socket()\n    print('NETWORK OPEN')\nexcept OSError:\n    print('denied')\n"


@pytest.mark.skipif(sys.platform != "linux", reason="seccomp network filter is Linux")
def test_a_child_that_rewrites_the_network_filter_cannot_disable_isolation_for_later_children(tmp_path,
                                                                                             monkeypatch):
    """Attack (review finding, critical): an isolated child cannot open sockets but can write files.
    It replaces tools/offline_test.py with a no-op filter; the next isolated child used to import that
    file at fork time and ran with full network. Expected: the filter is the one already in the
    body's memory; the next child is still denied."""
    from greg import capabilities
    kernel = tmp_path / "kernel"
    (kernel / "tools").mkdir(parents=True)
    (kernel / "tools" / "offline_test.py").write_text((capabilities.KERNEL_ROOT / "tools" / "offline_test.py").read_text())
    monkeypatch.setattr(capabilities, "KERNEL_ROOT", kernel)
    tamper = f"open({str(kernel / 'tools' / 'offline_test.py')!r}, 'w').write('def install_filter():\\n    pass\\n')"
    first = capabilities.run_isolated([sys.executable, "-c", tamper], cwd=tmp_path)
    assert first.returncode == 0 and "pass" in (kernel / "tools" / "offline_test.py").read_text()
    second = capabilities.run_isolated([sys.executable, "-c", NETWORK_PROBE], cwd=tmp_path)
    assert second.stdout.decode().strip() == "denied"


def confined_probe(tmp_path, code):
    from greg import capabilities
    require_landlock()
    python = Path(sys.executable)
    own, other, kernel, store = (tmp_path / n for n in ("own", "other", "kernel", "store"))
    for d in (own, other, kernel, store):
        d.mkdir()
        (d / "f.txt").write_text(d.name)
    confine = organs._confinement(python, own, store)
    return capabilities.run_isolated([str(python), "-s", "-c", code], cwd=own, confine=confine,
                                     extra_env={"PYTHONDONTWRITEBYTECODE": "1"})


def test_a_confined_organ_stage_reaches_only_its_code_and_the_store(tmp_path):
    """Attack (review finding): organ stages wrote anywhere (another organ's code, Kernel sources,
    the body's home). Expected under Landlock: its own code readable, the store writable, nothing
    else readable or writable."""
    root = str(tmp_path)
    code = ("import json, pathlib\nr = {}\n"
            f"base = pathlib.Path({root!r})\n"
            "for name, act in (('read_own', lambda: (base/'own'/'f.txt').read_text()),\n"
            "                  ('write_store', lambda: (base/'store'/'x').write_text('ok')),\n"
            "                  ('read_other', lambda: (base/'other'/'f.txt').read_text()),\n"
            "                  ('write_other', lambda: (base/'other'/'x').write_text('no')),\n"
            "                  ('write_kernel', lambda: (base/'kernel'/'f.txt').write_text('no')),\n"
            "                  ('write_own', lambda: (base/'own'/'x').write_text('no'))):\n"
            "    try:\n        act(); r[name] = True\n    except OSError:\n        r[name] = False\n"
            "print(json.dumps(r))\n")
    proc = confined_probe(tmp_path, code)
    assert proc.returncode == 0, proc.stderr.decode()
    reached = json.loads(proc.stdout.decode().strip().splitlines()[-1])
    assert reached == {"read_own": True, "write_store": True, "read_other": False, "write_other": False,
                       "write_kernel": False, "write_own": False}
    assert (tmp_path / "kernel" / "f.txt").read_text() == "kernel"


def test_founder_stop_ends_an_in_flight_organ_exchange(tmp_path, journal, monkeypatch):
    """Review finding: STOP could not end an organ exchange (three blocking stages of up to 900 s).
    Expected: the stage is supervised; STOP kills it within a second and nothing is recorded."""
    import time as _time
    params = git_checkouts(tmp_path)
    monkeypatch.setattr(organs, "DALEOBANKS_STAGE", "import time\ntime.sleep(60)\n")
    started = _time.monotonic()
    c = ctx(tmp_path, journal, roots=(tmp_path, Path("/usr/bin")))
    c.stop_check = lambda: _time.monotonic() - started > 0.5
    with pytest.raises(CapabilityError, match="STOP"):
        organs.exchange(params, c)
    assert _time.monotonic() - started < 10 and journal.replay("organ.") == []


def test_a_mission_keeps_its_bound_trace_for_a_second_seed(tmp_path, journal, monkeypatch):
    monkeypatch.setenv(bt.SIGNING_KEY_ENV, "k" * 64)
    bridge_message(journal, "m:organ-test")                 # bound to trace-m:organ-test
    seen = []

    def stage(python, cwd, code, *args, **kw):
        seen.append(args)
        raise CapabilityError("stop here")

    monkeypatch.setattr(organs, "_stage", stage)
    with pytest.raises(CapabilityError, match="stop here"):
        organs.exchange({**git_checkouts(tmp_path), "seed": "another seed"},
                        ctx(tmp_path, journal, roots=(tmp_path, Path("/usr/bin"))))
    assert seen[0][1] == "trace-m:organ-test"


@pytest.mark.parametrize("reply, why", [
    ({"headers": {}}, "signed trace None"),                                 # no trace at all
    ("no-body", "KeyError"),                                                 # malformed: becomes a refusal
    ("bad-packet", "broke its wire contract"),
])
def test_malformed_or_off_contract_organ_output_is_a_clean_refusal(tmp_path, journal, monkeypatch, reply, why):
    trace = organs.trace_for("m:organ-test", SEED)
    replies = {"no-body": {"headers": {bt.H_TRACE: trace}}, "bad-packet": message(trace)}
    monkeypatch.setattr(organs, "_stage", lambda *a, **k: replies.get(reply, reply) if isinstance(reply, str) else reply)
    with pytest.raises(CapabilityError, match=why):
        organs.exchange(git_checkouts(tmp_path), ctx(tmp_path, journal, roots=(tmp_path, Path("/usr/bin"))))
    assert journal.replay("organ.") == []


def test_live_exchange_never_signs_as_an_organ_when_per_organ_keys_are_configured(tmp_path, journal, monkeypatch):
    """Review finding: with UNIIMENTE_BRIDGE_KEY_DALEOBANKS in the body's environment, the Kernel signed
    the re-derivation request as DALEOBANKS's isolated identity and the organ refused it. Expected:
    the re-derivation reuses DALEOBANKS's own signed message; the exchange still reproduces."""
    params = live_organs()
    monkeypatch.setenv("UNIIMENTE_BRIDGE_KEY_DALEOBANKS", "d" * 64)
    out = organs.exchange({**params, "seed": SEED}, ctx(tmp_path, journal, roots=organ_roots(params)))
    assert out["appraisal_verdict"] == "REPRODUCED"


def test_live_exchange_runs_real_organ_code_and_reproduces(tmp_path, journal):
    params = live_organs()
    out = organs.exchange({**params, "seed": SEED}, ctx(tmp_path, journal, roots=organ_roots(params)))
    assert out["appraisal_verdict"] == "REPRODUCED" and out["transport_verified"] is True
    assert out["assessment"]["requires_human_approval"] is True
    assert out["sender_identity_isolated"] is False          # pinned organs share one key: stated, not hidden
    assert out["external_effects"] is None and out["authority_created"] is False
    status = organs.status({}, ctx(tmp_path, journal, capability="organ.status"))
    assert status["verdict"] is None and status["unbound_facts_ignored"] == 3   # no receipt vouches yet
    register(journal, "m:organ-test")
    finish(journal, "m:organ-test", out)
    status = organs.status({}, ctx(tmp_path, journal, capability="organ.status"))
    assert status["organs_observed"] == ["daleobanks", "wealthmachine"] and status["verdict"] == "REPRODUCED"
    assert journal.replay("mission.observed") == [] and journal.replay("mission.appraised") == []
    from greg import isolation
    for organ in ("daleobanks", "wealthmachine"):          # the code that ran is the code recorded
        assert out["organ_code"][organ]["head"] == out["organ_heads"][organ]
        assert len(out["organ_code"][organ]["tree_sha256"]) == 64
        assert len(out["organ_code"][organ]["interpreter"]["sha256"]) == 64
        assert out["organ_code"][organ]["filesystem_confined"] is bool(isolation.available().get("available"))
    for root in ("daleobanks_root", "wealthmachine_root"):    # the organ checkouts are never written
        import subprocess
        dirty = subprocess.run(["git", "-C", params[root], "status", "--porcelain"], capture_output=True,
                               text=True).stdout
        assert dirty == ""


def test_a_seed_with_no_opportunity_is_a_truthful_answer_not_a_fault(tmp_path, journal):
    """DALEOBANKS judging that a seed holds no opportunity is a correct organ answer: the exchange
    completes with that typed outcome (never counted against the capability as a refusal), sends
    nothing to WealthMachine and records no organ message."""
    params = live_organs()
    out = organs.exchange({**params, "seed": "The weather was pleasant today."},
                          ctx(tmp_path, journal, roots=organ_roots(params)))
    assert out["state"] == "NO_OPPORTUNITY" and out["appraisal_verdict"] is None
    assert journal.replay("organ.observed") == []


@pytest.mark.skipif(sys.platform != "linux", reason="seccomp network filter and Landlock are Linux")
@pytest.mark.parametrize("status, confined", [(97, False), (98, True)])
def test_a_command_that_exits_97_or_98_ran_and_is_not_reported_as_refused(tmp_path, status, confined):
    """Second review (containment 0): the preexec signalled its own failure with exit 97 (network) or 98
    (confinement), so a command that ran, wrote and then exited 97/98 itself was reported as 'command
    refused' and typed transient (never a capability fault). A refusal is now signalled out of band."""
    from greg import capabilities, isolation
    if confined:
        require_landlock()
    marker = tmp_path / "store" / "marker"
    marker.parent.mkdir()
    confine = organs._confinement(Path(sys.executable), tmp_path, marker.parent) if confined else None
    proc = capabilities.run_isolated(
        [sys.executable, "-s", "-c", f"open({str(marker)!r}, 'a').write('ran'); raise SystemExit({status})"],
        cwd=tmp_path, confine=confine)
    assert proc.returncode == status and marker.read_text() == "ran"


@pytest.mark.skipif(sys.platform != "linux", reason="seccomp network filter and Landlock are Linux")
@pytest.mark.parametrize("failing", ["network", "confinement"])
@pytest.mark.parametrize("supervised", [False, True])
def test_isolation_that_cannot_be_installed_refuses_the_command_before_it_runs(tmp_path, monkeypatch, failing,
                                                                              supervised):
    from greg import capabilities, isolation

    def broken(*a, **k):
        raise OSError("unavailable")

    if failing == "network":
        monkeypatch.setattr(capabilities, "_network_filter", lambda: broken)
    else:
        monkeypatch.setattr(isolation, "confine_paths", broken)
    marker = tmp_path / "marker"
    with pytest.raises(CapabilityError, match=f"{'network isolation' if failing == 'network' else 'filesystem'}"
                                              ".* unavailable; command refused") as raised:
        capabilities.run_isolated([sys.executable, "-c", f"open({str(marker)!r}, 'w').write('ran')"], cwd=tmp_path,
                                  confine={"read": [], "read_exec": [], "write": []} if failing == "confinement"
                                  else None, stop_check=(lambda: False) if supervised else None)
    assert raised.value.failure_class == "transient" and not marker.exists()


def test_an_interpreter_outside_a_venv_is_granted_alone_never_its_parent_tree(tmp_path):
    """Second review (containment 1): the grant was python.parent.parent, so an interpreter declared at
    ~/bin/python3 gave the stage read+exec on the whole home (the other organ, the Kernel's sources, the
    body's home) while the receipt said filesystem_confined. The grant now comes from the interpreter."""
    require_landlock()
    home = tmp_path / "home"
    (home / "bin").mkdir(parents=True)
    python = home / "bin" / "python3"
    python.symlink_to(os.path.realpath(sys.executable))
    for name in ("own", "other", "kernel", "store"):
        (home / name).mkdir()
        (home / name / "f.txt").write_text(name)
    confine = organs._confinement(python, home / "own", home / "store", exclude=(home / "other", home / "kernel"))
    assert str(home) not in {str(p) for p in confine["read_exec"]}
    from greg import capabilities
    code = ("import json, pathlib\nr = {}\n"
            f"for n in ('own', 'other', 'kernel'):\n    try:\n        pathlib.Path({str(home)!r}, n, 'f.txt').read_text()"
            "; r[n] = True\n    except OSError:\n        r[n] = False\nprint(json.dumps(r))\n")
    proc = capabilities.run_isolated([str(python), "-s", "-I", "-c", code], cwd=home / "own", confine=confine)
    assert proc.returncode == 0, proc.stderr.decode()
    assert json.loads(proc.stdout.decode().splitlines()[-1]) == {"own": True, "other": False, "kernel": False}


def test_an_interpreter_grant_that_reaches_another_organ_refuses_the_stage(tmp_path):
    require_landlock()
    home = tmp_path / "home"
    (home / "venv" / "bin").mkdir(parents=True)
    (home / "venv" / "pyvenv.cfg").write_text("home = /usr/bin\n")
    python = home / "venv" / "bin" / "python3"
    python.symlink_to(os.path.realpath(sys.executable))
    (home / "venv" / "other-organ").mkdir()                    # the other organ's checkout sits inside the venv
    with pytest.raises(CapabilityError, match="reaches"):
        organs._confinement(python, home / "own", home / "store", exclude=(home / "venv" / "other-organ",))
    assert organs._confinement(python, home / "own", home / "store", exclude=(tmp_path / "elsewhere",))[
        "read_exec"][0] == home / "venv"


@pytest.mark.skipif(sys.platform != "linux", reason="process groups and /proc")
def test_a_supervised_stage_leaves_no_process_behind(tmp_path):
    """Second review (containment 2): the process group was killed only while the leader still ran, so a
    stage that started a background process and exited 0 left it running (writing to the store) through
    the rest of the exchange. Everything left in the stage's process group is now killed when it ends."""
    import time as _time
    from greg import capabilities
    proc = capabilities.run_isolated(
        [sys.executable, "-c", "import subprocess; p = subprocess.Popen(['/bin/sleep', '30']); print(p.pid)"],
        cwd=tmp_path, stop_check=lambda: False)
    left = int(proc.stdout.decode().strip())

    def alive(pid):
        try:
            return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] != "Z"
        except FileNotFoundError:
            return False

    # The group is SIGKILLed when the stage ends; a loaded runner may take a moment to finish the kill. A leftover
    # `sleep 30` outlives any wait here, so the wait bounds only scheduling, never the property.
    deadline = _time.monotonic() + 10
    while alive(left) and _time.monotonic() < deadline:
        _time.sleep(0.05)
    if alive(left):
        try:
            stat = Path(f"/proc/{left}/stat").read_text().rsplit(")", 1)[1].split()
            why = {"state": stat[0], "ppid": stat[1], "pgid": stat[2], "sid": stat[3],
                   "cmdline": Path(f"/proc/{left}/cmdline").read_bytes().replace(b"\0", b" ").decode()[:120]}
        except (FileNotFoundError, IndexError) as exc:
            why = {"gone_while_reading": repr(exc)}
        assert not alive(left), f"a process the stage started is still running: {why}"


def test_a_later_executed_reconciliation_never_vouches_for_facts_the_founder_declared_not_executed(
        tmp_path, journal, monkeypatch):
    """Second review (measurement 0): one mission-wide founder cut admitted every organ fact recorded before
    the latest executed reconciliation, including an earlier dispatch the founder declared NOT executed.
    A founder reconciliation now vouches only for the facts of the dispatch it reconciles."""
    monkeypatch.setenv(bt.SIGNING_KEY_ENV, "k" * 64)
    mid = "m:organ-test"
    journal.record("mission.registered", {"mission_id": mid, "spec": {"strategies": [
        {"action_id": "organs-a", "capability": "organ.exchange"},
        {"action_id": "organs-b", "capability": "organ.exchange"}]}}, key=[mid, "registered"])
    seen = bridge_message(journal, mid)
    organ_bridge.record_appraisal(journal, mission_id=mid, appraiser="k", reproduced={"go_no_go": True},
                                  invariants={}, exchange={"trace_id": "t", "packet_sha256": seen["content_sha256"],
                                                           "assessment_sha256": "a" * 64, "redo_sha256": "r" * 64})
    finish(journal, mid, status="RECONCILED_NOT_EXECUTED", reconciled=True, action_id="organs-a")
    finish(journal, mid, status="REFUSED", action_id="organs-a", attempt=1)
    finish(journal, mid, reconciled=True, action_id="organs-b")        # executed, but it recorded nothing
    out = organs.status({}, ctx(tmp_path, journal, capability="organ.status"))
    assert out["verdict"] is None and out["messages"] == 0 and out["unbound_facts_ignored"] == 2


def test_a_function_named_organ_strategy_binds_its_receipted_facts(tmp_path, journal, monkeypatch):
    """Second review (measurement 1): only strategies naming the capability in the spec were read, so a
    strategy naming a function (resolved to organ.exchange by the engine) bound nothing and its mission
    could never close. The dispatched capability on the action record decides."""
    monkeypatch.setenv(bt.SIGNING_KEY_ENV, "k" * 64)
    mid = "m:organ-test"
    journal.record("mission.registered", {"mission_id": mid, "spec": {"strategies": [
        {"action_id": "organs", "function": "organ.signed_exchange"}]}}, key=[mid, "registered"])
    seen = bridge_message(journal, mid)
    organ_bridge.record_appraisal(journal, mission_id=mid, appraiser="k", reproduced={"go_no_go": True},
                                  invariants={}, exchange={"trace_id": "t", "packet_sha256": seen["content_sha256"],
                                                           "assessment_sha256": "a" * 64, "redo_sha256": "r" * 64})
    finish(journal, mid, {"packet_sha256": seen["content_sha256"], "assessment_sha256": "a" * 64})
    out = organs.status({}, ctx(tmp_path, journal, capability="organ.status"))
    assert out["verdict"] == "REPRODUCED" and out["messages"] == 1


def test_an_appraisal_retained_before_it_named_its_exchange_binds_to_its_own_receipt(tmp_path, journal,
                                                                                     monkeypatch):
    """Second review (measurement 3): appraisals recorded before they named their exchange were dropped
    although the DONE receipt that immediately follows them carries the digests. Such an appraisal binds
    to the receipted dispatch it was recorded in, and is reported as a legacy binding."""
    monkeypatch.setenv(bt.SIGNING_KEY_ENV, "k" * 64)
    mid = "m:organ-test"
    register(journal, mid)
    seen = bridge_message(journal, mid)
    organ_bridge.record_appraisal(journal, mission_id=mid, appraiser="k", reproduced={"go_no_go": True},
                                  invariants={})
    finish(journal, mid, {"packet_sha256": seen["content_sha256"], "assessment_sha256": "a" * 64})
    out = organs.status({}, ctx(tmp_path, journal, capability="organ.status"))
    assert out["verdict"] == "REPRODUCED" and out["unbound_facts_ignored"] == 0



def test_an_excluded_tree_under_a_fixed_system_grant_refuses_the_stage(tmp_path):
    """Third review (containment): only the interpreter grants were checked against the excluded trees, so an
    organ checked out under /usr stayed readable through the fixed /usr grant while the receipt said
    confined. Every grant is checked now."""
    require_landlock()
    venv = tmp_path / "venv"
    (venv / "bin").mkdir(parents=True)
    (venv / "pyvenv.cfg").write_text("home = /opt/python/bin\n")
    (venv / "bin" / "python3").write_text("")                       # never run: only its grants are computed
    with pytest.raises(CapabilityError, match="reaches /usr/share"):
        organs._confinement(venv / "bin" / "python3", tmp_path / "own", tmp_path / "store",
                            exclude=(Path("/usr/share"),))
