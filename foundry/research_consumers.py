"""Local compute adapters to existing consumers, isolated by child process.

Only the existing synchronous evaluator and draft refinery are called.
The authenticated production bridge remains the sole cross-service ingress.
"""
from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from adapters.contract_validation import validate_contract

ASSESS = """
import contextlib, json, sys
with contextlib.redirect_stdout(sys.stderr):
    from src.services.opportunity_intake import OpportunityIntakeService
    result = OpportunityIntakeService().evaluate_packet(json.load(sys.stdin))
print(json.dumps(result))
"""
DRAFT = """
import asyncio, contextlib, json, sys
from dataclasses import asdict
with contextlib.redirect_stdout(sys.stderr):
    from db.session import init_db, get_db_session
    from services.idea_refinery import IdeaRefinery, check_educational
    from services.ledger import DecisionLedger
    data = json.load(sys.stdin)
    init_db()
    refinery = IdeaRefinery(ledger=DecisionLedger('draft-decisions.jsonl'))
    with get_db_session() as session:
        idea = refinery.intake(session, data['text'])
        result = asyncio.run(refinery.refine(session, idea))
    drafts = []
    for draft in result['drafts']:
        if check_educational(draft.draft_text + ' ' + draft.script):
            raise ValueError('consumer draft failed its educational guard')
        draft.source_opportunity_packet_id = data['packet_id']
        draft.approval_status = 'pending'
        drafts.append(asdict(draft))
    if not refinery.ledger.verify_chain()[0]:
        raise ValueError('consumer decision chain failed verification')
    records = refinery.ledger.entries()
print(json.dumps({'drafts': drafts, 'consumer_decisions': records}, default=str))
"""


class SourceConsumer:
    def __init__(self, path, *, role):
        self.path = Path(path).resolve()
        self.role = role
        if role not in ("wmi", "dale"):
            raise ValueError("unknown consumer role")
        required = ("src/services/opportunity_intake.py" if role == "wmi"
                    else "services/idea_refinery.py")
        if not (self.path / required).is_file():
            raise ValueError(f"missing {role} source checkout")
        self.commit = self._git("rev-parse", "HEAD")
        if self._git("status", "--porcelain"):
            raise ValueError(f"{role} checkout has uncommitted changes; use a clean pinned checkout")

    def _git(self, *args):
        return subprocess.run(["git", "-C", str(self.path), *args], check=True,
                              capture_output=True, text=True, timeout=10).stdout.strip()

    def binding(self):
        return {"role": self.role, "path": str(self.path), "commit": self.commit}

    def _call(self, code, payload):
        try:
            supported_dotenv = version("python-dotenv") == "1.2.3"
        except PackageNotFoundError:
            supported_dotenv = False
        if not supported_dotenv:
            raise ValueError("isolated computation requires python-dotenv==1.2.3; install requirements-research-line.txt")
        if self._git("rev-parse", "HEAD") != self.commit or self._git("status", "--porcelain"):
            raise ValueError("consumer source changed after planning")
        raw = json.dumps(payload)
        if len(raw.encode()) > 128 * 1024:
            raise ValueError("consumer input exceeds 128 KiB")
        # Do not inherit provider keys, bridge credentials, database URLs or proxy settings.
        environment = {key: os.environ[key] for key in ("PATH", "LANG", "SYSTEMROOT") if key in os.environ}
        environment.update({
            "PYTHONPATH": os.pathsep.join((str(self.path), str(Path(__file__).resolve().parents[1]))),
            "PYTHONDONTWRITEBYTECODE": "1", "PYTHON_DOTENV_DISABLED": "1",
            "OPENAI_API_KEY": "", "LLM_PROVIDER": "template", "LIVE": "false",
            "PERSIST_STORE": "false", "DATABASE_URL": "sqlite:///:memory:",
        })
        with tempfile.TemporaryDirectory(prefix="egregore-local-compute-") as directory:
            result = subprocess.run([sys.executable, "-c", code], input=raw,
                                    cwd=directory, env=environment, text=True,
                                    capture_output=True, timeout=30)
        if result.returncode:
            # Preserve failure through the parent workflow; avoid copying arbitrary child logs.
            raise ValueError(f"{self.role} local computation failed with exit {result.returncode}")
        if len(result.stdout.encode()) > 1024 * 1024:
            raise ValueError("consumer output exceeds 1 MiB")
        return json.loads(result.stdout)

    def assess(self, packet):
        if self.role != "wmi":
            raise ValueError("WMI source required")
        validate_contract(packet, "wire-opportunity-packet")
        result = self._call(ASSESS, packet)
        validate_contract(result, "wire-venture-assessment")
        if result["opportunity_packet_id"] != packet["id"] or result["requires_human_approval"] is not True:
            raise ValueError("assessment must remain a linked recommendation")
        return result

    def draft(self, packet, analysis):
        if self.role != "dale":
            raise ValueError("DALEOBANKS source required")
        result = self._call(DRAFT, {"packet_id": packet["id"], "text": analysis["thesis"]})
        drafts = result.get("drafts")
        if (not isinstance(drafts, list) or not drafts or len(drafts) > 10
                or any(d.get("approval_status") != "pending"
                       or d.get("source_opportunity_packet_id") != packet["id"] for d in drafts)):
            raise ValueError("consumer drafts must remain linked and pending")
        return result
