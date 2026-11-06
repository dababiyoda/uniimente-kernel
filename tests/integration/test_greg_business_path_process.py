"""One business path on an actual Body process, with a hard restart after N3.

The driver supplies fictional customer evidence and a throwaway signing key.
It never ticks a Body, changes the clock, or writes journal events. The process
runs the same CLI loop the installed product runs. This is not founder use or
a commercial outcome, and it must never advance the founder's path.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from greg import path as devpath, rehearsal, sop, venture_books
from greg.body import Body, init_body, observe, send_signed
from greg.founder import generate_founder_key, load_founder_key
from greg.metrics import REHEARSAL_BODY

ROOT = Path(__file__).resolve().parents[2]


def events(home, prefix):
    with observe(home, actor="spiffe://uniimente.internal/greg/business-path-observer") as journal:
        return list(journal.replay(prefix))


def start(home, log):
    with log.open("a") as output:
        return subprocess.Popen(
            [sys.executable, "-m", "greg", "--home", str(home), "run", "--tick-seconds", "0.1"],
            cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT)},
            stdout=output, stderr=subprocess.STDOUT,
        )


def stop(process, sig=signal.SIGTERM):
    if process.poll() is None:
        process.send_signal(sig)
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)


def wait_for(process, log, predicate, what, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        assert process.poll() is None, log.read_text()[-4000:]
        value = predicate()
        if value:
            return value
        time.sleep(0.1)
    raise AssertionError(f"timed out: {what}\n{log.read_text()[-4000:]}")


def short_payment_refused(home, mid, reference):
    with observe(home, actor="spiffe://uniimente.internal/greg/business-path-observer") as journal:
        refused_receipts = {
            r.hash for r in journal.ledger.by_type("receipt")
            if (out := r.payload.get("result", {}).get("output", {})).get("matched") is False
            and out.get("expected", {}).get("reference") == reference
            and any(row.get("amount") == "0.01" for row in out.get("near_misses", []))
        }
        return any(e.payload["mission_id"] == mid and e.payload["check_id"] == "paid"
                   and e.payload["passed"] is False and e.payload["receipt"] in refused_receipts
                   for e in journal.replay("mission.observed"))


def run_case(home, key, process, log, spec, *, reject_short_payment=False):
    mid = spec["mission_id"]
    folder = home / "workspace" / mid.replace(":", "_")
    payment = spec["success_checks"][2]["sensor"]["params"]
    reference, amount = payment["reference"], payment["amount"]
    steps = {
        "human.send_offer": ("acceptance.txt", f"accepted {reference}\n"),
        "human.collect_payment": (
            "statement.csv", rehearsal.STATEMENT_HEADER + f"2026-10-02,Pay {reference},{amount},USD\n"),
        "human.deliver": ("delivery.txt", f"delivered {reference}\n"),
        "human.confirm_outcome": ("outcome.txt", f"confirmed {reference}\n"),
    }
    handled = set()
    send_signed(home, key, "MISSION", spec)

    def drive():
        # Only the signed decisions and customer's local deliverables come from
        # this driver. Registration, actions, appraisal and learning are the Body's.
        for event in events(home, "decision.requested"):
            ask = event.payload
            if ask["mission_id"] != mid or ask["request_id"] in handled:
                continue
            if ask["kind"] == "APPROVAL":
                send_signed(home, key, "DECISION", {"request_id": ask["request_id"], "answer": "approve"})
            elif ask["kind"] == "HUMAN_WORK":
                name, content = steps[ask["evidence"]["function"]]
                assert not (folder / name).exists(), "a human step must not be requested twice"
                folder.mkdir(parents=True, exist_ok=True)
                temporary = folder / (name + ".pending")
                if name == "statement.csv" and reject_short_payment:
                    temporary.write_text(rehearsal.STATEMENT_HEADER +
                                         f"2026-10-02,Pay {reference},0.01,USD\n")
                    temporary.replace(folder / name)
                    wait_for(process, log, lambda: short_payment_refused(home, mid, reference),
                             "short payment refused from its own receipt")
                    assert not (folder / "settlement.md").exists()
                    assert not any(e.payload["mission_id"] == mid for e in events(home, "mission.achieved"))
                    assert not any(e.payload["mission_id"] == mid
                                   and e.payload.get("evidence", {}).get("function") == "human.deliver"
                                   for e in events(home, "decision.requested"))
                temporary.write_text(content)
                temporary.replace(folder / name)
            else:
                raise AssertionError(f"unexpected decision for {mid}: {ask}")
            handled.add(ask["request_id"])
        return [e for e in events(home, "mission.appraised") if e.payload["mission_id"] == mid]

    [appraisal] = wait_for(process, log, drive, f"verified case {mid}")
    assert appraisal.payload["verdict"] == "VERIFIED", appraisal.payload
    [achieved] = [e for e in events(home, "mission.achieved") if e.payload["mission_id"] == mid]
    send_signed(home, key, "CRITIQUE", {
        "target_event_id": achieved.event_id, "verdict": "accept", "evidence_type": "founder_judgment",
        "text": "[REHEARSAL] fictional customer acceptance, not founder-tier evidence",
    })
    wait_for(process, log,
             lambda: any(e.payload.get("target_event_id") == achieved.event_id
                         for e in events(home, "critique.")), f"acceptance recorded for {mid}")
    return mid


def measurement(home):
    with observe(home, actor="spiffe://uniimente.internal/greg/business-path-observer") as journal:
        return rehearsal._measure(journal)


def test_business_path_runs_in_one_body_process_and_survives_restart(tmp_path):
    home, keyfile, log = tmp_path / "body", tmp_path / "REHEARSAL-key.pem", tmp_path / "body.log"
    init_body(home, read_roots=[str(ROOT)])
    rehearsal.mark_body(home)
    public = generate_founder_key(keyfile, None)
    key = load_founder_key(keyfile, None)
    # Setup only. After this point, only the child owns the writable Body.
    with Body(home) as body:
        body.enroll_founder(public)
    send_signed(home, key, "BODY_DESIGNATE", {"purpose": "first_founder_body"})
    process = start(home, log)
    all_missions = []
    try:
        wait_for(process, log, lambda: events(home, "body.booted"), "first boot")
        all_missions.append(run_case(home, key, process, log,
                                     rehearsal._case_spec(home, 0, "leases", approve_writes=True),
                                     reject_short_payment=True))
        n3 = measurement(home)
        assert [n for n in rehearsal.PATH_NODES if n3[n]["structurally_met"]] == ["N3"]
        first_pid = process.pid
        stop(process, signal.SIGKILL)
        process = start(home, log)
        assert process.pid != first_pid
        wait_for(process, log, lambda: events(home, "body.recovered"), "recovery after N3")
        assert measurement(home) == n3

        for n in (1, 2):
            all_missions.append(run_case(home, key, process, log,
                                         rehearsal._case_spec(home, n, "leases", approve_writes=True)))
        proposals = wait_for(process, log, lambda: events(home, "sop.proposed"), "learned procedure")
        assert len(proposals) == 1
        procedure_id = proposals[0].payload["procedure_id"]
        send_signed(home, key, "SOP_RATIFY", {
            "procedure_id": procedure_id, "pre_approve": ["draft-offer", "record-settlement"],
        })

        def ratified():
            with observe(home, actor="spiffe://uniimente.internal/greg/business-path-observer") as journal:
                return sop.ratified(journal).get(procedure_id)

        record = wait_for(process, log, ratified, "signed ratification")["record"]
        for n in (1, 2, 3):
            spec = sop.instantiate(record, {
                "reference": f"CASE-AUDIT-{n:02d}", "buyer": f"Audit client {n}",
                "offer": f"an audit memo {n}", "price": "300.00", "acceptance": "memo within 5 business days",
            }, venture="audits", now=datetime.now(timezone.utc))
            assert spec["founder_expression"].startswith(rehearsal.LABEL)
            all_missions.append(run_case(home, key, process, log, spec))
        n4 = measurement(home)
        assert [n for n in rehearsal.PATH_NODES if n4[n]["structurally_met"]] == ["N3", "N4"]

        tiers = venture_books.load_waterfall()
        send_signed(home, key, "TREASURY_REQUIREMENTS", {
            "venture": "audits", "currency": "USD", "requirements": {tiers[0]: "120", tiers[3]: "80"},
        })
        wait_for(process, log, lambda: measurement(home)["N7"]["structurally_met"], "N7 after N4")
    finally:
        stop(process)

    with observe(home, actor="spiffe://uniimente.internal/greg/business-path-observer") as journal:
        assert journal.ledger.verify_chain()[0]
        boots = list(journal.replay("body.booted"))
        assert [e.payload["pid"] for e in boots] == [first_pid, process.pid]
        assert len(journal.replay("body.recovered")) == 1
        achieved = [e.payload["mission_id"] for e in journal.replay("mission.achieved")]
        assert sorted(achieved) == sorted(all_missions) and len(set(achieved)) == 6
        done = [(e.payload["mission_id"], e.payload["action_id"]) for e in journal.replay("mission.action")
                if e.payload["status"] == "DONE"]
        assert sorted(done) == sorted((mid, action) for mid in all_missions
                                     for action in ("draft-offer", "record-settlement"))
        assert not journal.replay("command.rejected")
        # Journal.replay prefixes "greg.": greg.treasury.requirements is the
        # signed bookkeeping input above, not a capital.treasury money event.
        assert not [r for r in journal.ledger.by_type("event")
                    if str(r.payload.get("type", "")).startswith("treasury.")]
        assert all(e.payload["spec"]["founder_expression"].startswith(rehearsal.LABEL)
                   for e in journal.replay("mission.registered"))
        final = rehearsal._measure(journal)
        assert all(row["structurally_met"] and not row["met"] for row in final.values())
        assert set(devpath.venture_compounding(journal)["not_founder_tier"].values()) == {REHEARSAL_BODY}
        assert devpath.position(journal)["achieved"] == ["N0"]
        assert devpath.position(journal)["active"]["id"] == "N1"
