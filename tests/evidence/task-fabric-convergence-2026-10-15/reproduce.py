"""The defect, reproduced on a signed body mission before the change (run from the repository root).

``daleobanks_post``: a temporary worker drafts a post from a source through the Task Fabric (``worker.commission``,
document mode, one lease), and DALEOBANKS verifies it before the publish request may run. The worker here is a
scripted test double whose draft drops the source's hedge. A stub DALEOBANKS approves every draft, so what is
measured is GREG's side of the check. Nothing is posted: the publish request is outside the light cone and stops
for a founder decision that is never given.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import textwrap

sys.path.insert(0, os.getcwd())
from greg import templates, workers                                   # noqa: E402
from greg.body import Body                                            # noqa: E402
from tests.greg_fixtures import Clock, drop, make_body, signed       # noqa: E402

SOURCE = ("A study at two depots found the new routing method may reduce delays by 12%. "
          "It did not lower fuel costs. Drivers at Northgate reported fewer missed windows.")
DRAFTS = {"faithful": "A two-depot study found the routing method may cut delays by 12%. Fuel costs did not fall.",
          "hedge dropped": "A two-depot study found the routing method cuts delays by 12%. Fuel costs did not fall.",
          "negation removed": "A two-depot study found the routing method may cut delays by 12%. It lowered fuel costs."}
STUB = {"services/__init__.py": "",
        "services/ethics_guard.py": "class _R:\n    approved, reasons, uncertainty_score = True, [], 0.0\n"
                                    "class EthicsGuard:\n    def validate_text(self, text):\n        return _R()\n",
        "services/critic.py": "class _R:\n    blocking_issues, quality_score = [], 1.0\nclass Critic:\n"
                              "    def analyze_quality(self, text, content_type='reply'):\n        return _R()\n",
        "services/prompt_firewall.py": "class PromptFirewall:\n    def scan(self, text):\n"
                                       "        return {'risk': 0.0, 'patterns': []}\n"}


class Scripted:
    name = "scripted-test-double"

    def __init__(self, files):
        self.files = files

    def available(self):
        return True, ""

    def run(self, order, cwd):
        for rel, text in self.files.items():
            (cwd / rel).write_text(text)
        return workers.WorkerReport(self.name, self.name, 0, 0.1, 0.0, claim={"confidence": 1.0})


def stub(root: Path) -> Path:
    for rel, text in STUB.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text)
    (root / ".venv/bin").mkdir(parents=True)
    os.symlink(sys.executable, root / ".venv/bin/python")
    return root


def run(name: str, files: dict, spec_extra=None) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="greg-fabric-"))
    data = tmp / "data"
    data.mkdir()
    daleobanks = stub(tmp / "daleobanks")
    home, key, body_id, _ = make_body(tmp, read_roots=[data, daleobanks])
    (data / "source.txt").write_text(SOURCE)
    workers.PROVIDERS["scripted"] = Scripted(files)
    spec = templates.daleobanks_post(daleobanks_root=str(daleobanks), source=str(data / "source.txt"),
                                     brief="Summarise the depot study.", order="depot-note", budget_usd=1.0,
                                     max_chars=280, **(spec_extra or {}))
    for s in spec["strategies"]:
        if s["capability"] == "worker.commission":
            s["params"]["provider"] = "scripted"
    drop(home, signed(key, body_id, "MISSION", spec))
    clock, states = Clock(), []
    with Body(home, clock=clock) as body:
        body.boot()
        for _ in range(8):
            clock.advance(30)
            states.append(body.tick()["missions"][0]["state"])
            if states[-1] in ("ACHIEVED", "BLOCKED", "EXHAUSTED", "FAILED"):
                break
        observed = [e.payload for e in body.journal.replay("mission.observed")]
        blockers = [e.payload for e in body.journal.replay("mission.blocked")]
    checks = {}
    for o in observed:
        checks[o["check_id"]] = o["passed"]
    return {"draft": name, "states": states, "checks": checks,
            "blocked_for": [b.get("blocker", {}).get("why") or b.get("why") for b in blockers][-1:]}


if __name__ == "__main__":
    for name, text in DRAFTS.items():
        print(json.dumps(run(name, {"post.txt": text}), sort_keys=True))


def appraise_document(text: str) -> dict:
    """The Task Fabric's own evaluator on a document work order: ``worker.commission`` then ``worker.appraise``."""
    from greg.capabilities import BUILTINS, InvocationContext, SecretBroker
    tmp = Path(tempfile.mkdtemp(prefix="greg-appraise-"))
    (tmp / "source.txt").write_text(SOURCE)

    def ctx(capability):
        return InvocationContext(workspace=tmp / "ws", read_roots=(tmp,), secrets=SecretBroker(tmp / "s.json"),
                                 manifest=BUILTINS[capability][0], mission_id="m:repro", grant_id="grant-repro",
                                 authority_ref="sha256:repro")
    workers.PROVIDERS["scripted"] = Scripted({"post.txt": text})
    params = {"order": "depot-note", "mode": "document", "inputs": [str(tmp / "source.txt")],
              "objective": "Summarise the depot study.", "acceptance": {"output": "post.txt"},
              "allowed_paths": ["post.txt"], "provider": "scripted", "max_budget_usd": 1.0, "timeout_seconds": 60}
    workers.commission(params, ctx("worker.commission"))
    verdict = workers.appraise({"order": "depot-note"}, ctx("worker.appraise"))
    return {k: verdict[k] for k in ("verdict", "findings")}


if __name__ == "__main__":
    for name, text in DRAFTS.items():
        print(json.dumps({"draft": name, "worker.appraise": appraise_document(text)}, sort_keys=True))
