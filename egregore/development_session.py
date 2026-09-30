"""Synthetic development setup only. Not a founder authentication provider."""
import json
import os
from dataclasses import asdict
from pathlib import Path
from compiler.ucl_compiler import compile_constitution
from egregore.local_mission import ROOT, proposal
from identity.machine_passport import MachinePassport, PassportRegistry
from policy.consequence_gate import GrantIssuer
from provenance.commit_witness import WitnessSigner

LABEL = 'SYNTHETIC_DEVELOPMENT_ONLY_NOT_FOUNDER_AUTHENTICATION'


def write_json(path, data):
    path = Path(path)
    temporary = path.with_suffix('.tmp')
    with open(temporary, 'x', encoding='utf-8') as stream:
        os.chmod(temporary, 0o600)
        json.dump(data, stream, sort_keys=True, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def provision(job, path):
    passports, grants = PassportRegistry(), GrantIssuer()
    actor = passports.issue(kind='agent', creator=LABEL, owner_organ='uniimente-kernel',
        legal_principal='alfonso_lopez', declared_capabilities=['repository.audit'],
        budget_ceiling_usd=0, consequence_class='read_only')
    grant = grants.issue_single_action(proposal=proposal(job, actor.passport_id), policy_version='1.0.0')
    write_json(path, {'classification': LABEL, 'passport': asdict(actor), 'grant': grant,
                     'metadata': grants.get_meta(grant['grant_id'])})
    return restore(path)


def restore(path):
    data = json.loads(Path(path).read_text())
    if data.get('classification') != LABEL:
        raise ValueError('only explicitly synthetic authority fixtures supported')
    passports, grants = PassportRegistry(), GrantIssuer()
    actor = MachinePassport(**data['passport'])
    passports._passports[actor.passport_id] = actor
    grant = data['grant']
    grants._grants[grant['grant_id']] = grant
    grants._meta[grant['grant_id']] = data['metadata']
    return dict(compiled=compile_constitution(str(ROOT)), passports=passports, grants=grants,
        signer=WitnessSigner(env='development'), actor=actor.passport_id, grant_id=grant['grant_id'])
