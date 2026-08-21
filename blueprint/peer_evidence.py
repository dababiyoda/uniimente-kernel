"""Evidence about a peer organ's repository, pinned to a commit and a hash.

Doctrine (PEER ATTESTATION): the frozen handoff contract records BLK-6 —
"Blueprint evidence locators are kernel-repository-relative. Capabilities
implemented in DALEOBANKS and WealthMachineIntelligence cannot be bound to an
implementation path from the kernel, so they stand at BLUEPRINT here even where
real code exists there." Owner: CLAUDE. The ladder therefore *understates* the
peers, and the contract says so.

The tempting fix is to let the binder read a sibling checkout. That is wrong: a
rung which depends on what happens to be on this machine is not reproducible, and
the binder's whole claim is that a rung resolves against a fixed tree.

What is sound is an attestation: a record committed *here* stating that at a named
commit of a named repository, a named path existed with a named content hash. The
kernel never pretends to see the peer tree. It holds a dated, commit-pinned,
hash-bearing claim about it, and anyone can fetch that commit and check the hash.

What this cannot do, stated plainly:

* It cannot prove the peer code *works*. It proves a file existed with those
  bytes. That is exactly what IMPLEMENTATION_PATH claims inside this repository
  too — "code exists on disk" — and no more.
* It cannot prove the attestation was generated honestly. It can only be
  falsified: the commit and hash are both recorded, so a wrong one is checkable
  by a third party. That is the difference between an unverifiable claim and a
  refutable one.
* It goes stale by design. An attestation describes one commit. A peer that moves
  on does not invalidate the record; it means the record describes history, and
  the `attested_at` and `commit` fields say which history.

This module reads and writes attestations. It grants nothing and raises no rung on
its own: a binding must cite a `peer:` locator for any of this to matter.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone

ATTESTATION_VERSION = 1
KERNEL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ATTESTATION_DIR = os.path.join(KERNEL_ROOT, "blueprint", "attestations")

_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_ORGAN_RE = re.compile(r"^[a-z][a-z0-9-]*$")

#: `peer:<organ>/<path>` — the locator form a binding uses.
PEER_PREFIX = "peer:"


class PeerEvidenceError(ValueError):
    """An attestation is unanchored, malformed, or self-contradicting. Fails closed."""


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


@dataclass(frozen=True)
class AttestedPath:
    path: str
    kind: str                 # "file" or "directory"
    size: int
    digest: str | None        # None for a directory; files always carry one

    def __post_init__(self) -> None:
        if self.kind not in ("file", "directory"):
            raise PeerEvidenceError(f"{self.path}: kind must be file or directory")
        if self.kind == "file":
            if not self.digest or not self.digest.startswith("sha256:"):
                raise PeerEvidenceError(f"{self.path}: a file must carry a sha256 digest")
            if self.size <= 0:
                raise PeerEvidenceError(
                    f"{self.path}: zero bytes is not code, the same rule the kernel "
                    "applies to its own implementation paths")


@dataclass(frozen=True)
class PeerAttestation:
    """One peer repository at one commit, as read at attestation time."""

    organ: str
    repository: str
    commit: str
    attested_at: str
    method: str
    paths: tuple[AttestedPath, ...]
    limitations: tuple[str, ...] = ()
    version: int = ATTESTATION_VERSION

    def __post_init__(self) -> None:
        if not _ORGAN_RE.match(self.organ or ""):
            raise PeerEvidenceError(f"organ {self.organ!r} is not a short lowercase name")
        if not _COMMIT_RE.match(self.commit or ""):
            raise PeerEvidenceError(
                f"attestation for {self.organ} must pin a full 40-character commit; "
                f"got {self.commit!r}. An unpinned attestation cannot be checked.")
        if "/" not in self.repository:
            raise PeerEvidenceError(
                f"repository {self.repository!r} must be owner/name so a third party "
                "can fetch it")
        if not self.paths:
            raise PeerEvidenceError(
                f"attestation for {self.organ} names no paths, so it attests nothing")
        seen = [p.path for p in self.paths]
        if len(set(seen)) != len(seen):
            raise PeerEvidenceError(f"attestation for {self.organ} repeats a path")

    def by_path(self) -> dict[str, AttestedPath]:
        return {p.path: p for p in self.paths}

    def to_obj(self) -> dict:
        return {
            "version": self.version,
            "organ": self.organ,
            "repository": self.repository,
            "commit": self.commit,
            "attested_at": self.attested_at,
            "method": self.method,
            "limitations": list(self.limitations),
            "paths": [
                {"path": p.path, "kind": p.kind, "size": p.size, "digest": p.digest}
                for p in sorted(self.paths, key=lambda p: p.path)
            ],
        }

    @classmethod
    def from_obj(cls, obj: dict) -> PeerAttestation:
        if obj.get("version") != ATTESTATION_VERSION:
            raise PeerEvidenceError(
                f"attestation version {obj.get('version')!r} is not "
                f"{ATTESTATION_VERSION}; refusing a format this code does not define")
        return cls(
            organ=obj["organ"],
            repository=obj["repository"],
            commit=obj["commit"],
            attested_at=obj["attested_at"],
            method=obj["method"],
            limitations=tuple(obj.get("limitations") or ()),
            paths=tuple(
                AttestedPath(path=p["path"], kind=p["kind"], size=int(p["size"]),
                             digest=p.get("digest"))
                for p in obj["paths"]),
        )


def attest(organ: str, repository: str, commit: str, checkout: str,
           paths: list[str], limitations: tuple[str, ...] = ()) -> PeerAttestation:
    """Read a real checkout and record what is there. Derived, never supplied.

    Every path is resolved against `checkout` and hashed. A path that is absent
    raises rather than being recorded as missing: an attestation is a statement
    that these things exist, so it must not be constructible when they do not.
    """
    recorded: list[AttestedPath] = []
    for relative in sorted(set(paths)):
        target = os.path.normpath(os.path.join(checkout, relative))
        if not (target == checkout or target.startswith(checkout + os.sep)):
            raise PeerEvidenceError(f"{relative} escapes the checkout")
        if os.path.isdir(target):
            entries = [n for n in os.listdir(target) if not n.startswith(".")]
            if not entries:
                raise PeerEvidenceError(f"{relative} is an empty directory")
            recorded.append(AttestedPath(relative, "directory", len(entries), None))
        elif os.path.isfile(target):
            recorded.append(AttestedPath(relative, "file", os.path.getsize(target),
                                         sha256_file(target)))
        else:
            raise PeerEvidenceError(
                f"{relative} does not exist in {repository} at {commit[:7]}")
    return PeerAttestation(
        organ=organ, repository=repository, commit=commit,
        attested_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        method=("read from a local checkout of the named repository at the named "
                "commit; sizes and sha256 digests recorded from the real bytes"),
        paths=tuple(recorded), limitations=limitations)


def write(attestation: PeerAttestation, directory: str = ATTESTATION_DIR) -> str:
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, f"{attestation.organ}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(attestation.to_obj(), fh, indent=2, sort_keys=True)
        fh.write("\n")
    return path


def load_all(root: str = KERNEL_ROOT) -> dict[str, PeerAttestation]:
    """Every attestation on record, keyed by organ. Unreadable ones are skipped."""
    directory = os.path.join(root, "blueprint", "attestations")
    out: dict[str, PeerAttestation] = {}
    if not os.path.isdir(directory):
        return out
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(directory, name), encoding="utf-8") as fh:
                attestation = PeerAttestation.from_obj(json.load(fh))
        except (OSError, json.JSONDecodeError, KeyError, PeerEvidenceError):
            continue
        out[attestation.organ] = attestation
    return out


def split_locator(locator: str) -> tuple[str, str] | None:
    """`peer:<organ>/<path>` -> (organ, path), or None when not a peer locator."""
    if not locator.startswith(PEER_PREFIX):
        return None
    remainder = locator[len(PEER_PREFIX):]
    organ, _, path = remainder.partition("/")
    if not organ or not path:
        return None
    return organ, path


# -------------------------------------------------------------------------- CLI

#: Which peer organ maps to which repository and manifest. The paths attested are
#: exactly the `implementation_path` values those manifests declare, so an
#: attestation run is also a check on the manifests' own claims: a manifest naming
#: a path that does not exist makes `attest` raise rather than record a gap.
PEERS = {
    "daleobanks": ("dababiyoda/DALEOBANKS", "organs/daleobanks.manifest.yaml"),
    "wealthmachine": ("dababiyoda/WealthMachineIntelligence",
                      "organs/wealthmachine.manifest.yaml"),
    "pumpstation": ("dababiyoda/PumpStation", "organs/pumpstation.manifest.yaml"),
    "research-in": ("dababiyoda/RESEARCH-IN", "organs/research-in.manifest.yaml"),
}

LIMITATIONS = (
    "Records that a path existed with these bytes at this commit. It does not "
    "prove the peer code works, is reachable, or is authorized.",
    "Describes one commit. A peer that moves on does not invalidate this record; "
    "the record then describes history, and `commit` says which.",
)


def declared_paths(manifest: str, root: str = KERNEL_ROOT) -> list[str]:
    """The implementation paths an organ manifest declares for its capabilities."""
    import yaml

    with open(os.path.join(root, manifest), encoding="utf-8") as fh:
        document = yaml.safe_load(fh) or {}
    return sorted({
        capability["implementation_path"]
        for capability in (document.get("capabilities") or [])
        if capability.get("implementation_path")
    })


def main(argv: list[str] | None = None) -> int:
    import argparse
    import subprocess

    parser = argparse.ArgumentParser(
        prog="python -m blueprint.peer_evidence",
        description="Attest peer organ implementation paths at a pinned commit.")
    parser.add_argument("command", nargs="?", default="show",
                        choices=("show", "write"))
    parser.add_argument("--checkout-root", default="/home/user",
                        help="directory holding the peer checkouts")
    args = parser.parse_args(argv)

    if args.command == "show":
        on_record = load_all()
        if not on_record:
            print("no attestations on record")
            return 0
        for organ, attestation in sorted(on_record.items()):
            print(f"{organ:<15} {attestation.repository:<42} "
                  f"{attestation.commit[:7]}  {len(attestation.paths)} paths  "
                  f"{attestation.attested_at}")
        return 0

    for organ, (repository, manifest) in sorted(PEERS.items()):
        checkout = os.path.join(args.checkout_root, repository.split("/", 1)[1])
        if not os.path.isdir(checkout):
            print(f"{organ:<15} SKIP  no checkout at {checkout}")
            continue
        commit = subprocess.run(["git", "-C", checkout, "rev-parse", "HEAD"],
                                capture_output=True, text=True).stdout.strip()
        paths = declared_paths(manifest)
        if not paths:
            print(f"{organ:<15} SKIP  manifest declares no implementation paths")
            continue
        try:
            attestation = attest(organ, repository, commit, checkout, paths,
                                 LIMITATIONS)
        except PeerEvidenceError as exc:
            print(f"{organ:<15} REFUSED  {exc}")
            continue
        write(attestation)
        print(f"{organ:<15} {commit[:7]}  {len(attestation.paths)} paths attested")
    return 0


if __name__ == "__main__":          # pragma: no cover - CLI entry
    raise SystemExit(main())
