#!/usr/bin/env python3
"""The corrected authority singleton check.

PROPOSED REPLACEMENT for scripts/ci/check_authority_singleton.py, preserved on
this branch for human review. The old check is NOT deleted and NOT auto-swapped
in CI: a component must not alter its own approval requirements, and this check
polices the very change that introduces it.

Why the old one was wrong. It globbed `**/consequence_gate.py`, expected exactly
one, found `policy/consequence_gate.py`, and reported "exactly one source of
authority". That file is the engine with three verified authority defects. The
check was counting FILENAMES, not authority. It would have passed identically on
a tree where the gate could be bypassed entirely, and it would FAIL on a tree
where the canonical gate had legitimately moved.

What this one checks instead: the actual institutional invariant.

    one valid certificate issuer
  + one canonical authority protocol
  + zero organ-local issuers
  + zero active legacy authorizers

It is strictly stricter. Every condition the old check enforced is still
enforced (via the manifest's implementations list), plus eight it could not see.
"""
from __future__ import annotations

import ast
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from aperture import manifest              # noqa: E402
from aperture import dispositions as D     # noqa: E402

FAILURES: list[str] = []
CHECKS: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append(name)
    if ok:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}: {detail}")
        FAILURES.append(f"{name}: {detail}")


def _imports(path: pathlib.Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return set()
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def main() -> int:
    print("canonical authority manifest:", manifest.MANIFEST_PATH.relative_to(ROOT))
    ca = manifest.canonical()
    print(f"  architecture = {ca['architecture']}  protocol = {ca['protocol_name']}")
    print()

    # 1 - the manifest names the Reality Aperture, not a legacy engine.
    check("check_canonical_authority_manifest",
          ca["protocol_name"] == "reality_aperture"
          and ca["canonical_package"] == "aperture",
          f"manifest names {ca['protocol_name']!r}")

    # 2 - exactly one implementation may issue authority.
    n = manifest.active_issuer_count()
    check("check_single_valid_certificate_issuer", n == 1,
          f"{n} implementations declare may_issue_authority")

    # 3 - no legacy engine is active.
    check("check_no_active_legacy_authorizer",
          ca.get("legacy_engines_active") is False
          and not any(manifest.may_issue_authority(m)
                      for m in manifest.forbidden_on_canonical_path()),
          "a legacy engine is marked active or may issue authority")

    # 4 - organs may not issue locally.
    check("check_no_organ_local_issuer",
          ca.get("organ_local_issuers_allowed") is False,
          "organ_local_issuers_allowed is true")

    # 5 - the runtime disposition registry agrees with the manifest.
    #     This is the drift condition that invalidated the previous Gate A.
    problems = D.agrees_with_manifest()
    check("check_runtime_matches_disposition_registry", not problems,
          "; ".join(problems))

    # 6 - verification cannot sign.
    from aperture import VerificationRegistry
    pub = [a for a in dir(VerificationRegistry) if not a.startswith("_")]
    check("check_public_keys_cannot_sign",
          "sign" not in pub and all("sign" not in a.lower() or a == "verify"
                                    for a in pub),
          f"VerificationRegistry exposes {pub}")

    # 7 - canonical code does not import a superseded engine.
    offenders = []
    for py in (ROOT / ca["canonical_package"]).rglob("*.py"):
        for imp in _imports(py):
            for forbidden in manifest.forbidden_on_canonical_path():
                if imp == forbidden or imp.startswith(forbidden + "."):
                    offenders.append(f"{py.relative_to(ROOT)} -> {imp}")
    check("check_canonical_path_imports_clean", not offenders,
          "; ".join(offenders))

    # 8 - every consequence class has a declared revocation policy.
    missing = []
    for cls in ("internal_read", "internal_write", "external_contact",
                "financial", "irreversible"):
        try:
            manifest.revocation_policy_for(cls)
        except Exception as e:  # noqa: BLE001
            missing.append(f"{cls}: {e}")
    check("check_revocation_policy", not missing, "; ".join(missing))

    # 9 - high-consequence classes fail closed on stale revocation state.
    bad = []
    for cls in ("external_contact", "financial", "irreversible"):
        action = manifest.revocation_policy_for(cls)["on_stale_or_unavailable"]
        if action == "permit":
            bad.append(f"{cls} permits on stale revocation state")
    check("check_revocation_staleness", not bad, "; ".join(bad))

    # 10 - PRODUCTION key custody is disabled.
    envs = manifest.environments()
    check("check_production_custody_disabled",
          envs.get("PRODUCTION", {}).get("enabled") is False,
          "PRODUCTION custody is not explicitly disabled")

    # 11 - shadow mode forbids production adapters and credentials.
    sm = manifest.shadow_mode()
    check("check_shadow_has_no_production_credentials",
          sm.get("production_credentials_forbidden") is True
          and sm.get("real_external_effects_allowed") is False,
          "shadow mode does not forbid production credentials or effects")
    check("check_shadow_cannot_resolve_production_adapter",
          sm.get("production_adapters_forbidden") is True,
          "shadow mode does not forbid production adapters")

    # 12 - no environment variable may swap authority engines.
    #      An undocumented switch is a second government with a flag.
    suspicious = []
    for py in (ROOT / ca["canonical_package"]).rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        for line in text.splitlines():
            if "environ" in line and any(
                    k in line.lower() for k in ("engine", "gate", "issuer", "backend")):
                suspicious.append(f"{py.relative_to(ROOT)}: {line.strip()[:80]}")
    check("check_no_env_switch_for_authority_engine", not suspicious,
          "; ".join(suspicious))

    print()
    if FAILURES:
        print(f"{len(FAILURES)} of {len(CHECKS)} canonical authority checks FAILED")
        return 1
    print(f"all {len(CHECKS)} canonical authority checks pass")
    print(f"VALID_CANONICAL_CERTIFICATE_ISSUERS = {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
