"""Each NODE_REVOKE / node-enrollment safeguard, and each safeguard that keeps a revoked device key from acting, must
fail a behavioral test when removed (scratch copy; live source never mutated).

The device-revocation mutants (2026-11-13, the review of 7474e937) carry their own test files as a fifth element: a
revocation waiting in the inbox wins over a backdated device command (B2), greg serve refuses device keys while the
ledger ends inside an incomplete record and shows that record to the founder (B3, B4), and the proof host's stop
control gives an incomplete line a real chance to complete before it blocks (B1).

The second fix round (2026-11-13, the re-check of 8f72ceff): a waiting revocation is read under the founder keys a
waiting rotation ahead of it enrolls (N1), greg serve names an inbox file by when it arrived, not by the signer's own
clock (N2), and a JSON document nested too deep is malformed input wherever GREG reads input it does not control (N3,
its own test file). send_signed's arrival name is not mutated: the founder signs at the moment the file arrives, so
the two names differ at most in width."""
from pathlib import Path
import os, shutil, subprocess, sys, tempfile
ROOT=Path(__file__).resolve().parents[2]
TESTS=['tests/unit/test_greg_node_revoke.py']
REVOKING=['tests/unit/test_device_revocation_wins.py']
LIVE=['tests/unit/test_live_ledger_readers.py']
NESTED=['tests/unit/test_greg_nested_json_inputs.py']
F='greg/founder.py'
C='greg/compute.py'
B='greg/body.py'
R='greg/recovery.py'
L='greg/lightcone.py'
I='greg/cli.py'
S='greg/remote.py'
P='greg/phone/app.js'
M='egregore/local_mission.py'
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
    # B2: a founder revocation waiting in the inbox wins, whatever order the device's command sorts in
    ('a key a waiting revocation names still verifies',F,
     '        if kid in self.revoking:\n            raise FounderAuthError(REVOKING)\n','',REVOKING),
    ('the inbox pass reads no waiting revocation',B,
     '        revoking = self.revoking(paths)\n','        revoking = frozenset()\n',REVOKING),
    ('a direct apply reads no waiting revocation',B,
     'verifier = self.verifier(revoking=self.revoking() if revoking is None else revoking)',
     'verifier = self.verifier(revoking=revoking or ())',REVOKING),
    ('a revocation that does not verify counts',B,
     '            current.verify(envelope, now=now, expected_kind=kind)\n','',REVOKING),
    # N1: a revocation signed by the key a waiting rotation enrolls
    ('a waiting rotation is not read',B,
     'envelope.get("kind") in ("DEVICE_REVOKE", "ROTATE_FOUNDER_KEY")','envelope.get("kind") in ("DEVICE_REVOKE",)',
     REVOKING),
    ('a waiting rotation does not change the keys a later revocation is read under',B,
     '                keys.pop(next(iter(keys)))\n                keys[new_id] = new_hex\n','                pass\n',REVOKING),
    ('a rotation to a malformed key raises out of the pre-read',B,
     '            except (ValueError, FounderAuthError):   # apply refuses a rotation',
     '            except ZeroDivisionError:   # apply refuses a rotation',REVOKING),
    # N2: greg serve names a command by when it arrived
    ("greg serve names a command by the signer's clock",S,
     'name = f"{arrival_name(now)}-remote-',
     'name = f"{envelope[\'issued_at\'].replace(\':\', \'\')}-remote-',REVOKING),
    # N3: a document nested too deep is malformed input. Since bdfca22d's re-check every such read goes through
    # greg.untrusted_json, so each mutant puts back the plain json.loads that let RecursionError (or a deep value
    # that later raised it) escape; the former mutants that dropped RecursionError from an except are equivalent now.
    ('the inbox is parsed without the untrusted reader',B,
     '    return untrusted_json.loads(raw.decode("utf-8"))','    return json.loads(raw.decode("utf-8"))',NESTED),
    ('the intake is parsed without the untrusted reader',B,
     '                    item = untrusted_json.loads(raw)\n','                    item = json.loads(raw)\n',NESTED),
    ('greg serve parses a command without the untrusted reader',S,
     'envelope = untrusted_json.loads(body.decode("utf-8"))','envelope = json.loads(body.decode("utf-8"))',NESTED),
    ('a revocation body DEVICE_REVOKE refuses counts',B,
     '                kid, _ = revocation.revoke_fields(body)\n',
     '                kid = body["device_key_id"]\n',REVOKING),
    # re-check of 48d66f5f: F1, a suspected-compromise revocation counts too
    ('only an exact {"device_key_id"} revocation counts',B,
     '                kid, _ = revocation.revoke_fields(body)\n',
     '                kid, _ = revocation.revoke_fields(body)\n                if set(body) != {"device_key_id"}:\n                    continue\n',REVOKING),
    # F3: an inbox entry that is not a regular file is never read with a blocking open
    ('a FIFO in the inbox is read as a file',B,
     '        if not stat.S_ISREG(info.st_mode):\n            raise OSError(errno.EINVAL',
     '        if False:\n            raise OSError(errno.EINVAL',NESTED),
    ('setting a FIFO aside reads it with a blocking open',B,
     '            raw = _read_inbox_file(path)      # never waits on a FIFO',
     '            raw = path.read_bytes()      # never waits on a FIFO',NESTED),
    # F2: the same nested-JSON class in four more readers
    ('a nested worker report raises',"greg/workers.py",
     'value = untrusted_json.loads(line.split(REPORT_MARK, 1)[1].strip())',
     'value = json.loads(line.split(REPORT_MARK, 1)[1].strip())',NESTED),
    ('a nested organ signal raises',"greg/organ_exchange.py",
     'signal = untrusted_json.loads(raw.decode("utf-8"))','signal = json.loads(raw.decode("utf-8"))',NESTED),
    ('a nested Ollama answer raises',"greg/models.py",
     '                result = untrusted_json.loads(raw)\n            except (UnicodeError, ValueError, RecursionError) as exc:',
     '                result = json.loads(raw)\n            except (UnicodeError, ValueError) as exc:',NESTED),
    ('a nested MCP answer raises',"greg/mcp_tools.py",
     'answer = untrusted_json.loads(lines[-1])',
     'answer = json.loads(lines[-1])',NESTED),
    # re-check of bdfca22d
    ('M1: a refused inbox file is opened again with a blocking read',B,
     '            consumed = getattr(exc, "consumed", None)\n            # the reason',
     '            raw = path.read_bytes()\n            consumed = getattr(exc, "consumed", None)\n            # the reason',NESTED),
    ('M2: the inbox digests are read with a blocking read',B,
     '            out.add(sha256_json(_parse_inbox(_read_inbox_file(path))))',
     '            out.add(sha256_json(_parse_inbox(path.read_bytes())))',NESTED),
    ('M3: a built candidate\'s output is read without the untrusted reader',"greg/builders.py",
     '        results = untrusted_json.loads(proc.stdout)','        results = json.loads(proc.stdout)',NESTED),
    ('M3: a claims file is read without the untrusted reader',"greg/cognition/restatement.py",
     '        claims = untrusted_json.loads(raw)','        claims = json.loads(raw)',NESTED),
    ('M3: a model draft is read without the untrusted reader',"greg/planner.py",
     '                value = untrusted_json.loads(text[start:end + 1])',
     '                value = json.loads(text[start:end + 1])',NESTED),
    ('M3: a too-deep draft is retried from every inner brace',"greg/planner.py",
     '            except untrusted_json.TooDeep:\n                raise MissionError(',
     '            except ZeroDivisionError:\n                raise MissionError(',NESTED),
    ('M3: the Claude Code report is read without the untrusted reader',"greg/models.py",
     '        result = untrusted_json.loads(proc.stdout)\n    except (json.JSONDecodeError, TypeError):',
     '        result = json.loads(proc.stdout)\n    except (json.JSONDecodeError, TypeError):',NESTED),
    ('the untrusted reader lets RecursionError escape',"greg/untrusted_json.py",
     '    except RecursionError:\n','    except ZeroDivisionError:\n',NESTED),
    ('the untrusted reader accepts a value deeper than MAX_DEPTH',"greg/untrusted_json.py",
     '        if depth > MAX_DEPTH:','        if False:',NESTED),
    ('the untrusted reader refuses MAX_DEPTH itself',"greg/untrusted_json.py",
     '        if depth > MAX_DEPTH:','        if depth >= MAX_DEPTH:',NESTED),
    ('L1: the revocation count reads with its own reader',B,
     '            envelope = _parse_inbox(_read_inbox_file(path))\n        except (OSError, ValueError):\n            continue',
     '            envelope = json.loads(path.read_bytes()[:65536])\n        except (OSError, ValueError):\n            continue',REVOKING),
    ('L2: an inbox entry behind a link is followed',B,
     'os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)','os.O_RDONLY | os.O_NONBLOCK)',NESTED),
    # (removing only the size check is equivalent: the read loop bounds the same file)
    ('L2: an oversized inbox entry is read whole, either check',B,
     '        if info.st_size > INBOX_FILE_BYTES:\n            raise InboxEntryRefused(errno.EFBIG, f"inbox entry is larger than {INBOX_FILE_BYTES} bytes", str(path))\n        chunks, total = [], 0\n        while chunk := os.read(fd, 1 << 16):\n            total += len(chunk)\n            if total > INBOX_FILE_BYTES:',
     '        chunks, total = [], 0\n        while chunk := os.read(fd, 1 << 16):\n            total += len(chunk)\n            if False:',NESTED),
    # F1 (re-check of 6933be8c): a link or an oversized file is refused like a malformed command, never a body exit
    ('F1: a linked inbox entry makes the running body exit',B,
     'raise InboxEntryRefused(errno.ELOOP, "inbox entry is a symbolic link", str(path)) from None',
     'raise OSError(errno.ELOOP, "inbox entry is a symbolic link", str(path)) from None',NESTED),
    ('F1: a refused inbox entry is not a malformed command',B,
     'class InboxEntryRefused(OSError, ValueError):','class InboxEntryRefused(OSError):',NESTED),
    # F2-F7 (re-check of 6933be8c): the remaining readers of output GREG did not write
    ('F3: the planner scan has no depth bound',"greg/planner.py",
     '                    if len(stack) > untrusted_json.MAX_DEPTH:\n                        raise MissionError(',
     '                    if False:\n                        raise MissionError(',NESTED),
    ('F3: the planner forgets braces that never close and rescans from each',"greg/planner.py",
     '            for opened in stack:\n                close.setdefault(opened, None)\n',
     '            for opened in stack:\n                pass\n',NESTED),
    ('F6: the heartbeat is read with plain json.loads',B,
     '        value = untrusted_json.loads(layout.heartbeat.read_text())\n',
     '        value = json.loads(layout.heartbeat.read_text())\n',NESTED),
    ("F2: an organ message's body is read with plain json.loads","greg/organs.py",
     '        return untrusted_json.loads(body)\n    except ValueError:\n        raise CapabilityError(f"{organ} returned a message',
     '        return json.loads(body)\n    except ValueError:\n        raise CapabilityError(f"{organ} returned a message',NESTED),
    ("F2: the organ exchange's stdout is read with plain json.loads","greg/organ_exchange.py",
     '        return untrusted_json.loads(done.stdout)\n    except ValueError:\n        raise CapabilityError("organ returned output',
     '        return json.loads(done.stdout)\n    except ValueError:\n        raise CapabilityError("organ returned output',NESTED),
    ("F2: the venture organ's stdout is read with plain json.loads","greg/ventures.py",
     '        return untrusted_json.loads(done.stdout)\n','        return json.loads(done.stdout)\n',NESTED),
    ('F2: a GitHub body is read with plain json.loads',"greg/briefs.py",
     '        return untrusted_json.loads(body if isinstance(body, str) else body.decode("utf-8"))\n',
     '        return json.loads(body if isinstance(body, str) else body.decode("utf-8"))\n',NESTED),
    ('F4: the MCP client prints its renewal only inside the answer line',"greg/mcp_remote.py",
     '            print(json.dumps({"renewed": renewed}), flush=True)\n','',NESTED),
    ('F4: a renewal printed alone is not kept',"greg/mcp_tools.py",
     '            mcp_login.store_renewal(ctx.secrets, str(bearer), login, item["renewed"])\n            return\n',
     '            return\n',NESTED),
    # B3/B4: greg serve while the ledger ends inside an incomplete record (it may be the device's revocation)
    ('greg serve reads no waiting revocation',S,
     'revoking=pending_revocations(candidates, settled, now=self.now))','revoking=())',REVOKING),
    ('greg serve never notes an incomplete last record',S,
     '            self.torn = self.ledger.unacknowledged_tail is not None\n','            self.torn = False\n',REVOKING),
    ('a device read is served while the last record is incomplete',S,
     '                raise RemoteError(401, str(exc))\n            if reader.torn and principal != "founder":\n',
     '                raise RemoteError(401, str(exc))\n            if False:\n',REVOKING),
    ('a device command is taken while the last record is incomplete',S,
     '                raise RemoteError(403, str(exc))\n            if reader.torn and principal != "founder":\n',
     '                raise RemoteError(403, str(exc))\n            if False:\n',REVOKING),
    ('the founder is refused too while the last record is incomplete',S,
     '                raise RemoteError(401, str(exc))\n            if reader.torn and principal != "founder":\n',
     '                raise RemoteError(401, str(exc))\n            if reader.torn:\n',REVOKING),
    ("the founder's status hides an incomplete last record",B,
     '"unacknowledged_tail": ledger.unacknowledged_tail and {','"unacknowledged_tail": None and {',REVOKING),
    ('the phone page hides an incomplete last record',P,
     '(status.security.unacknowledged_tail ? " · last record INCOMPLETE','(false ? " · last record INCOMPLETE',REVOKING),
    # B1: the stop control's settle window
    ('the settle window opens before the first read returns',M,
     '            line, since = tail["offset"], time.monotonic()\n','            line, since = tail["offset"], began\n',LIVE),
    ('a read that began inside the window decides the line will not finish',M,
     '        elif began >= since + settle:','        elif time.monotonic() >= since + settle:',LIVE),
    ('a new incomplete line gets no window of its own',M,
     '        if tail["offset"] != line:','        if line is None:',LIVE),
    ('the wait has no bound',M,'        if began >= first + limit:\n','        if False:\n',LIVE),
    ('a line that never completes is judged only by the bound',M,
     '        elif began >= since + settle:','        elif False:',LIVE),
    ('an incomplete line is read as no stop',M,
     '        if tail is None:\n            return False\n','        if True:\n            return False\n',LIVE),
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
        for name,rel,old,new,*own in MUTANTS:
            path=repo/rel;original=path.read_text()
            if original.count(old)!=1:
                print('STALE',name,flush=True);invalid+=1;continue
            path.write_text(original.replace(old,new));purge(repo)
            run=subprocess.run([sys.executable,'-B','-m','pytest','-q','-x','-p','no:cacheprovider',*(own[0] if own else TESTS)],
                cwd=repo,env=env,capture_output=True,text=True,timeout=300)
            caught=run.returncode==1 and 'FAILED tests/' in run.stdout and 'ERROR collecting' not in run.stdout
            print('CAUGHT' if caught else 'SURVIVED_OR_INVALID',name,flush=True)
            invalid+=not caught;caught_count+=caught;path.write_text(original)
        purge(repo)
        clean=subprocess.run([sys.executable,'-B','-m','pytest','-q','-p','no:cacheprovider',*TESTS,*REVOKING,*LIVE,*NESTED],
            cwd=repo,env=env,capture_output=True,text=True,timeout=300)
        print('UNMUTATED', 'PASS' if clean.returncode==0 else 'FAIL',flush=True)
        invalid+=clean.returncode!=0
    print(f'{caught_count}/{len(MUTANTS)} mutants caught',flush=True)
    return int(bool(invalid))
if __name__=='__main__':raise SystemExit(main())
