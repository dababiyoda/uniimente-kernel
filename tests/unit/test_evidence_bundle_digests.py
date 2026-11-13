"""The 2026-10-15 validation bundle's Digests table matches the tree it names (second review of PR #184, finding 13).

The README says each claim was run on the commit it names. After the freeze files moved, its table still named
``freeze-v8.json`` as the seal of the joined tree with another file's digest. Every committed file the table names
must hash to its stated digest, and the named seal must be the freeze the evaluation and CI's RUNNER_FREEZE use.
"""
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "docs/evidence/one-machine-ten-steps/2026-10-15/README.md"


def _digest_rows():
    section = README.read_text().split("## Digests", 1)[1].split("\n## ", 1)[0]
    for line in section.splitlines():
        m = re.match(r"\|\s*`([^`]+)`\s*(\([^)]*\))?\s*\|\s*`([0-9a-f]{64})`\s*\|", line)
        if m:
            yield m.group(1), m.group(2) or "", m.group(3)


def test_committed_files_in_the_digest_table_hash_to_their_stated_digest():
    checked = 0
    for rel, _label, digest in _digest_rows():
        path = next((base / rel for base in (ROOT, README.parent) if (base / rel).is_file()), None)
        if path is not None:
            assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, f"{rel}: the README's digest is stale"
            checked += 1
    assert checked, "no committed file in the Digests table was checked"


def test_the_seal_of_the_joined_tree_is_the_freeze_the_evaluation_uses():
    seals = [rel for rel, label, _ in _digest_rows() if "seal of the joined tree" in label]
    used = re.search(r"manifest = HERE / '([^']+)'", (ROOT / "cortex/evaluation/seed_genome/run.py").read_text()).group(1)
    assert f"cortex/evaluation/seed_genome/{used}" in (ROOT / "scripts/ci/replay_seed_compatibility.py").read_text()
    assert seals == [f"cortex/evaluation/seed_genome/{used}"]
