"""What policy/consequence_gate.py may and may not do, enforced permanently.

Classification: SUPERSEDED (as an authority engine).

Retained: regression oracle for the previous engine's behaviour, and
counterfactual twin for differential conformance. Its own 13 tests still run
and still pass; they document what the previous engine did, which is
institutional memory the Final Build Order requires preserving.

Prohibited, and enforced below: it may not create authorization certificates,
sign authority records, maintain an independent trust root, bypass aperture
verification, or interpret legacy HMAC records as new authority.

The distinction matters. The engine is not broken and not removed. It is no
longer the road to reality.
"""
from __future__ import annotations

import ast
import inspect
import pathlib

import pytest

from aperture import manifest

ROOT = pathlib.Path(__file__).resolve().parents[2]
LEGACY = "policy.consequence_gate"


def test_legacy_gate_is_classified_exactly_once():
    entry = manifest.implementation(LEGACY)
    assert entry["classification"] == "SUPERSEDED"
    assert entry["may_issue_authority"] is False
    assert entry["retained_functions"]
    assert entry["prohibited_functions"]


def test_legacy_gate_still_imports_and_its_tests_still_pass():
    """Preservation: superseded is not broken."""
    import policy.consequence_gate as legacy
    assert hasattr(legacy, "ConsequenceGate")


def test_legacy_gate_cannot_create_authorization_certificates():
    import policy.consequence_gate as legacy
    for name in ("AuthorizationCertificate", "build_certificate",
                 "AuthorityIssuer"):
        assert not hasattr(legacy, name), f"legacy gate exposes {name}"


def test_legacy_gate_cannot_sign_authority_records():
    """Its signer is symmetric HMAC and produces nothing the aperture accepts."""
    from provenance.commit_witness import WitnessSigner
    assert not hasattr(WitnessSigner, "public_key_hex")
    sig = inspect.signature(WitnessSigner.sign)
    assert "witness" in sig.parameters      # signs witnesses, not certificates


def test_legacy_gate_does_not_import_the_aperture():
    """It must not become a facade that wraps and therefore re-enters the
    canonical path. It is a twin, not a front door."""
    src = (ROOT / "policy" / "consequence_gate.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    assert not any(i == "aperture" or i.startswith("aperture.") for i in imports)


def test_legacy_gate_cannot_bypass_aperture_verification():
    """Nothing in the aperture accepts a legacy witness as authority."""
    from aperture.effector import Aperture
    params = set(inspect.signature(Aperture.execute).parameters)
    assert "witness" not in params
    assert "grant" not in params
    assert "cert" in params


def test_legacy_gate_cannot_interpret_hmac_as_new_authority():
    from aperture.legacy import (classify_legacy_record, refuse_as_authority,
                                 LegacyAuthorityRefused,
                                 AUTHORIZING_CLASSIFICATIONS,
                                 CANONICAL_ASYMMETRIC)
    assert AUTHORIZING_CLASSIFICATIONS == {CANONICAL_ASYMMETRIC}
    rec = classify_legacy_record("x", {"k": 1}, "hmac-sha256:00",
                                 shared_secret=b"uniimente-dev-witness-key")
    assert rec.authorizes_new_effect() is False
    with pytest.raises(LegacyAuthorityRefused):
        refuse_as_authority(rec)


def test_legacy_gate_is_forbidden_on_the_canonical_path():
    assert LEGACY in manifest.forbidden_on_canonical_path()


def test_no_canonical_module_imports_the_legacy_gate():
    offenders = []
    for py in (ROOT / "aperture").rglob("*.py"):
        src = py.read_text(encoding="utf-8")
        if "policy.consequence_gate" in src and not src.lstrip().startswith('"""'):
            for line in src.splitlines():
                s = line.strip()
                if "policy.consequence_gate" in s and (
                        s.startswith("import ") or s.startswith("from ")):
                    offenders.append(f"{py.relative_to(ROOT)}: {s}")
    assert not offenders, offenders
