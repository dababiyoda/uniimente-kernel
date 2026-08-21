#!/usr/bin/env python3
"""WP-04 Rebuild Drill — the Continuity Loop proof on the Postgres spine.

Proves the institution's continuity claim against a REAL Postgres (Neon)
spine, end to end:

    1. ORIGIN: run the full gate loop (compiled WP-02 constitution, echo
       adapter — no external network) into a FRESH drill-owned table
       ``wp04_origin`` (dropped and recreated by this script).
    2. RECORD origin state: count, head record_hash, verify_chain.
    3. DESTROY/REBUILD: replay ``wp04_origin.iter()`` into a fresh table
       ``wp04_rebuilt`` purely through ``PostgresSpine.append_record`` — the
       clearly-marked REBUILD-ONLY path that re-validates every record's
       hash against the frozen WP-01 formula before accepting it.
    4. PROVE: identical counts, identical seq-ordered record_hash lists,
       both verify_chain true, equal head hashes.
    5. NEGATIVE CONTROL: copy origin into ``wp04_tampered``, flip one byte
       in one payload via SQL, verify_chain must be False.
    6. Write proof/wp04_rebuild_capsule.json (NO DSN, NO credentials).
    7. One-line verdict; exit 0 only if all proofs hold.

Credentials: the DSN is read from the UNIIMENTE_SPINE_DSN environment
variable ONLY. It is never written to any file, test, or proof artifact.

Usage (from the slice root):
    UNIIMENTE_SPINE_DSN=... python scripts/rebuild_drill.py

Exit codes: 0 = all proofs hold; 1 = any proof failed; 2 = DSN env var absent.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from kernel.adapters.echo import EchoAdapter  # noqa: E402
from kernel.authority.approvals import ApprovalService  # noqa: E402
from kernel.contracts.action import ActionIntent  # noqa: E402
from kernel.gate.pipeline import Gate  # noqa: E402
from kernel.spine import PostgresSpine  # noqa: E402
from kernel.ucl import Constitution, compile_policy_fn  # noqa: E402
from kernel.ucl.version import constitution_version_from_dir, policy_version  # noqa: E402

# Drill-owned tables (never shared). Hardcoded identifiers — never
# interpolated from user input into raw SQL.
ORIGIN_TABLE = "wp04_origin"
REBUILT_TABLE = "wp04_rebuilt"
TAMPERED_TABLE = "wp04_tampered"
CAPSULE_PATH = REPO_ROOT / "proof" / "wp04_rebuild_capsule.json"
TAMPER_SEQ = 0  # ActionIntent record; payload field actor_id gets one byte flipped
TAMPER_FIELD = "payload.actor_id"

_DSN_HELP = (
    "UNIIMENTE_SPINE_DSN is not set. Export a Postgres DSN first, e.g.:\n"
    "  export UNIIMENTE_SPINE_DSN='postgresql://user:pass@host/dbname?sslmode=require'\n"
    "The DSN is read from the environment only and is never written to disk."
)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_gate_loop_into_origin(dsn: str) -> PostgresSpine:
    """Step 1: the full WP-01/WP-02/WP-03 loop, spine = wp04_origin."""
    constitution_dir = REPO_ROOT / "constitution"
    model = Constitution.from_directory(constitution_dir, current_state="normal")
    versions = {
        "policy_version": policy_version(model),
        "constitution_version": constitution_version_from_dir(constitution_dir),
    }
    policy_fn = compile_policy_fn(model, **versions)

    spine = PostgresSpine(dsn, table=ORIGIN_TABLE)
    authority = ApprovalService(approver_id="founder")
    gate = Gate(
        versions["policy_version"],
        versions["constitution_version"],
        authority,
        spine,
        policy_fn=policy_fn,
    )
    adapter = EchoAdapter(witness_public_key=authority.public_key)
    gate.register_adapter(adapter.adapter_id, adapter.public_key_hex)

    intent = ActionIntent(
        actor_id="uniimente-kernel",
        organ_id="research-organ",
        legal_principal="Uniimente Ltd",
        objective=(
            "WP-04 rebuild drill: seal one full gate loop on the Postgres "
            "spine, then prove rebuild-from-spine byte-identity"
        ),
        action_type="research_fetch",
        resource="web",
        target="echo://wp04-rebuild-drill",  # echo adapter: no network
        payload={"method": "GET", "max_bytes": 262144, "max_redirects": 3},
        consequence_class="C2",
        evidence_ids=[],
        expected_outcome="wp04 drill: simulated bounded research outcome",
        rollback=None,
        expiry_minutes=30,
    )
    approval = authority.issue_approval(gate.fingerprint(intent))
    episode = gate.run(intent, adapter=adapter, approval=approval)
    if not (episode.closed and episode.close_reason == "completed"):
        raise RuntimeError(f"gate loop did not complete: {episode.close_reason!r}")
    return spine


def main() -> int:
    dsn = os.environ.get("UNIIMENTE_SPINE_DSN")
    if not dsn:
        print(_DSN_HELP, file=sys.stderr)
        return 2
    try:
        import psycopg
    except ImportError:
        print(
            "rebuild_drill requires the psycopg v3 driver: "
            "pip install 'psycopg[binary]'",
            file=sys.stderr,
        )
        return 2

    # Drill-owned tables: drop and recreate from scratch every run.
    with psycopg.connect(dsn) as conn:
        for table in (ORIGIN_TABLE, REBUILT_TABLE, TAMPERED_TABLE):
            conn.execute(f"DROP TABLE IF EXISTS {table}")
        conn.commit()

    # 1-2. ORIGIN: full gate loop, then record state.
    origin = run_gate_loop_into_origin(dsn)
    origin_records = list(origin.iter())
    origin_count = len(origin_records)
    origin_head = origin_records[-1]["record_hash"] if origin_records else None
    origin_verify = origin.verify_chain()

    # 3. REBUILD: replay origin purely through the re-validating rebuild API.
    rebuilt = PostgresSpine(dsn, table=REBUILT_TABLE)
    for record in origin_records:
        rebuilt.append_record(record)

    # 4. PROVE byte-identity of the rebuilt chain.
    rebuilt_records = list(rebuilt.iter())
    rebuilt_count = len(rebuilt_records)
    rebuilt_head = rebuilt_records[-1]["record_hash"] if rebuilt_records else None
    rebuilt_verify = rebuilt.verify_chain()
    hash_parity = [r["record_hash"] for r in origin_records] == [
        r["record_hash"] for r in rebuilt_records
    ]
    rebuild_proof = (
        origin_count == rebuilt_count
        and hash_parity
        and origin_verify
        and rebuilt_verify
        and origin_head == rebuilt_head
        and origin_count > 0
    )

    # 5. NEGATIVE CONTROL: copy origin, flip one payload byte via SQL.
    PostgresSpine(dsn, table=TAMPERED_TABLE)  # idempotent DDL for the copy target
    with psycopg.connect(dsn) as conn:
        conn.execute(f"INSERT INTO {TAMPERED_TABLE} SELECT * FROM {ORIGIN_TABLE}")
        conn.execute(
            f"UPDATE {TAMPERED_TABLE} "
            f"SET payload = jsonb_set(payload, '{{actor_id}}', "
            f"to_jsonb((payload->>'actor_id') || 'X')) "
            f"WHERE seq = %s",
            (TAMPER_SEQ,),
        )
        conn.commit()
    tampered = PostgresSpine(dsn, table=TAMPERED_TABLE)
    tampered_verify = tampered.verify_chain()
    tamper_control = tampered_verify is False

    ok = bool(rebuild_proof and tamper_control)

    # 6. Capsule — NO DSN, NO credentials anywhere.
    capsule = {
        "capsule_schema": "wp04-rebuild-capsule/1.0",
        "generated_at": _utcnow_iso(),  # wall clock: capsule metadata only
        "ok": ok,
        "tables": {
            "origin": ORIGIN_TABLE,
            "rebuilt": REBUILT_TABLE,
            "tampered": TAMPERED_TABLE,
        },
        "origin": {
            "record_count": origin_count,
            "head_record_hash": origin_head,
            "verify_chain": origin_verify,
        },
        "rebuilt": {
            "record_count": rebuilt_count,
            "head_record_hash": rebuilt_head,
            "verify_chain": rebuilt_verify,
        },
        "record_hash_parity": hash_parity,
        "tampered": {
            "verify_chain": tampered_verify,
            "tampered_seq": TAMPER_SEQ,
            "tampered_field": TAMPER_FIELD,
        },
        "rebuild_proof": rebuild_proof,
        "tamper_control": tamper_control,
    }
    capsule_text = json.dumps(capsule, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if dsn in capsule_text:
        print("REFUSAL: DSN would leak into the capsule; aborting write", file=sys.stderr)
        return 1
    CAPSULE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CAPSULE_PATH.write_text(capsule_text, encoding="utf-8")

    # 7. One-line verdict.
    print(
        "WP-04 REBUILD DRILL: "
        f"ok={ok} "
        f"origin_records={origin_count} "
        f"rebuilt_records={rebuilt_count} "
        f"hash_parity={hash_parity} "
        f"verify_origin={origin_verify} "
        f"verify_rebuilt={rebuilt_verify} "
        f"verify_tampered={tampered_verify} "
        f"tamper_control={'PASS' if tamper_control else 'FAIL'} "
        f"head={origin_head} "
        f"-> {CAPSULE_PATH.relative_to(REPO_ROOT)}"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
