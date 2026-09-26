"""Synthetic authority ONLY: submit, detach a finite proof host, exit interface.

Never an installation or founder authentication provider. Run only inside the
reviewed offline test boundary. No grant is created by a worker or on restart.
"""
import json
import os
from pathlib import Path
import sys

from compiler.ucl_compiler import compile_constitution
from egregore.local_mission import ROOT, proposal, submit, supervise
from identity.machine_passport import PassportRegistry
from policy.consequence_gate import ConsequenceGate, GrantIssuer
from provenance.commit_witness import WitnessSigner
from provenance.ledger import EvidenceLedger


def authority(job):
    compiled = compile_constitution(str(ROOT))
    passports = PassportRegistry()
    actor = passports.issue(kind="agent", creator="synthetic-proof-fixture",
        owner_organ="uniimente-kernel", legal_principal="alfonso_lopez",
        declared_capabilities=["repository.audit"], budget_ceiling_usd=0.0,
        consequence_class="read_only")
    grants = GrantIssuer()
    grant = grants.issue_single_action(proposal=proposal(job, actor.passport_id), policy_version="1.0.0")
    return dict(compiled=compiled, passports=passports, grants=grants,
                signer=WitnessSigner(env="development"), actor=actor.passport_id,
                grant_id=grant["grant_id"])


def prepare(path, job, auth):
    ledger = EvidenceLedger(auth["compiled"].constitution_hash, str(path))
    try:
        gate = ConsequenceGate(compiled=auth["compiled"], passports=auth["passports"],
            grants=auth["grants"], signer=auth["signer"], ledger=ledger)
        submit(path, job, gate, actor=auth["actor"])
    finally:
        ledger.close()


if __name__ == "__main__":
    job_path, ledger_path, result_path = map(Path, sys.argv[1:4])
    job = json.loads(job_path.read_text())
    auth = authority(job)
    prepare(ledger_path, job, auth)
    pid = os.fork()
    if pid:
        print(json.dumps({"host_pid": pid, "interface_pid": os.getpid()}), flush=True)
        os._exit(0)
    os.setsid()
    with open(str(result_path) + ".log", "w") as log, open(os.devnull) as empty:
        os.dup2(empty.fileno(), 0)
        os.dup2(log.fileno(), 1)
        os.dup2(log.fileno(), 2)
        try:
            result = supervise(ledger_path, job, auth, crash_first=True)
            temporary = Path(str(result_path) + ".tmp")
            temporary.write_text(json.dumps(result, sort_keys=True))
            temporary.replace(result_path)
        finally:
            os._exit(0)
