"""Signed canonical Body/console rehearsal with real native mechanisms and laboratory keys.

These signatures authenticate per-test laboratory identities, not Alfonso or a founder device.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
from urllib.error import HTTPError

import pytest

from greg import planner
from greg.body import Body, Layout, status
from greg.console import Console, render_home, render_proposal, serve
from tests.greg_fixtures import make_body, signed
from tests.unit.test_greg_interface import _post
from tests.unit.test_greg_controlled_words import ROUTE, FLOW, LP


def test_cli_controlled_template_executes_the_canonical_runtime_entry_point(tmp_path):
    home, _, _, _ = make_body(tmp_path)
    root = Path(__file__).resolve().parents[2]
    env = {**os.environ, "PYTHONPATH": str(root)}

    def run(*arguments):
        process = subprocess.run([sys.executable, "-m", "greg", "--home", str(home), *arguments],
                                 cwd=root, env=env, capture_output=True, text=True, timeout=30)
        assert process.returncode == 0, process.stderr
        return process.stdout

    key_args = ("--key", str(tmp_path / "founder.pem"), "--no-passphrase")
    run("mission", "new", "network-in-words", "--text", FLOW, *key_args)
    run("run", "--max-ticks", "1")
    with Body(home) as body:
        assert body.journal.replay("decision.requested")[-1].payload["kind"] == "CAPABILITY_ATTACH"
        assert not body.journal.replay("mission.achieved")
    run("attach", "cognition.flow", *key_args)
    run("run", "--max-ticks", "1")
    snapshot = json.loads(run("status"))
    assert any(g["achieved"] for g in snapshot["goals"])
    with Body(home) as body:
        appraisal = body.journal.replay("mission.appraised")[-1].payload
        assert appraisal["verdict"] == "VERIFIED", appraisal["findings"]
        assert all(r.payload["result"].get("output", {}).get("authority_created") is False
                   for r in body.ledger.by_type("receipt"))


@pytest.mark.parametrize("text,capability,proof,field,expected", [
    (ROUTE, "cognition.graph", "search_trace", "cost", 5),
    (FLOW, "cognition.flow", "flow_certificate", "value", 4),
    (LP, "cognition.linear", "linear_program_certificate", "objective_value", 11),
])
def test_words_wait_for_signed_attachment_then_execute_verify_and_survive_restart(tmp_path, text, capability, proof, field, expected):
    if capability == "cognition.linear":
        pytest.importorskip("ortools")
    home, key, body_id, _ = make_body(tmp_path)
    console = Console(home, key=key)
    pid = console.ask(text)
    proposal = console.proposals[pid]["proposal"]
    assert proposal["status"] == "PROPOSED", proposal
    spec = proposal["spec"]
    review = render_proposal(console, pid).decode()
    assert "Check GREG's reading" in review and "Unit scope:" in review and "Clause 4:" in review
    assert "real-world suitability still needs evidence" in review
    console.sign_proposal(pid)
    with Body(home) as body:
        body.boot()
        body.tick()
        assert body.registry.state[capability] == "VERIFIED"
        assert not body.journal.replay("mission.achieved")
    request = next(r for r in status(home)["decisions_required"] if r["kind"] == "CAPABILITY_ATTACH")
    assert any(c["capability_id"] == capability and c["state"] == "VERIFIED" for c in request["evidence"]["registered"])
    page = render_home(console).decode()
    assert "Attach " + capability in page and "separate signed" in page
    # Real loopback HTTP writes a signed command; it does not mutate registry state itself.
    server = serve(console, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        for fields, origin, code in [({"csrf": "forged", "request_id": request["request_id"], "capability_id": capability}, None, 403),
                                    ({"csrf": console.csrf, "request_id": request["request_id"], "capability_id": capability}, "https://evil.example", 403),
                                    ({"csrf": console.csrf, "request_id": request["request_id"], "capability_id": "fs.write"}, None, 400)]:
            with pytest.raises(HTTPError) as exc:
                _post(port, "/attach", fields, origin=origin)
            assert exc.value.code == code
        _post(port, "/attach", {"csrf": console.csrf, "request_id": request["request_id"], "capability_id": capability})
    finally:
        server.shutdown()
        server.server_close()
    envelope = json.loads(next(Layout(home).inbox.glob("*-capability_attach-*.json")).read_text())
    assert envelope["kind"] == "CAPABILITY_ATTACH" and envelope["body"]["capability_id"] == capability
    with Body(home) as body:
        body.boot()
        body.tick()
        assert body.registry.state[capability] == "ATTACHED"
        # A tick appends its result to canonical history; the next tick rebuilds
        # the cached book. Inspect the post-tick projection, not its input cache.
        body.engine.book.rebuild()
        state = body.engine.book.missions[spec["mission_id"]]
        assert state.status == "ACHIEVED", state.blocker
        receipts = [r.payload["result"]["output"] for r in body.ledger.by_type("receipt") if isinstance(r.payload.get("result", {}).get("output"), dict)
                    and r.payload["result"]["output"].get("problem_id") == spec["success_checks"][0]["sensor"]["params"]["problem_id"]]
        assert receipts and all(r["output"][field] == expected for r in receipts)
        assert all(r["proof_type"] == proof and r["evaluator_result"]["verdict"] == "STRUCTURALLY_VERIFIED" for r in receipts)
        assert all(r["authority_created"] is False and r["empirical_validity"] == "WORLD_UNVERIFIED" for r in receipts)
        assert body.journal.replay("mission.appraised")[-1].payload["verdict"] == "VERIFIED"
        count = len(body.ledger.by_type("receipt"))
        body.apply(signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": capability}))
    with Body(home) as body:
        body.boot()
        body.tick()
        assert body.registry.state[capability] == "DETACHED"
        assert len(body.ledger.by_type("receipt")) == count
    with pytest.raises(ValueError):
        console.attach(request["request_id"], capability)


def test_stale_attach_evidence_and_keyless_console_cannot_attach(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    console = Console(home, key=key)
    console.sign_proposal(console.ask(FLOW))
    with Body(home) as body:
        body.boot()
        body.tick()
    request = next(r for r in status(home)["decisions_required"] if r["kind"] == "CAPABILITY_ATTACH")
    with pytest.raises(PermissionError):
        Console(home).attach(request["request_id"], "cognition.flow")
    with Body(home) as body:
        body.apply(signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": "cognition.flow"}))
    with pytest.raises(ValueError):
        console.attach(request["request_id"], "cognition.flow")


def test_lp_infeasibility_without_certificate_blocks_truthfully(tmp_path):
    pytest.importorskip("ortools")
    text = "Maximize x + y. x + y >= 3. x between 0 and 1. y between 0 and 1."
    home, key, body_id, _ = make_body(tmp_path)
    proposal = planner.propose(text, Console(home).context())
    with Body(home) as body:
        body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": "cognition.linear"}))
        body.apply(signed(key, body_id, "MISSION", proposal["spec"]))
        body.boot()
        body.tick()
        assert body.engine.book.missions[proposal["spec"]["mission_id"]].status != "ACHIEVED"
        receipts = [r.payload["result"].get("output") for r in body.ledger.by_type("receipt")]
        records = [r for r in receipts if isinstance(r, dict) and r.get("method") == "cognition.linear"]
        assert records and all(r["output"]["solver_status"] == "INFEASIBLE" for r in records)
        assert all(r["abstention_state"] != "NONE" for r in records)
        assert all(r["proof_artifact"]["infeasibility_certificate"] is None for r in records)
