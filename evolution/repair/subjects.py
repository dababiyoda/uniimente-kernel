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

# ---------------------------------------------------------------------------
# SR-002 — fixed source binding for current evaluations.
SR002 = SubjectBinding("sr002-0.1.0",
    "07af5758197501662df81ff05e2b34ce8224a322",
    (
        ("constitution/constitution.ucl",
         "5c269850d8da799db66030103c52a175596d9c5f3bb61d25f54d7da9dde2ecd0"),
        ("constitution/sovereignty.ucl",
         "dc44c1f4304d42791a9db634796584531d40ba6b46191f2cba3877e48ee7fbcc"),
        ("constitution/shutdown-policy.ucl",
         "e3b443663cc5ed81a8b8827d8feb49962f82f262e85c282113f534c2afab2e54"),
        ("constitution/amendment-policy.ucl",
         "0132d53ec1e770a526f0e57888235a0b0bac4ed14b443782da537fb70b2ac01f"),
        ("constitution/participant-rights.ucl",
         "feba5d83800cd5d04702087473eea4d38290950097072efc578cfd498d631687"),
        ("authority/authority-matrix.yaml",
         "bd763098ecbbfd6ea7e8c9d80b83ed329fefd4766e53ed9b11006719fc671a45"),
        ("authority/legal-principals.yaml",
         "bff91ae68dcf54aed7e4021c30d5230a25b35a2167928ddd70842702a2bd732b"),
        ("authority/reserved-matters.yaml",
         "f185e0d11dec25e2bc3dbb73ce92bbb5d276358d1ac8abcaca7526a2805eb924"),
        ("identity/organ-registry.yaml",
         "995810a39c21f7e8da811598fdd83e2fe07127c51656c9652d2283d98c3f1085"),
        ("identity/agent-registry.yaml",
         "533e919e6c1cb918cfd249765f35ab24efc24729d79af804d09d96d65d45d20e"),
        ("identity/service-identities.yaml",
         "cd8c2c493b22a25926bbcedb049ebe28d86bd6e087ab920c0bbe2bae08cceac0"),
        ("policy/consequence_gate.py",
         "1c189be5af884932ed2115557b5a285883a2c6045af183c7f6f65a0815a06f2e"),
    ),
    "7755bdc6759a153f113cf4af98815f899b9a047aaf679fd38faff16b44f4aab8")
