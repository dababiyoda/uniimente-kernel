"""`python -m handoff.conform` — verify the bundle seal and run every vector.

Three checks, in order, each fatal:

1. **Bundle integrity.** Every path in `BUNDLE_MANIFEST.json` exists and hashes to
   the value recorded there, and no bundle file is missing from the manifest. A
   file that drifted, or one that was added without being listed, fails here.
2. **Seal.** The recomputed digest of `BUNDLE_MANIFEST.json` matches `SEAL.json`,
   and the commit named in the seal exists and is an ancestor of HEAD.
3. **Acceptance vectors.** Every vector is validated against its schema and must
   land on its declared expectation. A REJECT vector that validates is as much a
   failure as an ACCEPT vector that does not.

Nothing here mutates the bundle. `--emit-manifest` writes `BUNDLE_MANIFEST.json`
and is used once, in commit A, before the seal exists.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field

HANDOFF_DIR = os.path.dirname(os.path.abspath(__file__))
KERNEL_ROOT = os.path.dirname(HANDOFF_DIR)
BUNDLE_MANIFEST_PATH = os.path.join(HANDOFF_DIR, "BUNDLE_MANIFEST.json")
SEAL_PATH = os.path.join(HANDOFF_DIR, "SEAL.json")

CONTRACT_VERSION = "1.0.0"

#: Everything the seal covers. Pre-existing canonical schemas are included so a
#: change to one of them cannot silently alter what the bundle means.
BUNDLE_FILES: tuple[str, ...] = (
    "handoff/contract.json",
    "handoff/CHATGPT_BRIEF.md",
    "handoff/conform.py",
    "handoff/schemas/boundary-envelope.schema.json",
    "handoff/schemas/capability-request.schema.json",
    "handoff/schemas/containment-requirement.schema.json",
    "handoff/schemas/evidence-record.schema.json",
    # Referenced canonical schemas, not forked into the bundle.
    "contracts/organ-manifest.schema.json",
    "contracts/capability-grant.schema.json",
    "contracts/evidence.schema.json",
)

VECTOR_DIR = os.path.join(HANDOFF_DIR, "vectors")


class ConformanceError(RuntimeError):
    """The bundle failed verification. Fails closed; no partial acceptance."""


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _vector_paths() -> tuple[str, ...]:
    if not os.path.isdir(VECTOR_DIR):
        return ()
    return tuple(sorted(
        os.path.join("handoff", "vectors", n)
        for n in os.listdir(VECTOR_DIR) if n.endswith(".json")
    ))


def bundle_paths() -> tuple[str, ...]:
    """Every sealed path, sorted. Vectors are discovered, never hand-listed."""
    return tuple(sorted(set(BUNDLE_FILES) | set(_vector_paths())))


def build_manifest(root: str = KERNEL_ROOT) -> dict:
    """The manifest: sorted path + SHA-256 for every file the seal covers."""
    entries = []
    for rel in bundle_paths():
        absolute = os.path.join(root, rel)
        if not os.path.isfile(absolute):
            raise ConformanceError(f"bundle file missing: {rel}")
        entries.append({"path": rel, "sha256": sha256_file(absolute)})
    return {
        "manifest_version": "1.0.0",
        "contract_version": CONTRACT_VERSION,
        "digest_algorithm": "sha256",
        "digest_definition": (
            "The bundle digest is SHA-256 over the exact bytes of this file as "
            "committed, serialized with indent=2, sort_keys=True and a trailing "
            "newline."
        ),
        "file_count": len(entries),
        "files": entries,
    }


def serialize_manifest(manifest: dict) -> bytes:
    return (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")


def bundle_digest(root: str = KERNEL_ROOT) -> str:
    """SHA-256 of the committed BUNDLE_MANIFEST.json bytes."""
    path = os.path.join(root, "handoff", "BUNDLE_MANIFEST.json")
    if not os.path.isfile(path):
        raise ConformanceError(
            "handoff/BUNDLE_MANIFEST.json is absent; the bundle was never frozen"
        )
    return sha256_file(path)


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------

@dataclass
class ConformanceReport:
    contract_version: str = CONTRACT_VERSION
    bundle_digest: str | None = None
    sealed_commit: str | None = None
    integrity: list[str] = field(default_factory=list)
    seal: list[str] = field(default_factory=list)
    vectors_passed: int = 0
    vectors_failed: list[str] = field(default_factory=list)
    vectors_skipped: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not (self.integrity or self.seal or self.vectors_failed)

    def to_dict(self) -> dict:
        return {
            "contract_version": self.contract_version,
            "bundle_digest": self.bundle_digest,
            "sealed_commit": self.sealed_commit,
            "integrity_failures": self.integrity,
            "seal_failures": self.seal,
            "vectors_passed": self.vectors_passed,
            "vectors_failed": self.vectors_failed,
            "vectors_skipped": self.vectors_skipped,
            "ok": self.ok,
        }


def check_integrity(root: str = KERNEL_ROOT) -> tuple[list[str], str | None]:
    """Every listed file hashes as recorded, and nothing sealed is unlisted."""
    problems: list[str] = []
    manifest_path = os.path.join(root, "handoff", "BUNDLE_MANIFEST.json")
    if not os.path.isfile(manifest_path):
        return ["handoff/BUNDLE_MANIFEST.json is absent; the bundle is unfrozen"], None

    with open(manifest_path, encoding="utf-8") as fh:
        manifest = json.load(fh)

    recorded = {e["path"]: e["sha256"] for e in manifest.get("files", [])}
    expected = set(bundle_paths())

    for missing in sorted(expected - set(recorded)):
        problems.append(f"bundle file not listed in the manifest: {missing}")
    for extra in sorted(set(recorded) - expected):
        problems.append(f"manifest lists a file outside the bundle: {extra}")

    for rel, digest in sorted(recorded.items()):
        absolute = os.path.join(root, rel)
        if not os.path.isfile(absolute):
            problems.append(f"sealed file is gone: {rel}")
            continue
        actual = sha256_file(absolute)
        if actual != digest:
            problems.append(
                f"sealed file changed under the same digest: {rel} "
                f"(recorded {digest[:12]}…, actual {actual[:12]}…)"
            )
    return problems, sha256_file(manifest_path)


def _git(root: str, *args: str) -> str | None:
    try:
        out = subprocess.run(("git", "-C", root) + args, capture_output=True,
                             text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def verify_seal(root: str = KERNEL_ROOT) -> tuple[list[str], str | None]:
    """The seal names commit A and the digest of the manifest commit A froze."""
    problems: list[str] = []
    seal_path = os.path.join(root, "handoff", "SEAL.json")
    if not os.path.isfile(seal_path):
        return (["handoff/SEAL.json is absent; commit B of the two-commit freeze "
                 "has not landed"], None)

    with open(seal_path, encoding="utf-8") as fh:
        seal = json.load(fh)

    sealed_commit = seal.get("frozen_at_commit")
    declared = seal.get("bundle_digest")

    if seal.get("contract_version") != CONTRACT_VERSION:
        problems.append(
            f"seal names contract_version {seal.get('contract_version')!r}, "
            f"this bundle is {CONTRACT_VERSION!r}"
        )

    actual = bundle_digest(root)
    if declared != actual:
        problems.append(
            f"bundle digest mismatch: seal says {declared}, manifest hashes to {actual}"
        )

    if not sealed_commit:
        problems.append("seal names no commit A")
    else:
        if _git(root, "cat-file", "-e", f"{sealed_commit}^{{commit}}") is None:
            problems.append(f"commit A {sealed_commit[:12]} is not in this repository")
        else:
            head = _git(root, "rev-parse", "HEAD")
            if head and head != sealed_commit:
                merge_base = _git(root, "merge-base", "--is-ancestor",
                                  sealed_commit, "HEAD")
                # --is-ancestor prints nothing; None means non-zero exit.
                if merge_base is None:
                    problems.append(
                        f"commit A {sealed_commit[:12]} is not an ancestor of HEAD; "
                        "the seal describes a history this branch does not contain"
                    )
    return problems, sealed_commit


def run_vectors(root: str = KERNEL_ROOT) -> tuple[int, list[str], list[str]]:
    """Every vector must land on its declared expectation."""
    try:
        import jsonschema
    except ImportError:
        return 0, [], ["jsonschema is not installed; vectors could not be run"]

    passed = 0
    failed: list[str] = []
    skipped: list[str] = []

    for rel in _vector_paths():
        with open(os.path.join(root, rel), encoding="utf-8") as fh:
            vector = json.load(fh)
        schema_path = os.path.join(root, "handoff", "schemas",
                                   f"{vector['schema']}.schema.json")
        if not os.path.isfile(schema_path):
            skipped.append(f"{vector['vector_id']}: no schema {vector['schema']}")
            continue
        with open(schema_path, encoding="utf-8") as fh:
            schema = json.load(fh)

        validator = jsonschema.Draft202012Validator(schema)
        errors = list(validator.iter_errors(vector["document"]))
        validates = not errors
        expected_accept = vector["expect"] == "ACCEPT"

        if validates == expected_accept:
            passed += 1
        elif expected_accept:
            failed.append(
                f"{vector['vector_id']}: expected ACCEPT, schema refused it "
                f"({errors[0].message})"
            )
        else:
            failed.append(
                f"{vector['vector_id']}: expected REJECT, schema admitted it — "
                f"{vector['why']}"
            )
    return passed, failed, skipped


def run(root: str = KERNEL_ROOT) -> ConformanceReport:
    report = ConformanceReport()
    report.integrity, report.bundle_digest = check_integrity(root)
    report.seal, report.sealed_commit = verify_seal(root)
    report.vectors_passed, report.vectors_failed, report.vectors_skipped = \
        run_vectors(root)
    return report


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m handoff.conform")
    parser.add_argument("--emit-manifest", action="store_true",
                        help="write handoff/BUNDLE_MANIFEST.json (commit A only)")
    parser.add_argument("--json", action="store_true", help="machine-readable report")
    args = parser.parse_args(argv)

    if args.emit_manifest:
        manifest = build_manifest()
        with open(BUNDLE_MANIFEST_PATH, "wb") as fh:
            fh.write(serialize_manifest(manifest))
        print(f"wrote handoff/BUNDLE_MANIFEST.json — {manifest['file_count']} files")
        print(f"bundle digest: {sha256_file(BUNDLE_MANIFEST_PATH)}")
        return 0

    report = run()

    if args.json:
        json.dump(report.to_dict(), sys.stdout, indent=2)
        print()
        return 0 if report.ok else 1

    print("=" * 74)
    print(f"UNIIMENTE HANDOFF CONFORMANCE — contract {report.contract_version}")
    print("=" * 74)
    print(f"bundle digest : {report.bundle_digest}")
    print(f"sealed commit : {report.sealed_commit}")
    print(f"files sealed  : {len(bundle_paths())}")
    print()

    print(f"[{'PASS' if not report.integrity else 'FAIL'}] bundle integrity")
    for p in report.integrity:
        print(f"       - {p}")

    print(f"[{'PASS' if not report.seal else 'FAIL'}] seal")
    for p in report.seal:
        print(f"       - {p}")

    total = report.vectors_passed + len(report.vectors_failed)
    print(f"[{'PASS' if not report.vectors_failed else 'FAIL'}] acceptance vectors "
          f"{report.vectors_passed}/{total}")
    for p in report.vectors_failed:
        print(f"       - {p}")
    for p in report.vectors_skipped:
        print(f"       ~ skipped: {p}")

    print()
    print("RESULT:", "CONFORMANT" if report.ok else "NON-CONFORMANT")
    print()
    print("This report verifies a bundle. It authorizes nothing.")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
