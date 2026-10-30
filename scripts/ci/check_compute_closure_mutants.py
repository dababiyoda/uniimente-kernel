"""Each compute-closure safeguard must fail a behavioral test when removed (scratch copy; live source never mutated)."""
from pathlib import Path
import os, shutil, subprocess, sys, tempfile
ROOT=Path(__file__).resolve().parents[2]
TESTS=['tests/unit/test_greg_compute_closure.py']
C='greg/compute.py'
CLI='greg/cli.py'
MUTANTS=[
    # the re-ask and its identity
    ('re-ask carries its epoch',C,'{"resource": found["resource"]} if epoch == 0 else','{"resource": found["resource"]} if True else'),
    ('no new ask while one is pending',C,'    if standing["pending"]:\n        return None','    if False:\n        return None'),
    ('re-ask only on a window after the answer',C,'if standing["closed_at"] is not None and journal.positions("")','if False and journal.positions("")'),
    ('only a signed answer closes an ask',C,'counted=MissionBook(journal).answers)','counted=None)'),
    ('a withdrawal closes an ask at its position',C,'if e.type in ("greg.decision.answered", "greg.decision.withdrawn")','if e.type in ("greg.decision.answered",)'),
    ('an ask row under another identity is not an ask',C,'\n                 and e.event_id == fact_id("decision.requested", e.payload.get("request_id"))]',']'),
    ('the epoch counts only this resource\'s asks',C,'and _bottleneck_resource(e.payload) == resource\n','and True\n'),
    # sampling
    ('unparseable /proc text is None, never 0',C,'    except (TypeError, ValueError):\n        return None\n    return number','    except (TypeError, ValueError):\n        return 0.0\n    return number'),
    ('a negative /proc reading is None',C,'return number if math.isfinite(number) and number >= 0 else None','return number if math.isfinite(number) else None'),
    ('unreadable PSI is None, never 0',C,'    except (OSError, UnicodeDecodeError):\n        return {}\n    for line in text.splitlines():','    except (OSError, UnicodeDecodeError):\n        return {"avg10": "0", "avg60": "0", "total": "0"}\n    for line in text.splitlines():'),
    ('a missing field never counts as pressure',C,'not isinstance(value, bool) else None','not isinstance(value, bool) else 0.0'),
    # bottleneck rules
    ('memory rule',C,'PRECEDENCE = ("memory", "io", "cpu", "disk")','PRECEDENCE = ("io", "cpu", "disk")'),
    ('declared precedence',C,'PRECEDENCE = ("memory", "io", "cpu", "disk")','PRECEDENCE = ("cpu", "memory", "io", "disk")'),
    ('MemAvailable floor',C,'\n               or _below(s, "mem_available_ratio", MEM_AVAILABLE_FLOOR),',','),
    ('io rule',C,'"io": (lambda s: _at_least(s, "psi_io_some_avg60", IO_PSI_THRESHOLD),','"io": (lambda s: False,'),
    ('status reports the sustained bottleneck',C,'"bottleneck": assess([e.payload for e in telemetry])','"bottleneck": None'),
    # step timing and the heaviest workload
    ('a loop record between intent and outcome voids the timing',C,'LOOP_RECORDS = ("mission.", "decision.", "body.", "command.", "compute.telemetry")','LOOP_RECORDS = ()'),
    ('loop record: mission',C,'LOOP_RECORDS = ("mission.", "decision.",','LOOP_RECORDS = ("decision.",'),
    ('loop record: decision',C,'LOOP_RECORDS = ("mission.", "decision.", "body.",','LOOP_RECORDS = ("mission.", "body.",'),
    ('loop record: body',C,'"decision.", "body.", "command.",','"decision.", "command.",'),
    ('loop record: command',C,'"body.", "command.", "compute.telemetry")','"body.", "compute.telemetry")'),
    ('loop record: telemetry',C,'"command.", "compute.telemetry")','"command.")'),
    ('timed from the latest intent of the slot',C,'start, started_at = max(begun)','start, started_at = min(begun)'),
    ('an outcome with no intent before it is not timing',C,'        if not begun or not isinstance','        if not isinstance'),
    ('an outcome without a capability is not timing',C,' or not isinstance(p.get("capability"), str) or',' or'),
    ('a recovered step is not timing',C,' or (p.get("routing") or {}).get("recovered"):\n            continue',':\n            continue'),
    ('a negative span is not timing',C,'        if seconds >= 0:\n            steps.append','        if True:\n            steps.append'),
    ('steps timed inside the window only',C,'\n              and first <= s["position"] <= last]',']'),
    ('the baseline is taken before the window',C,' and first is not None and s["position"] < first]',' and first is not None]'),
    ('no workload is named when the window took 0 s',C,'    if total > 0:\n        work["heaviest"] = rows[0]','    if True:\n        work["heaviest"] = rows[0]'),
    ('the delay is labelled an estimate',C,'DELAY_METHOD = ("estimate (method: ','DELAY_METHOD = ("measured (method: '),
    # benchmark
    ('benchmark scratch is removed',C,'    with tempfile.TemporaryDirectory(prefix="greg-benchmark-") as scratch:','    scratch = tempfile.mkdtemp(prefix="greg-benchmark-")\n    if True:'),
    ('a scratch ledger that fails verification stops the benchmark',C,'    if not ok:\n        raise RuntimeError','    if False:\n        raise RuntimeError'),
    ('varying output is not deterministic',C,'"deterministic": len(outputs) == 1','"deterministic": True'),
    ('contention is measured during every replicate',C,'round(min(1.0, max(0.0, 1 - chain_cpu / chain_wall)), 4) if chain_wall > 0 else None','None'),
    ('conditions are recorded at the end of a run',C,'    host["conditions_at_end"] = _conditions()\n',''),
    # verification
    ('verify: above the noise floor',C,'faster = p_value <= alpha and effect > noise_floor','faster = p_value <= alpha and effect > 0'),
    ('verify: significance',C,'faster = p_value <= alpha and effect > noise_floor','faster = effect > noise_floor'),
    ('verify: one-sided, after faster',C,'if sum(chosen) <= observed)','if sum(chosen) >= observed)'),
    ('verify: midranks keep ties exact',C,'            ranks[order[k]] = i + j + 2','            ranks[order[k]] = 2 * (k + 1)'),
    ('verify: minimum replicates',C,'    if min(len(b), len(a)) < MIN_REPLICATES:','    if False:'),
    ('verify: same workload',C,'    if len(digests) == 2 and digests[0] != digests[1]:','    if False:'),
    ('verify: contention measured during both runs',C,'    if not shifts:\n','    if False:\n'),
    ('verify: a quieter host credits no change',C,'    if faster and quieter:','    if False:'),
    ('verify: a busier host may mask a change',C,'    if not faster and busier:','    if False:'),
    ('verify: the declared contention tolerance',C,'if d < -CONTENTION_TOLERANCE)','if d < 0)'),
    ('verify: same host reported',C,'"same_host": ({k: v','"same_host": None and ({k: v'),
    # the CLI
    ('cli writes nothing in the body home',CLI,'for p in (out, *out.parents)):\n                    raise BodyError("benchmark results','for p in ()):\n                    raise BodyError("benchmark results'),
    ('cli expands ~ in the body home as the body does',CLI,'body_home = Layout(home).home','body_home = Path(home).resolve()'),
    ('cli never overwrites a file it did not write',CLI,'if not isinstance(kept, dict) or kept.get("kind") != "compute.benchmark":','if False:'),
    ('cli --runs must be at least 1',CLI,'                if runs < 1:\n                    raise BodyError("--runs','                if False:\n                    raise BodyError("--runs'),
]

def purge(repo):
    for cache in repo.rglob('__pycache__'):
        shutil.rmtree(cache,ignore_errors=True)

def main():
    invalid=caught_count=0
    with tempfile.TemporaryDirectory(prefix='greg-compute-mutants-') as temp:
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
