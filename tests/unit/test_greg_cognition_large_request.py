"""A numeric request larger than one argv string reaches its solver and its verifier on stdin.

Admission v8 demoted convex_qp_dual to NICHE because a held-out dense QP exceeded GREG's 64 KiB request limit; the
deeper cause was that the request travelled to the worker as one argv string, which Linux caps at 128 KiB.
"""
import pytest

from greg.cognition import cortex
from greg.cognition.contracts import CognitionError, canonical
from greg.cognition.genomes import admission, library


def test_a_dense_qp_over_the_argv_ceiling_is_solved_and_verified_on_the_canonical_path():
    data, _ = library.executables()["convex_qp_dual"].instance(5)        # development seed, about 500 KB
    assert len(canonical(data).encode()) > 256 * 1024
    out = admission.smoke("convex_qp_dual", 5)
    assert out["abstention_state"] == "NONE" and out["verifier"] == "STRUCTURALLY_VERIFIED"
    assert out["authority_created"] is False


def test_the_request_ceiling_still_binds():
    big = {"problem_id": "p", "operation": "x", "data": {"blob": "a" * (cortex.MAX_COGNITIVE_REQUEST_BYTES + 1)}}
    with pytest.raises(CognitionError, match="exceeds 1 MiB"):
        cortex.compile_problem(big)
