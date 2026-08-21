"""BenchmarkAdapter — witness-only deterministic benchmark execution (WP-05).

The bounded side effect of an evolution cycle: run the pinned measurement
harness for a pre-registered ExperimentSpec and attest the result.

Constitutional reasoning:

- Hard Rule 1 (witness): inherited from ``BoundedAdapter`` — ``execute``
  re-verifies the CommitWitness (presence, type, signature against the
  authority key, expiry, one-use) before ANY harness code loads. No witness,
  no measurement. The harness the adapter runs is the one named by the PINNED
  PROTOCOL inside ``witness.expected_outcome`` — the document the
  founder-approved fingerprint binds — never a caller-supplied path, and the
  reference must sit in the construction-time allowlist (anything else is
  refused).
- Hard Rule 4 (fail closed on ANY ambiguity): an unparseable protocol, a
  non-allowlisted ``harness_ref``, a missing harness entry point, or ANY
  mismatch between the executed workload's op trace and the pinned protocol
  op lists raises ``ExecutionRefusal`` BEFORE the receipt is produced.
- Hard Rule 5 (determinism): the metric is connection op-count on a fake
  DBAPI (SPEC-WP05 3.4 ADR-4) — no wall clock, no network, no DSN anywhere
  in the measurement path.

Reconciliation semantics (WP-03 ADR-6 contract shape, NOT reopened): the
attestation hash is ``sha256_hex(canonical_json(witness.expected_outcome))``,
so the gate's RECONCILE stage passes iff the pinned protocol was honored —
any deviation raises before this adapter returns. The measured values ride
in the signed receipt facts (``external_id`` canonical JSON), the only free
result field in the WP-01 receipt shape; the VerifierRecord stage later
re-checks those facts against an independent re-run.

Pinned protocol (canonical JSON in ``witness.expected_outcome``) keys:
``workload_id``, ``harness_ref``, ``baseline_ops``, ``candidate_ops``,
``metric``, ``baseline_trace``, ``candidate_trace``. The trace lists pin not
just the op counts but the exact op ORDER of both measurement paths.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Sequence

from ..contracts.execution import CommitWitness
from ..crypto.hashing import canonical_json, sha256_hex
from ..gate import errors
from .base import BoundedAdapter

ADAPTER_ID = "benchmark-adapter"

# The exact key set of the pinned protocol document (fail closed on drift).
_PROTOCOL_KEYS = frozenset(
    {
        "workload_id",
        "harness_ref",
        "baseline_ops",
        "candidate_ops",
        "metric",
        "baseline_trace",
        "candidate_trace",
    }
)

REPO_ROOT = Path(__file__).resolve().parents[2]


class BenchmarkAdapter(BoundedAdapter):
    """Witness-only deterministic benchmark adapter (one action family).

    Family membership is enforced by the pinned protocol shape: a witness
    whose ``expected_outcome`` does not parse as a protocol document naming
    an allowlisted harness is refused at protocol validation.
    """

    def __init__(
        self,
        *,
        adapter_id: str = ADAPTER_ID,
        harness_allowlist: Sequence[str] = ("scripts/wp05_bench.py",),
        repo_root: str | Path | None = None,
        **kwargs,
    ):
        super().__init__(adapter_id=adapter_id, **kwargs)
        allowlist = tuple(harness_allowlist)
        if not allowlist or any(not isinstance(h, str) or not h for h in allowlist):
            raise ValueError("harness allowlist must be non-empty (fail closed)")
        self._harness_allowlist = allowlist
        self._repo_root = Path(repo_root) if repo_root is not None else REPO_ROOT
        self.calls = 0
        self.executed_witness_ids: list[str] = []

    @property
    def harness_allowlist(self) -> tuple[str, ...]:
        return self._harness_allowlist

    # ------------------------------------------------------------- perform

    def _parse_protocol(self, witness: CommitWitness) -> dict:
        """Parse the pinned protocol document; refuse on any ambiguity."""
        stage = "EXECUTE"
        try:
            doc = json.loads(witness.expected_outcome)
        except (TypeError, ValueError) as exc:
            raise errors.ExecutionRefusal(
                f"expected_outcome is not a parseable protocol document: {exc!r}",
                stage=stage,
            ) from exc
        if not isinstance(doc, dict) or set(doc.keys()) != _PROTOCOL_KEYS:
            raise errors.ExecutionRefusal(
                "protocol document must carry exactly the keys "
                f"{sorted(_PROTOCOL_KEYS)}; ambiguity fails closed",
                stage=stage,
            )
        return doc

    def _load_harness(self, harness_ref: str):
        """Load the allowlisted harness module from its repo-relative path."""
        stage = "EXECUTE"
        if harness_ref not in self._harness_allowlist:
            raise errors.ExecutionRefusal(
                f"harness {harness_ref!r} is not in the benchmark allowlist "
                "(refused before any code loads)",
                stage=stage,
            )
        path = self._repo_root / harness_ref
        if not path.is_file():
            raise errors.ExecutionRefusal(
                f"harness {harness_ref!r} does not exist", stage=stage
            )
        spec = importlib.util.spec_from_file_location("wp05_pinned_harness", path)
        if spec is None or spec.loader is None:
            raise errors.ExecutionRefusal(
                f"harness {harness_ref!r} is not loadable", stage=stage
            )
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            raise errors.ExecutionRefusal(
                f"harness {harness_ref!r} failed to load: {exc!r}", stage=stage
            ) from exc
        for entry_point in ("measure_baseline", "measure_candidate"):
            if not callable(getattr(module, entry_point, None)):
                raise errors.ExecutionRefusal(
                    f"harness {harness_ref!r} lacks {entry_point}(); fail closed",
                    stage=stage,
                )
        return module, path

    def _perform(self, witness: CommitWitness) -> tuple[str, str | None]:
        """Run the pinned harness and attest; any deviation raises FIRST.

        Returns (attestation_hash, external_id): the ADR-6 outcome-attestation
        hash over the pinned protocol, and the signed receipt facts carrying
        the measured values the verifier later re-checks.
        """
        stage = "EXECUTE"
        protocol = self._parse_protocol(witness)
        module, harness_path = self._load_harness(protocol["harness_ref"])

        baseline_value, baseline_trace = module.measure_baseline()
        candidate_value, candidate_trace = module.measure_candidate()

        # Op-trace verification: the executed workload must match the pinned
        # protocol op lists EXACTLY — counts and order (Hard Rule 4).
        if (
            int(baseline_value) != protocol["baseline_ops"]
            or int(candidate_value) != protocol["candidate_ops"]
            or list(baseline_trace) != list(protocol["baseline_trace"])
            or list(candidate_trace) != list(protocol["candidate_trace"])
        ):
            raise errors.ExecutionRefusal(
                "executed workload contradicts the pinned protocol "
                f"(measured baseline={baseline_value}, candidate={candidate_value}; "
                f"pinned baseline_ops={protocol['baseline_ops']}, "
                f"candidate_ops={protocol['candidate_ops']})",
                stage=stage,
            )

        harness_sha256 = sha256_hex(harness_path.read_bytes())
        source_ref = getattr(module, "MEASURED_SOURCE", None)
        if not isinstance(source_ref, str) or not source_ref:
            raise errors.ExecutionRefusal(
                "harness does not declare MEASURED_SOURCE; fail closed", stage=stage
            )
        source_path = self._repo_root / source_ref
        if not source_path.is_file():
            raise errors.ExecutionRefusal(
                f"measured source {source_ref!r} does not exist", stage=stage
            )
        baseline_source_sha256 = sha256_hex(source_path.read_bytes())

        facts = {
            "workload_id": protocol["workload_id"],
            "metric": protocol["metric"],
            "baseline_value": float(baseline_value),
            "candidate_value": float(candidate_value),
            "baseline_source_sha256": baseline_source_sha256,
            "harness_sha256": harness_sha256,
        }
        # Outcome-attestation hash (ADR-6): identical semantics to EchoAdapter
        # and to what the gate's RECONCILE stage verifies.
        attestation_hash = sha256_hex(canonical_json(witness.expected_outcome).encode("utf-8"))
        self.calls += 1
        self.executed_witness_ids.append(witness.id)
        return attestation_hash, canonical_json(facts)
