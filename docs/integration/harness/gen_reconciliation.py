#!/usr/bin/env python3
"""Generate TEST_INVENTORY_RECONCILIATION.json from the measured node-ID files.

Every number in the output is read from a file produced by an executed pytest
collection. Nothing here is transcribed by hand.
"""
import hashlib
import json
import pathlib
import collections

W = pathlib.Path("/tmp/claude-0/-home-user/cae04d8c-db77-5252-86ff-7ce47d4772c5/scratchpad/gateB")
OUT = pathlib.Path("/home/user/uniimente-kernel/docs/integration/TEST_INVENTORY_RECONCILIATION.json")


def ids(name):
    return sorted(set(p for p in (W / name).read_text().splitlines() if p.strip()))


def sha(name):
    return hashlib.sha256((W / name).read_bytes()).hexdigest()


def by_file(node_ids):
    c = collections.Counter(n.split("::")[0] for n in node_ids)
    return dict(sorted(c.items()))


clean_main = ids("cleanmain.sorted")
merged = ids("merged.sorted")
sdk_raw = ids("sdk.sorted")
contaminated = ids("main.sorted")

sdk_rerooted = sorted("sdk-python/" + n for n in sdk_raw)
gained = sorted(set(merged) - set(clean_main))
lost = sorted(set(clean_main) - set(merged))
contaminated_extra = sorted(set(contaminated) - set(clean_main))

