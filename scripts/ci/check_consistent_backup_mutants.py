"""Each safeguard that makes a backup of a running body consistent must fail a behavioral test when removed (WU-14).

Every mutant runs in a scratch copy of the repository, with bytecode off and every ``__pycache__`` purged first, so a
stale compiled module can never stand in for the mutated source.
"""
from pathlib import Path
import os, shutil, subprocess, sys, tempfile

ROOT = Path(__file__).resolve().parents[2]
SEED = "foundry/systems/seed.py"
BACKUP = "greg/backup.py"
RECOVERY = "greg/recovery.py"
UNIT = "tests/unit/test_greg_seed_consistency.py"
CADENCE = "tests/unit/test_greg_backup.py"
MUTANTS = [
    ("head read from the live ledger after the copy", SEED,
     '"backed_up_at": backed_up_at, "ledger_head": head}',
     '"backed_up_at": backed_up_at, "ledger_head": ledger_prefix(home)[1]}', UNIT),
    ("the live ledger copied again with the other files", SEED,
     "if rel == LEDGER:\n            continue", "if rel == LEDGER and False:\n            continue", UNIT),
    ("torn final line packed", SEED,
     'return raw[:raw.rfind(b"\\n") + 1]', "return raw", UNIT),
    ("prefix not verified as a chain", SEED, "    if not constitution:\n", "    if True:\n", UNIT),
    ("derived heartbeat packed", SEED,
     "if rel in DERIVED:\n            derived.append(rel)", "if False:\n            derived.append(rel)", UNIT),
    ("derived heartbeat restored from a seed that carries one", SEED,
     "if rel in DERIVED:                              #", "if False:                                       #", UNIT),
    ("an earlier recovery point outside the verified ledger accepted", SEED,
     "        if cut is None:\n", "        if False:\n", CADENCE),
    ("an earlier recovery point packs the whole ledger", SEED,
     'prefix, head = b"\\n".join(prefix.split(b"\\n")[:cut.seq + 1]) + b"\\n", end', "head = end", CADENCE),
    ("a store inside the body home or a read root accepted", BACKUP,
     "        if store == root or root in store.parents:\n", "        if False:\n", CADENCE),
    ("read roots not checked", BACKUP,
     '(("the body home", _home(ctx)), *(("a read root", Path(r).resolve()) for r in ctx.read_roots))',
     '(("the body home", _home(ctx)),)', CADENCE),
    ("any target prefix taken as a store", BACKUP,
     'raw = target[len(PREFIX):] if target.startswith(PREFIX) else ""', 'raw = target.split(":", 1)[-1]', CADENCE),
    ("a backup counted without its drill", BACKUP, '        proof = drill(store, made["seed"])\n',
     '        proof = {"restored_head": made["ledger_head"], "restored_records": 0, "held": True, '
     '"drill_seconds": 0}\n', CADENCE),
    ("freshness ignores the RPO", BACKUP, "    if why is None and age > rpo:\n", "    if False:\n", CADENCE),
    ("recovery point inside the backup's own dispatch", BACKUP,
     "end=before_dispatch(home, ctx.grant_id)", "end=None", CADENCE),
    ("verified evidence not bound to the signed store", BACKUP, ', target=PREFIX + str(store))', ')', CADENCE),
    ("the drill trusts the restore without re-verifying its file", RECOVERY,
     "        layout = Layout(home)\n        config = json.loads(layout.config.read_text())\n",
     '        return {"seed": seed_address, "restored_head": report["ledger_head_at_recovery_point"], '
     '"held": True}\n', CADENCE),
    # Review findings (WU14-ATK-1..7, WU14-F1..F4): each safeguard added for one must fail a test when removed.
    ("files read by path, following links (the base behaviour)", SEED,
     "            continue\n        data, why = _read(dirfd, name, keys)\n",
     "            continue\n        path = Path(home) / rel\n        data, why = (path.read_bytes(), None) if path.is_file() "
     "else (None, 'not a file')\n", UNIT),
    ("a hard link to key material packed", SEED,
     "    if (listed.st_dev, listed.st_ino) in keys:\n", "    if False:\n", UNIT),
    ("one unreadable file fails the whole seed", SEED,
     "    except OSError as exc:                 # EIO", "    except FileNotFoundError as exc:       # EIO", UNIT),
    ("the queues read after the ledger", SEED,
     "    waiting = _waiting(home, keys)\n    ledger, head = ledger_prefix(home, end=end)\n",
     "    ledger, head = ledger_prefix(home, end=end)\n    waiting = _waiting(home, keys)\n", UNIT),
    ("a home that is a link is not walked", SEED, "    root = os.path.realpath(home)\n", "    root = str(home)\n",
     UNIT),
    ("the drill accepts a restored body that is not held", RECOVERY,
     "        if not held:                                              #", "        if False:  #", CADENCE),
    ("a missing store is created (on the body's own disk)", BACKUP, "    before = _identity(store)\n",
     "    store.mkdir(parents=True, exist_ok=True)\n    before = _identity(store)\n", CADENCE),
    ("a store on the body's own filesystem accepted unsigned", BACKUP,
     "    if same and not accepted:\n", "    if False:\n", CADENCE),
    ("a store replaced during the backup accepted", BACKUP,
     "    if _identity(store) != before:\n", "    if False:\n", CADENCE),
    ("status trusts the receipts alone (a store that is gone stays fresh)", BACKUP,
     "    why = _gone(home, store, latest)\n", "    why = None\n", CADENCE),
    ("status does not check the latest seed is still in the store", BACKUP,
     "    if not _intact(store, latest):\n", "    if False:\n", CADENCE),
    ("a non-canonical target accepted (its backups unseen)", BACKUP,
     "    if target != PREFIX + str(store):\n", "    if False:\n", CADENCE),
    ("a store path with a glob character accepted by the capability", BACKUP,
     "    if any(c in raw for c in GLOB):\n", "    if False:\n", CADENCE),
    ("a store path with a glob character accepted by the spec", BACKUP,
     "    if any(c in str(store) for c in GLOB):\n", "    if False:\n", CADENCE),
    ("an RPO no longer than the cadence signed", BACKUP,
     "    if rpo_seconds < 2 * cadence_seconds:\n", "    if False:\n", CADENCE),
    ("freshness judged from the oldest verified backup", BACKUP, "latest = rows[-1]", "latest = rows[0]", CADENCE),
    ("a store equal to the body home or a read root accepted", BACKUP,
     "if store == root or root in store.parents:", "if root in store.parents:", CADENCE),
]


def purge(repo: Path) -> None:
    for cache in repo.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)


def main() -> int:
    invalid = 0
    with tempfile.TemporaryDirectory(prefix="greg-consistent-backup-mutants-") as temp:
        repo = Path(temp) / "repo"
        shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        env = {**os.environ, "PYTHONPATH": str(repo), "PYTHONDONTWRITEBYTECODE": "1"}
        for name, rel, old, new, tests in MUTANTS:
            path = repo / rel
            original = path.read_text()
            if original.count(old) != 1:
                print("STALE", name)
                invalid += 1
                continue
            path.write_text(original.replace(old, new))
            purge(repo)
            run = subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", tests],
                                 cwd=repo, env=env, capture_output=True, text=True, timeout=300)
            caught = (run.returncode == 1 and f"FAILED {tests}::" in run.stdout
                      and "ERROR collecting" not in run.stdout)
            print("CAUGHT" if caught else "SURVIVED_OR_INVALID", name)
            invalid += not caught
            path.write_text(original)
    return int(bool(invalid))


if __name__ == "__main__":
    raise SystemExit(main())
