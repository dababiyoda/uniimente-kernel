"""P2 — evaluator sovereignty: build a chamber and prove it is actually a boundary.

The founder's correction governs this module: **"separate subprocess" is not
sufficient isolation.** A child process under the same user that can read the
repository can still read the evaluator. Subprocess separation changes who is
running, not what is visible. Only a changed filesystem view is a boundary.

What this module establishes, measured rather than configured:

* ``unshare --mount`` alone is NOT a boundary. The new mount namespace inherits
  the parent's mount table, so the repository stays readable. This was measured
  first and is the reason the chamber does real bind-mount work.
* ``unshare --net`` IS a boundary for networking — the chamber sees zero
  interfaces and cannot connect.
* A chroot into a chamber whose only bind mounts are the language runtime, with
  the chamber root remounted read-only and a single writable tmpfs at ``/work``,
  excludes the repository entirely.
* ``env -i`` is required. The host environment leaked a live cloud credential
  into the chamber until it was cleared.

The result is reported by property, not by technology: a probe attempts every
prohibited route and each attempt yields a receipt. "The candidate did not
happen to try it" is not evidence.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field

HERE = os.path.dirname(os.path.abspath(__file__))
CHAMBER_SH = os.path.join(HERE, "chamber.sh")
HOSTILE_PROBE_SH = os.path.join(HERE, "hostile_probe.sh")


def repo_root() -> str:
    return os.path.dirname(os.path.dirname(HERE))


#: Routes the probe attempts. Every one must be denied in an isolated chamber.
#: ``write_own_chamber`` is the inverse control: it must SUCCEED, otherwise the
#: chamber is merely broken rather than isolated and the probe would report a
#: clean sheet for the wrong reason.
PROHIBITED_ROUTES = (
    "read_frozen_contract",
    "read_evaluator_dir",
    "read_repair_spec",
    "read_git_objects",
    "read_constitution",
    "read_authority",
    "traverse_to_parent_repo",
    "network_ifaces",
    "network_connect",
    "write_outside_chamber",
    "env_leaks_protected",
    # P2.1 — privilege-derived routes. The original eleven proved the enumerated
    # paths were blocked for that probe; they said nothing about what arbitrary
    # candidate code could do with retained root and capabilities.
    "running_as_root",
    "capabilities_dropped",
    "no_new_privs",
    "can_mount",
    "can_mknod",
    "can_chroot_escape",
)
REQUIRED_SUCCESS_ROUTE = "write_own_chamber"


class IsolationUnavailable(RuntimeError):
    """The environment cannot construct a chamber at all.

    Raised rather than returning a soft failure, because a caller that treats
    "could not build the chamber" as "nothing breached" would convert an
    unrunnable experiment into a passing one.
    """


@dataclass
class ProbeResult:
    """Receipts from one hostile-probe run."""

    mode: str
    returncode: int
    raw: str
    receipts: dict[str, str] = field(default_factory=dict)

    @property
    def breaches(self) -> list[str]:
        return sorted(k for k, v in self.receipts.items() if v == "BREACH")

    @property
    def vacuous_routes(self) -> list[str]:
        """Routes whose subject does not exist, so 'denied' proves nothing.

        Reported separately so a denial that only means "the file was never
        there" is never counted as evidence of a boundary.
        """
        missing = []
        root = repo_root()
        subjects = {
            "read_frozen_contract": "runtime/contract.py",
            "read_repair_spec": "evolution/repair/spec.py",
            "read_git_objects": ".git",
            "read_constitution": "constitution/constitution.ucl",
            "read_authority": "authority/authority-matrix.yaml",
        }
        for route, rel in subjects.items():
            if not os.path.exists(os.path.join(root, rel)):
                missing.append(route)
        # The evaluator directory contains this file, so it always exists; the
        # probe's check targets a path that may legitimately be absent until
        # held-out cases are created.
        if not os.path.isdir(os.path.join(root, "runtime", "evaluator", "heldout")):
            missing.append("read_evaluator_dir")
        return sorted(missing)


def _parse(raw: str) -> dict[str, str]:
    receipts: dict[str, str] = {}
    for line in raw.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] in PROHIBITED_ROUTES + (REQUIRED_SUCCESS_ROUTE,):
            receipts[parts[0]] = parts[-1]
    return receipts


def run_probe(mode: str, chamber_root: str | None = None) -> ProbeResult:
    """Run the hostile probe inside a chamber.

    ``mode='isolated'`` builds the intended boundary. ``mode='broken'``
    deliberately bind-mounts the repository into the chamber — the negative
    control that proves the probe can still detect a breach.
    """
    if mode not in ("isolated", "broken", "broken_privilege"):
        raise ValueError(f"unknown mode {mode!r}")
    if not shutil.which("unshare"):
        raise IsolationUnavailable("unshare is not available in this environment")
    if os.geteuid() != 0:
        raise IsolationUnavailable(
            "chamber construction needs mount privileges; running unprivileged"
        )

    cleanup = chamber_root is None
    chamber_root = chamber_root or tempfile.mkdtemp(prefix="uniimente-chamber-")
    env = dict(os.environ, REPO_ROOT=repo_root())
    try:
        proc = subprocess.run(
            [
                "unshare", "--mount", "--net", "--pid", "--fork",
                CHAMBER_SH, chamber_root, mode, HOSTILE_PROBE_SH,
            ],
            capture_output=True, text=True, timeout=120, env=env, check=False,
        )
    except subprocess.SubprocessError as exc:  # pragma: no cover - environment
        raise IsolationUnavailable(f"chamber could not be launched: {exc}") from exc
    finally:
        if cleanup:
            subprocess.run(["umount", "-R", chamber_root],
                           capture_output=True, check=False)
            shutil.rmtree(chamber_root, ignore_errors=True)

    raw = proc.stdout + proc.stderr
    receipts = _parse(raw)
    if not receipts:
        raise IsolationUnavailable(
            f"chamber produced no receipts (rc={proc.returncode}); "
            f"the probe did not run: {raw[:400]}"
        )
    return ProbeResult(mode=mode, returncode=proc.returncode, raw=raw, receipts=receipts)


@dataclass
class IsolationVerdict:
    """The P2 result. ``PROVEN`` requires discrimination, not merely silence."""

    isolated: ProbeResult
    broken: ProbeResult
    broken_privilege: ProbeResult | None = None

    @property
    def discriminates(self) -> bool:
        """The probe must behave differently in the two configurations.

        Identical results mean the instrument is dead — it would report the same
        thing whether or not a boundary existed, which is exactly the failure
        mode this workstream has produced eight times.
        """
        fs = not self.isolated.breaches and bool(self.broken.breaches)
        if self.broken_privilege is None:
            return fs
        return fs and bool(self.broken_privilege.breaches)

    @property
    def verdict(self) -> str:
        if self.isolated.breaches:
            return "EVALUATOR_ISOLATION_NOT_PROVEN"
        if not self.broken.breaches:
            return "EVALUATOR_ISOLATION_NOT_PROVEN"  # filesystem probe is dead
        if self.broken_privilege is None:
            # P2.1: without a privilege control the claim covers only the
            # enumerated filesystem routes, not arbitrary candidate code.
            return "EVALUATOR_ISOLATION_PROVEN_FOR_ENUMERATED_ROUTES"
        if not self.broken_privilege.breaches:
            return "EVALUATOR_ISOLATION_NOT_PROVEN"  # privilege probe is dead
        return "EVALUATOR_ISOLATION_PROVEN"

    def to_dict(self) -> dict:
        return {
            "verdict": self.verdict,
            "discriminates": self.discriminates,
            "isolated_breaches": self.isolated.breaches,
            "broken_breaches": self.broken.breaches,
            "broken_privilege_breaches": (
                self.broken_privilege.breaches if self.broken_privilege else None
            ),
            "isolated_receipts": self.isolated.receipts,
            "broken_receipts": self.broken.receipts,
            "vacuous_routes": self.isolated.vacuous_routes,
            "routes_attempted": len(PROHIBITED_ROUTES),
        }


def prove_isolation() -> IsolationVerdict:
    """Run both configurations and return the discriminating verdict."""
    return IsolationVerdict(
        isolated=run_probe("isolated"),
        broken=run_probe("broken"),
        broken_privilege=run_probe("broken_privilege"),
    )


if __name__ == "__main__":  # pragma: no cover - manual invocation
    import json
    import sys

    try:
        verdict = prove_isolation()
    except IsolationUnavailable as exc:
        print(json.dumps({"verdict": "EVALUATOR_ISOLATION_NOT_PROVEN",
                          "reason": str(exc)}, indent=2))
        sys.exit(2)
    print(json.dumps(verdict.to_dict(), indent=2, sort_keys=True))
    sys.exit(0 if verdict.verdict == "EVALUATOR_ISOLATION_PROVEN" else 1)
