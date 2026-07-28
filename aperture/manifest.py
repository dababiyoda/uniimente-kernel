"""Loader for the one canonical authority declaration.

Everything that needs to know which authority system governs this repository
reads it from here: the CI singleton check, the disposition registry, the
import-boundary tests, runtime configuration and the docs. Nothing keeps its
own copy.

That is the whole point of this module. Gate A was previously marked closed
while the CI singleton check still named the defective legacy engine as the one
source of authority. Two hardcoded lists disagreed and a gate closed on the
strength of whichever happened to be consulted. A single loaded artifact cannot
drift against itself.
"""
from __future__ import annotations

import functools
import pathlib
from typing import Any

import yaml

from .certificate import CertificateError

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "authority" / "canonical-authority.yaml"


class ManifestError(CertificateError):
    """The canonical declaration is missing, malformed, or self-contradictory."""


@functools.lru_cache(maxsize=1)
def load(path: pathlib.Path | None = None) -> dict[str, Any]:
    p = path or MANIFEST_PATH
    if not p.exists():
        raise ManifestError(
            f"canonical authority manifest missing at {p}. Without it nothing in "
            "this repository can state which authority system governs it, so "
            "everything fails closed.", code="manifest_missing")
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    _validate(data)
    return data


def _validate(data: dict[str, Any]) -> None:
    ca = data.get("canonical_authority")
    if not ca:
        raise ManifestError("manifest has no canonical_authority block",
                            code="manifest_malformed")
    impls = data.get("implementations") or []
    issuers = [i for i in impls if i.get("may_issue_authority")]
    allowed = int(ca.get("active_issuers_allowed", 1))
    if len(issuers) != allowed:
        raise ManifestError(
            f"manifest declares active_issuers_allowed={allowed} but lists "
            f"{len(issuers)} implementations with may_issue_authority: "
            f"{[i['module'] for i in issuers]}", code="manifest_contradiction")
    if issuers and issuers[0]["module"] != ca["issuer"].rsplit(".", 1)[0]:
        raise ManifestError(
            f"manifest names issuer {ca['issuer']!r} but the implementation "
            f"marked may_issue_authority is {issuers[0]['module']!r}",
            code="manifest_contradiction")
    if ca.get("legacy_engines_active"):
        raise ManifestError("legacy_engines_active must be false",
                            code="manifest_contradiction")
    if ca.get("organ_local_issuers_allowed"):
        raise ManifestError("organ_local_issuers_allowed must be false",
                            code="manifest_contradiction")


# -- accessors ------------------------------------------------------------

def canonical() -> dict[str, Any]:
    return load()["canonical_authority"]


def canonical_issuer_module() -> str:
    return canonical()["issuer"].rsplit(".", 1)[0]


def canonical_issuer_symbol() -> str:
    return canonical()["issuer"].rsplit(".", 1)[1]


def forbidden_on_canonical_path() -> tuple[str, ...]:
    return tuple(load().get("forbidden_on_canonical_path", ()))


def implementations() -> tuple[dict[str, Any], ...]:
    return tuple(load().get("implementations", ()))


def implementation(module: str) -> dict[str, Any]:
    for i in implementations():
        if i["module"] == module:
            return i
    raise ManifestError(f"{module!r} has no declared disposition; every "
                        "authority-capable module must have exactly one",
                        code="undeclared_implementation")


def may_issue_authority(module: str) -> bool:
    try:
        return bool(implementation(module).get("may_issue_authority"))
    except ManifestError:
        return False


def active_issuer_count() -> int:
    return sum(1 for i in implementations() if i.get("may_issue_authority"))


def environments() -> dict[str, Any]:
    return load().get("environments", {})


def revocation_policy() -> dict[str, Any]:
    return load().get("revocation", {})


def revocation_policy_for(consequence_class: str) -> dict[str, Any]:
    by = revocation_policy().get("policy_by_consequence_class", {})
    if consequence_class not in by:
        raise ManifestError(
            f"no revocation policy declared for consequence class "
            f"{consequence_class!r}; refusing rather than guessing",
            code="revocation_policy_missing")
    return by[consequence_class]


def shadow_mode() -> dict[str, Any]:
    return load().get("shadow_mode", {})
