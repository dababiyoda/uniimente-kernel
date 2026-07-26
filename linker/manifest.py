"""Organ Manifest loading and validation.

Doctrine (LINKER): a manifest is a signed self-description, never a grant.
Loading one confers nothing. Validation fails closed: a manifest that does
not match the contract does not enter the link graph, and the missing
fields are named instead of guessed.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

import yaml

KERNEL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST_SCHEMA_PATH = os.path.join(KERNEL_ROOT, "contracts", "organ-manifest.schema.json")
ORGANS_DIR = os.path.join(KERNEL_ROOT, "organs")


class ManifestError(ValueError):
    """Invalid organ manifest. Fails closed; the organ stays unlinked."""


@dataclass
class OrganManifest:
    organ_id: str
    name: str
    role: str
    repository: str | None
    capabilities: list[dict]
    consumes: list[str]
    produces: list[str]
    prohibited_actions: list[str]
    authority: dict
    health: dict
    status: str
    unresolved: list[str] = field(default_factory=list)
    raw: dict = field(default_factory=dict)


def _schema():
    with open(MANIFEST_SCHEMA_PATH) as f:
        return json.load(f)


def load_manifest(path: str) -> OrganManifest:
    """Load one manifest file, validate it against the contract, and return
    the typed view. Raises ManifestError naming every violation."""
    import jsonschema

    with open(path) as f:
        data = yaml.safe_load(f)
    validator = jsonschema.Draft202012Validator(_schema())
    problems = [f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
                for e in validator.iter_errors(data)]
    if problems:
        raise ManifestError(f"manifest {os.path.basename(path)} invalid: {problems}")
    return OrganManifest(
        organ_id=data["organ_id"], name=data["name"], role=data["role"],
        repository=data.get("repository"),
        capabilities=data["capabilities"],
        consumes=data["contracts"]["consumes"],
        produces=data["contracts"]["produces"],
        prohibited_actions=data["prohibited_actions"],
        authority=data["authority"], health=data["health"], status=data["status"],
        unresolved=data.get("unresolved", []), raw=data)


def load_all(organs_dir: str = ORGANS_DIR) -> list[OrganManifest]:
    manifests = []
    for name in sorted(os.listdir(organs_dir)):
        if name.endswith(".manifest.yaml"):
            manifests.append(load_manifest(os.path.join(organs_dir, name)))
    if not manifests:
        raise ManifestError(f"no manifests found in {organs_dir}")
    return manifests
