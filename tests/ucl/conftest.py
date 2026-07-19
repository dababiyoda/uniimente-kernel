"""Shared UCL fixtures — locate the real five-file constitution/ directory.

Primary location: <slice-root>/constitution (WP-02 vendors the five real
.ucl files there, byte-identical to uniimente-kernel@build/consequence-gate).
Fallback: walk upwards from this file for a repo checkout that carries
constitution/*.ucl (repo-relative layout).

All fixtures are deterministic: no wall-time, no randomness, no network.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from kernel.contracts.action import ActionIntent
from kernel.ucl import Constitution, compile_policy_fn, parse_file
from kernel.ucl.version import constitution_version_from_dir, policy_version

EXPECTED_FILES = (
    "amendment-policy.ucl",
    "constitution.ucl",
    "participant-rights.ucl",
    "shutdown-policy.ucl",
    "sovereignty.ucl",
)


def _has_five_files(path: Path) -> bool:
    return path.is_dir() and all((path / name).is_file() for name in EXPECTED_FILES)


def _locate_constitution_dir() -> Path:
    here = Path(__file__).resolve()
    candidates = [here.parents[2] / "constitution"]  # slice root
    candidates += [parent / "constitution" for parent in here.parents]  # repo-relative
    for candidate in candidates:
        if _has_five_files(candidate):
            return candidate
    raise RuntimeError(
        "could not locate a constitution/ directory containing the five .ucl files"
    )


@pytest.fixture(scope="session")
def constitution_dir() -> Path:
    """Path to the directory holding the five real .ucl files."""
    return _locate_constitution_dir()


@pytest.fixture(scope="session")
def constitution_documents(constitution_dir):
    """The five parsed UCL documents, sorted by filename (deterministic)."""
    files = sorted(constitution_dir.glob("*.ucl"), key=lambda p: p.name)
    return [parse_file(path) for path in files]


@pytest.fixture()
def make_model(constitution_dir):
    """Factory: Constitution model for a given current safety state."""

    def build(*, current_state: str = "normal") -> Constitution:
        return Constitution.from_directory(constitution_dir, current_state=current_state)

    return build


@pytest.fixture()
def model(make_model) -> Constitution:
    """The constitution model in the default ("normal") safety state."""
    return make_model()


@pytest.fixture()
def versions(constitution_dir, model) -> dict[str, str]:
    """Content-addressed versions for the real constitution."""
    return {
        "policy_version": policy_version(model),
        "constitution_version": constitution_version_from_dir(constitution_dir),
    }


@pytest.fixture()
def make_policy_fn(versions):
    """Factory: compile a policy_fn for a given model."""

    def build(model: Constitution):
        return compile_policy_fn(
            model,
            policy_version=versions["policy_version"],
            constitution_version=versions["constitution_version"],
        )

    return build


@pytest.fixture()
def policy_fn(make_policy_fn, model):
    """The compiled constitution in the default safety state."""
    return make_policy_fn(model)


def make_intent(**overrides) -> ActionIntent:
    """Golden C2 bounded research intent (overridable per test)."""
    fields = dict(
        actor_id="agent-7",
        organ_id="research-organ",
        legal_principal="Uniimente Ltd",
        objective="Research competitor pricing",
        action_type="research",
        resource="web",
        target="https://example.com/competitors",
        payload={"query": "competitor pricing", "max_pages": 3},
        consequence_class="C2",
        evidence_ids=[],
        expected_outcome="bounded research brief on competitor pricing",
        rollback=None,
        expiry_minutes=30,
    )
    fields.update(overrides)
    return ActionIntent(**fields)


def evaluate(policy_fn, intent, versions, *, trace=None):
    """Invoke a compiled policy_fn the way the gate does (EVALUATE stage)."""
    return policy_fn(
        intent,
        intent_fingerprint="f" * 64,
        policy_version=versions["policy_version"],
        constitution_version=versions["constitution_version"],
        trace=list(trace or []),
    )
