"""Explicit subject bindings; never rewrite the sealed Package 3 experiment.

SR-001 changes the gate under a later bounded founder direction. The old
experiment remains bound to its original bytes. A new run names both that
unchanged experiment and this separately reviewed subject, with no promotion.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path

from evolution.repair import spec


@dataclass(frozen=True)
class SubjectBinding:
    subject_id: str
    source_commit: str
    artifacts: tuple[tuple[str, str], ...]
    continuity_sha256: str

    def matches(self, root):
        combined = hashlib.sha256()
        for relative, expected in self.artifacts:
            raw = (Path(root) / relative).read_bytes()
            if hashlib.sha256(raw).hexdigest() != expected:
                return False
            combined.update(raw)
        return combined.hexdigest() == self.continuity_sha256

    def to_dict(self):
        return {"subject_id": self.subject_id, "source_commit": self.source_commit,
                "artifact_sha256": dict(self.artifacts),
                "continuity_sha256": self.continuity_sha256,
                "experiment_spec_sha256": spec.SPEC_SHA256,
                "authority": "test subject only; no promotion or authority grant"}


FROZEN = SubjectBinding("package3-original", spec.BASELINE_COMMIT,
    tuple(spec.CONTINUITY_ARTIFACT_SHA256.items()), spec.CONTINUITY_COMBINED_SHA256)

# Fixed before the successor evaluation. These are reviewed source commitments,
# not fingerprints silently measured from whatever code happens to be running.
SR001 = SubjectBinding("sr001-boundary-0.1.1",
    "3e059c20331d96e05a44daac1b097896aaabde93",
    tuple({**spec.CONTINUITY_ARTIFACT_SHA256,
        "policy/consequence_gate.py":
        "1c189be5af884932ed2115557b5a285883a2c6045af183c7f6f65a0815a06f2e"}.items()),
    "5594003e1f691bb4a20220505c932b69332c83743ece43a3325f5bbe89a19d70")

SR001_WORKFLOW_CLASS_SHA256 = {
    "DurableWorkflow": "7b303f6e5d268722221b6063b540ee0786fbe2675ab062c8c7b81e50b82220bb",
    "WorkflowStep": "ed63561261f29e9869f0626ec7fdd7bb505c21f1d8e9231c349753873310bbec",
}
