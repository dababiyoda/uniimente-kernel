"""Each NODE_REVOKE / node-enrollment safeguard must fail a behavioral test when removed (scratch copy; live source
never mutated)."""
from pathlib import Path
import os, shutil, subprocess, sys, tempfile
ROOT=Path(__file__).resolve().parents[2]
TESTS=['tests/unit/test_greg_node_revoke.py']
F='greg/founder.py'
C='greg/compute.py'
B='greg/body.py'
R='greg/recovery.py'
L='greg/lightcone.py'
I='greg/cli.py'
MUTANTS=[
    # founder key only
    ('a device may never be delegated NODE_REVOKE',F,
     'DEVICE_KINDS = ("DECISION", "CRITIQUE", "LIFECYCLE",','DEVICE_KINDS = ("NODE_REVOKE", "DECISION", "CRITIQUE", "LIFECYCLE",'),
    ('the verifier refuses a device any kind outside DEVICE_KINDS',F,
     'if kind is not None and (kind not in DEVICE_KINDS or kind not in device["kinds"]):','if kind is not None and (kind not in device["kinds"]):'),
    ('NODE_REVOKE is dispatched to revoke_node',B,
     '        if kind == "NODE_REVOKE":                # founder key only (DEVICE_KINDS excludes it)\n            return compute.revoke_node(self.journal, body, digest, now=now)\n',''),
    # enrollment shape
    ('enrollment takes only its declared fields',C,
     'if not required <= set(body) <= required | {"expires_at"}:','if not required <= set(body):'),
    ('node_id is a bounded string',C,
     '    if not isinstance(node_id, str) or not 1 <= len(node_id) <= 128:\n        raise','    if False:\n        raise'),
    ('node_id has an upper bound',C,
     'not 1 <= len(node_id) <= 128:','not 1 <= len(node_id):'),
    ('the node_id bound admits 128 characters',C,
     'not 1 <= len(node_id) <= 128:','not 1 <= len(node_id) <= 127:'),
    ('a node key is exactly 64 hex characters',C,
     'if isinstance(value, str) and len(value) == 64:','if isinstance(value, str):'),
    ('a node key decodes to exactly 32 bytes',C,
     '    if raw is None or len(raw) != 32:','    if raw is None:'),
    # expiry
    ('expires_at must be a string',C,
     '        if not isinstance(body["expires_at"], str):\n            raise','        if False:\n            raise'),
    ('an out-of-range expires_at is a refusal, not a crash',C,
     '        except OverflowError:\n            raise ValueError("expires_at is out of range") from None','        except ZeroDivisionError:\n            raise ValueError("expires_at is out of range") from None'),
    ('expires_at is later than the command time',C,
     '        if when <= now:\n','        if False:\n'),
    ('an expired node is inactive',C,
     'else "EXPIRED" if expires is not None and now >= instant(expires) else "ACTIVE")','else "ACTIVE")'),
    # re-enrollment
    ('an active node_id is not enrolled again without a revoke',C,
     '    if nodes.get(node_id, {}).get("state") == "ACTIVE":\n','    if False:\n'),
    ('each enrollment is its own fact, so a revoked node can be enrolled again',C,
     'journal.record("node.enrolled", record, key=[node_id, command_digest])','journal.record("node.enrolled", record, key=node_id)'),
    ('the same signed enrollment applied again returns its record',C,
     '        if event.payload.get("command_digest") == command_digest:\n            return event.payload','        if False:\n            return event.payload'),
    # key separation
    ('a founder or device key never becomes a node key',C,
     '    if raw in _principal_keys(journal):\n','    if False:\n'),
    ('a rotated-in founder key is a principal key',C,
     '    found += [e.payload.get("new_public_key") for e in journal.replay("founder.key_rotated")]\n',''),
    ('a device key, even revoked, is a principal key',C,
     '    found += [e.payload.get("public_key") for e in journal.replay("device.enrolled")]\n',''),
    ("this body's own identity key never becomes a node key",C,
     '    if _body_id_of(raw) in own:\n','    if False:\n'),
    ("no node takes this body's own id",C,
     '    if node_id in own:\n','    if False:\n'),
    ('each active node has its own key',C,
     '    if any(n["state"] == "ACTIVE" and bytes.fromhex(n["node_public_key"]) == raw for n in nodes.values()):','    if False:'),
    ('only an active node holds its key',C,
     'if any(n["state"] == "ACTIVE" and bytes.fromhex(n["node_public_key"]) == raw','if any(bytes.fromhex(n["node_public_key"]) == raw'),
    # revocation
    ('a revocation ends the enrollment',C,
     '        elif event.type == "greg.node.revoked":\n','        elif False:\n'),
    ('only active nodes are active_nodes',C,
     'return {k: v for k, v in node_states(journal, now=now).items() if v["state"] == "ACTIVE"}','return dict(node_states(journal, now=now))'),
    ('a revocation takes exactly node_id',C,
     '    if set(body) != {"node_id"}:\n        raise ValueError("NODE_REVOKE needs exactly node_id")','    if "node_id" not in body:\n        raise ValueError("NODE_REVOKE needs exactly node_id")'),
    ('an unknown node is not revoked',C,
     '    if node is None:\n        raise','    if False:\n        raise'),
    ('a revoked node is not revoked twice',C,
     '    if node["state"] == "REVOKED":\n','    if False:\n'),
    # restore: an enrollment from before the recovery point is voided, as device delegations are
    ('a restore voids the unrevoked node enrollments',R,
     '        nodes = compute.unrevoked_nodes(body.journal, now=now)\n','        nodes = []\n'),
    ('a restore records each void as a revocation',R,
     '        compute.void_for_restore(body.journal, nodes, restore_id=restore_id, now=now)\n',''),
    ('a restore voids expired enrollments too, so a clock set back revives none',C,
     'if v["state"] != "REVOKED")','if v["state"] == "ACTIVE")'),
    ("a restore's revocation ends an enrollment like the founder's",C,
     '        elif event.type == "greg.node.revoked":\n','        elif event.type == "greg.node.revoked" and data.get("by") != "restore":\n'),
    # a light cone out of float range is a refusal, never an exception past every caller
    ('an out-of-range light-cone budget is a scope error',L,
     '        except OverflowError:   # a JSON integer','        except ZeroDivisionError:   # a JSON integer'),
    # greg node list reads beside a running body
    ('node list never opens the ledger as its writer',I,
     '                with observe(home, actor="spiffe://uniimente.internal/greg/cli-reader") as journal:\n'
     '                    data = {"nodes": list(compute.node_states(journal).values())}',
     '                with Body(home) as b:\n'
     '                    data = {"nodes": list(compute.node_states(b.journal).values())}'),
    ('the same signed revocation applied again returns its record',C,
     '        if event.payload.get("command_digest") == command_digest:\n            return {"node_id"','        if False:\n            return {"node_id"'),
]

