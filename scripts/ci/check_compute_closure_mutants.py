"""Each compute-closure safeguard must fail a behavioral test when removed (scratch copy; live source never mutated)."""
from pathlib import Path
import os, shutil, subprocess, sys, tempfile
ROOT=Path(__file__).resolve().parents[2]
TESTS=['tests/unit/test_greg_compute_closure.py']
C='greg/compute.py'
MUTANTS=[
    ('re-ask carries its epoch',C,'{"resource": found["resource"]} if epoch == 0 else','{"resource": found["resource"]} if True else'),
    ('no new ask while one is pending',C,'    if standing["pending"]:\n        return None','    if False:\n        return None'),
    ('re-ask only on a window after the answer',C,'if standing["closed_at"] is not None and journal.positions("")','if False and journal.positions("")'),
    ('only a signed answer closes an ask',C,'counted=MissionBook(journal).answers)','counted=None)'),
    ('a withdrawal closes an ask at its position',C,'if e.type in ("greg.decision.answered", "greg.decision.withdrawn")','if e.type in ("greg.decision.answered",)'),
    ('unparseable /proc text is None, never 0',C,'    except (TypeError, ValueError):\n        return None\n    return number','    except (TypeError, ValueError):\n        return 0.0\n    return number'),
    ('unreadable PSI is None, never 0',C,'    except (OSError, UnicodeDecodeError):\n        return None, None','    except (OSError, UnicodeDecodeError):\n        return 0.0, 0.0'),
    ('a missing field never counts as pressure',C,'not isinstance(value, bool) else None','not isinstance(value, bool) else 0.0'),
    ('memory rule',C,'PRECEDENCE = ("memory", "io", "cpu", "disk")','PRECEDENCE = ("io", "cpu", "disk")'),
    ('declared precedence',C,'PRECEDENCE = ("memory", "io", "cpu", "disk")','PRECEDENCE = ("cpu", "memory", "io", "disk")'),
    ('MemAvailable floor',C,'\n               or _below(s, "mem_available_ratio", MEM_AVAILABLE_FLOOR),',','),
    ('io rule',C,'"io": (lambda s: _at_least(s, "psi_io_some_avg60", IO_PSI_THRESHOLD),','"io": (lambda s: False,'),
    ('steps timed inside the window only',C,'\n              and first <= s["position"] <= last]',']'),
    ('a recovered step is not timing',C,'        if (p.get("routing") or {}).get("recovered"):\n            continue','        if False:\n            continue'),
    ('the delay is labelled an estimate',C,'DELAY_METHOD = ("estimate (method: ','DELAY_METHOD = ("measured (method: '),
    ('verify: above the noise floor',C,'verified = p_value <= alpha and effect > noise_floor','verified = p_value <= alpha and effect > 0'),
    ('verify: significance',C,'verified = p_value <= alpha and effect > noise_floor','verified = effect > noise_floor'),
    ('verify: one-sided, after faster',C,'if sum(chosen) <= observed)','if sum(chosen) >= observed)'),
    ('verify: minimum replicates',C,'    if min(len(b), len(a)) < MIN_REPLICATES:','    if False:'),
    ('verify: same workload',C,'    if len(digests) == 2 and digests[0] != digests[1]:','    if False:'),
    ('benchmark scratch is removed',C,'    with tempfile.TemporaryDirectory(prefix="greg-benchmark-") as scratch:','    scratch = tempfile.mkdtemp(prefix="greg-benchmark-")\n    if True:'),
    ('cli writes nothing in the body home','greg/cli.py','if Path(home).resolve() in (out, *out.parents):\n                    raise BodyError("benchmark results','if False:\n                    raise BodyError("benchmark results'),
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