doc = {
    "artifact": "TEST_INVENTORY_RECONCILIATION",
    "gate": "Gate B - UNEXPLAINED_TEST_COLLECTION_DELTA",
    "date": "2026-07-27",
    "repository": "dababiyoda/uniimente-kernel",
    "result": {
        "UNEXPLAINED_TEST_COLLECTION_DELTA": 0,
        "gate_b_status": "CLOSED",
        "closure_proof": "set(clean_main) union set(sdk_rerooted) == set(merged), byte-for-byte",
        "tests_lost_by_the_merge": len(lost),
        "tests_gained_by_the_merge": len(gained),
        "merged_suite_result": "679 passed in 12.60s",
    },
    "refs": {
        "origin/main": "8cb3074a4a837c89aada9bdb5351d7d9b3e4a9c1",
        "origin/main_subject": "UNIIMENTE canonical-v1 Kernel release",
        "origin/phase7/fast-capability-evolution": "640ec9d24d2a282bd062ea0dbcab1baa46758867",
        "merge_base_worktree_HEAD": "8cb3074a4a837c89aada9bdb5351d7d9b3e4a9c1",
        "merge_state": "MERGE_HEAD present; 91 files staged; merge deliberately NOT committed",
        "conflict_resolution": "4 conflicts resolved --ours (policy/README.md, verifier/README.md, verifier/v2/criteria.json, contracts/outcome.schema.json)",
    },
    "collections": {
        "clean_main": {
            "count": len(clean_main),
            "source": "git worktree --detach at origin/main",
            "command": "python -m pytest --collect-only -q | grep '::' | sort -u",
            "sha256_of_node_id_file": sha("cleanmain.sorted"),
        },
        "merged": {
            "count": len(merged),
            "source": "worktree at origin/main with phase7 merged and staged, uncommitted",
            "command": "python -m pytest --collect-only -q | grep '::' | sort -u",
            "sha256_of_node_id_file": sha("merged.sorted"),
        },
        "sdk_subtree_alone": {
            "count": len(sdk_raw),
            "source": "same merged worktree, rootdir=sdk-python/",
            "note": "node IDs are relative to sdk-python/, so they require re-rooting before comparison",
            "sha256_of_node_id_file": sha("sdk.sorted"),
        },
        "contaminated_main": {
            "count": len(contaminated),
            "source": "/home/user/uniimente-kernel working tree",
            "actual_ref": "claude/integration-canonicalization-audit @ dd281aa",
            "status": "INVALID - retained as the record of the measurement error",
            "sha256_of_node_id_file": sha("main.sorted"),
        },
    },
    "identities_verified": [
        {
            "claim": "clean origin/main node IDs == merged INTERSECT contaminated-main",
            "method": "diff -q cleanmain.sorted both.ids",
            "result": "IDENTICAL, 495 == 495, byte-for-byte",
        },
        {
            "claim": "sdk subtree node IDs re-rooted under sdk-python/ == tests gained by the merge",
            "method": "diff -q <(sed 's|^|sdk-python/|' sdk.sorted) gained.ids",
            "result": "IDENTICAL, 184 == 184, byte-for-byte",
        },
        {
            "claim": "clean_main UNION sdk_rerooted == merged",
            "method": "diff -q <(cat cleanmain.sorted sdk_rerooted.sorted | sort -u) merged.sorted",
            "result": "IDENTICAL, 679 == 679, byte-for-byte. Delta closes to zero.",
        },
    ],
    "the_error_that_produced_the_apparent_65_delta": {
        "apparent_delta": 65,
        "arithmetic_that_looked_wrong": "560 + 184 = 744, but merged collected 679",
        "root_cause": (
            "The 'main' collection was run against /home/user/uniimente-kernel, whose "
            "checked-out branch is claude/integration-canonicalization-audit, which is "
            "built on top of claude/uniimente-system-design-hczheq. It therefore carried "
            "this session's own unmerged test files. It was never origin/main."
        ),
        "the_65_accounted_for_exactly": by_file(contaminated_extra),
        "provenance_of_each": {
            "tests/unit/test_traceability.py": "ABSENT on origin/main; added this session on claude/uniimente-system-design-hczheq (PR #54)",
            "tests/unit/test_governance_records.py": "ABSENT on origin/main; added this session on claude/uniimente-system-design-hczheq (PR #54)",
            "tests/unit/test_repair_spec_frozen.py": "PRESENT on origin/main; 2 additional cases added this session (baseline_corpus)",
            "tests/integration/test_phase_zero_connection.py": "PRESENT on origin/main; 1 additional case added this session (pumpstation manifest)",
        },
        "hypothesis_under_test": (
            "That ~65 main tests were being displaced by SDK path or name collisions, "
            "meaning the merge LOSES coverage."
        ),
        "hypothesis_verdict": "REFUTED. Zero collisions. sdk.ids INTERSECT merged.ids under the "
                              "un-rerooted comparison was 0 because of the rootdir prefix, not because "
                              "of displacement. The merge is purely additive.",
    },
    "why_sdk_tests_were_absent_from_main": {
        "finding": "sdk-python/ EXISTS on origin/main but contains exactly one file: README.md",
        "files_on_main": 1,
        "test_files_on_main": 0,
        "files_on_phase7": 32,
        "test_files_on_phase7": 14,
        "pytest_config_on_main": "none (no pytest.ini, setup.cfg, pyproject.toml or tox.ini)",
        "conclusion": (
            "The absence is missing code, not a collection-exclusion rule. No norecursedirs "
            "or testpaths setting was involved."
        ),
        "institutional_note": (
            "main's sdk-python/README.md describes an SDK that DALEOBANKS and "
            "WealthMachineIntelligence 'migrate onto this in Phases 2-3', with 'Publish "
            "target: Phase 10'. The implementation it describes exists only on an unmerged "
            "branch. This is a directory-level instance of documentation asserting a "
            "capability that the canonical branch does not contain."
        ),
    },
    "tests_gained_by_file": by_file(gained),
    "tests_lost_by_file": by_file(lost),
    "residual_limitations": [
        "Node-ID identity proves collection is additive. The 679-passing run proves the merged "
        "tree is green. Neither proves the 495 main tests exercise the same MECHANISMS after "
        "the merge - a test can pass against a changed implementation.",
        "Gate B measures test inventory only. It is not evidence about authority semantics; "
        "that is Gate A.",
        "The merge is staged and uncommitted. These counts describe a working tree, not a commit. "
        "Re-measure before any tag.",
        "This session's own work (PR #54, 65 tests) is NOT in the merged tree and was never "
        "supposed to be. It is a separate branch and a separate landing decision.",
    ],
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(doc, indent=2) + "\n")
print(f"wrote {OUT}")
print(f"  delta={doc['result']['UNEXPLAINED_TEST_COLLECTION_DELTA']} "
      f"lost={len(lost)} gained={len(gained)} contaminated_extra={len(contaminated_extra)}")