def purge(repo):
    for cache in repo.rglob('__pycache__'):
        shutil.rmtree(cache,ignore_errors=True)

def main():
    invalid=caught_count=0
    with tempfile.TemporaryDirectory(prefix='greg-node-revoke-mutants-') as temp:
        repo=Path(temp)/'repo';scratch_tmp=Path(temp)/'tmp';scratch_tmp.mkdir()
        shutil.copytree(ROOT,repo,ignore=shutil.ignore_patterns('.git','__pycache__','.pytest_cache'))
        env={**os.environ,'PYTHONPATH':str(repo),'PYTHONDONTWRITEBYTECODE':'1','TMPDIR':str(scratch_tmp)}
        for name,rel,old,new in MUTANTS:
            path=repo/rel;original=path.read_text()
            if original.count(old)!=1:
                print('STALE',name,flush=True);invalid+=1;continue
            path.write_text(original.replace(old,new));purge(repo)
            run=subprocess.run([sys.executable,'-B','-m','pytest','-q','-x','-p','no:cacheprovider',*TESTS],
                cwd=repo,env=env,capture_output=True,text=True,timeout=300)
            caught=run.returncode==1 and 'FAILED tests/' in run.stdout and 'ERROR collecting' not in run.stdout
            print('CAUGHT' if caught else 'SURVIVED_OR_INVALID',name,flush=True)
            invalid+=not caught;caught_count+=caught;path.write_text(original)
        purge(repo)
        clean=subprocess.run([sys.executable,'-B','-m','pytest','-q','-p','no:cacheprovider',*TESTS],
            cwd=repo,env=env,capture_output=True,text=True,timeout=300)
        print('UNMUTATED', 'PASS' if clean.returncode==0 else 'FAIL',flush=True)
        invalid+=clean.returncode!=0
    print(f'{caught_count}/{len(MUTANTS)} mutants caught',flush=True)
    return int(bool(invalid))
if __name__=='__main__':raise SystemExit(main())
