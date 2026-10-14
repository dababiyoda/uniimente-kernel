"""The live constitutional tripwire (CONTRADICTION-0002 Option A), attacked.

A tripwire that only says "ok" on a clean tree proves almost nothing, so most of
this file is attacks on a throwaway tree: silent edits, deletions, undeclared
additions, forged or replayed authorizations, path and caller-string
"authorizations", key-log tampering. Keys are generated per test in temporary
directories; none is committed. The founder steps the check prints are run end
to end with a throwaway key.
"""
from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from governance import integrity
from governance.integrity import (AUTHORIZATIONS, AUTHORIZE, FOUNDER_KEYS, KEYS, MANIFEST,
                                  IntegrityRecordError, Verdict, key_set_digest, sign_envelope, verify)
from governance.integrity.__main__ import main

ROOT = Path(__file__).resolve().parents[2]
SR002_WITNESS = "d7c235ae5f34e9370f44ca8567b13bcb0444e3f9"
GATE = "policy/consequence_gate.py"
MANIFEST_RAW = json.loads((ROOT / MANIFEST).read_text())
PROTECTED = [entry["path"] for entry in MANIFEST_RAW["artifacts"] if "baseline_sha256" in entry]


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _git_show(commit: str, path: str) -> bytes:
    return subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=ROOT)


@pytest.fixture()
def tree(tmp_path):
    """The twelve artifacts as SR-002 ratified them, plus fresh, empty records."""
    for rel in PROTECTED:
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(_git_show(SR002_WITNESS, rel))
    records = tmp_path / "governance" / "integrity"
    records.mkdir(parents=True)
    (tmp_path / MANIFEST).write_bytes((ROOT / MANIFEST).read_bytes())
    (tmp_path / FOUNDER_KEYS).write_text(json.dumps({"version": 1, "genesis": [], "changes": []}))
    (tmp_path / AUTHORIZATIONS).write_text(json.dumps({"version": 1, "authorizations": []}))
    return tmp_path


def _key(tmp_path, name="founder"):
    from greg.founder import generate_founder_key, load_founder_key
    path = tmp_path.parent / f"{tmp_path.name}-{name}.pem"
    public = generate_founder_key(path, None)
    return path, public, load_founder_key(path, None)


def _edit(tree, rel=GATE, extra=b"\n# changed after ratification\n"):
    target = tree / rel
    target.write_bytes(target.read_bytes() + extra)
    return _sha(target.read_bytes())


def _record(tree, rel, update):
    data = json.loads((tree / rel).read_text())
    update(data)
    (tree / rel).write_text(json.dumps(data))


def _enroll(tree, public, label="founder"):
    _record(tree, FOUNDER_KEYS, lambda r: r["genesis"].append({"public_key": public, "label": label}))


def _authorize(tree, key, artifact, previous, new, reason="reviewed", **kw):
    envelope = sign_envelope(key, AUTHORIZE, {"artifact": artifact, "previous_sha256": previous,
                                              "new_sha256": new, "reason": reason}, **kw)
    _record(tree, AUTHORIZATIONS, lambda r: r["authorizations"].append(envelope))
    return envelope


def _cli(tree, *args):
    return main(["--root", str(tree), *args])


# -- the baseline and the separation ------------------------------------------

def test_the_baseline_is_the_sr002_founder_ratified_digests():
    from evolution.repair.subjects import SR002
    baseline = {e["path"]: e["baseline_sha256"] for e in MANIFEST_RAW["artifacts"] if "baseline_sha256" in e}
    assert baseline == dict(SR002.artifacts)
    for rel, digest in baseline.items():
        assert _sha(_git_show(SR002_WITNESS, rel)) == digest, rel
    assert MANIFEST_RAW["baseline_source"]["source_commit"] == SR002.source_commit
    assert integrity.load_manifest(ROOT).protected == tuple(sorted(baseline)) + (FOUNDER_KEYS,)


def test_the_committed_records_are_sound():
    manifest = integrity.load_manifest(ROOT)
    keys = integrity.load_founder_keys(ROOT)
    integrity.authorized_state(manifest, keys, integrity.load_authorizations(ROOT))
    report = verify(ROOT)
    assert {s.artifact for s in report.statuses} >= set(manifest.protected)


def test_the_check_runs_none_of_the_code_it_judges():
    """The check must not import the Gate, the policy engine, GREG or the sealed
    experiment: a changed module could otherwise vouch for itself."""
    child = ("import io, json, sys, contextlib\n"
             "from governance.integrity.__main__ import main\n"
             "with contextlib.redirect_stdout(io.StringIO()):\n"
             "    main(['--check', '--json'])\n"
             "print(json.dumps(sorted(sys.modules)))\n")
    proc = subprocess.run([sys.executable, "-c", child], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    loaded = {m.split(".")[0] for m in json.loads(proc.stdout)}
    repo_packages = {p.name for p in ROOT.iterdir() if (p / "__init__.py").exists()}
    assert loaded & repo_packages == {"governance"}


def _imports(path: Path) -> set[str]:
    names = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


def test_the_live_check_and_the_sealed_experiment_stay_separate():
    for path in (ROOT / "governance").rglob("*.py"):
        assert not _imports(path) & {"evolution", "greg", "egregore", "policy", "compiler"}, path
    for path in (ROOT / "evolution").rglob("*.py"):
        assert "governance" not in _imports(path), path


def test_the_scheme_is_greg_founders_and_signatures_are_domain_separated(tmp_path):
    from egregore.contracts import canonical_json
    from greg.founder import FounderAuthError, FounderVerifier, key_id, sign_command
    for value in ({"b": [1, 2, {"z": None}], "a": "ünï", "c": True}, [], {"n": 10**20}):
        assert integrity.canonical_json(value) == canonical_json(value)
    _, public, key = _key(tmp_path)
    assert integrity.key_id(public) == key_id(public)
    assert integrity.public_hex_of(key) == public
    keys = {key_id(public): public}
    command = sign_command(key, "DECISION", {"artifact": GATE}, body_id="kernel")
    with pytest.raises(IntegrityRecordError):
        integrity.verify_envelope(command, keys, AUTHORIZE)
    record = sign_envelope(key, AUTHORIZE, {"artifact": GATE})
    verifier = FounderVerifier(body_id="kernel", enrolled=keys, seen_nonce=lambda n: False)
    with pytest.raises(FounderAuthError):
        verifier.verify(record)
    unsigned = integrity.canonical_json({k: v for k, v in record.items() if k != "signature"})
    greg_domain = key.sign(("uniimente-greg-founder-command-v1\n" + unsigned).encode()).hex()
    with pytest.raises(IntegrityRecordError, match="does not verify"):
        integrity.verify_envelope({**record, "signature": greg_domain}, keys, AUTHORIZE)


def test_ci_runs_the_live_check_in_the_one_source_of_authority_job():
    workflow = (ROOT / ".github/workflows/canonical-ci.yml").read_text()
    job = workflow.split("  authority:\n", 1)[1].split("\n  sealed:\n", 1)[0]
    assert "python -m governance.integrity --check" in job
    assert "check_authority_singleton.py" in job


# -- a clean tree, and silent changes -----------------------------------------

def test_the_ratified_tree_is_intact(tree):
    report = verify(tree)
    assert report.intact, report.findings
    assert len(report.statuses) == 13
    assert not report.founder_keys.enrolled
    assert _cli(tree, "--check") == 0


@pytest.mark.parametrize("rel", PROTECTED)
def test_a_silent_edit_to_any_protected_artifact_is_caught(tree, rel, capsys):
    observed = _edit(tree, rel)
    finding, = verify(tree).findings
    assert (finding.artifact, finding.verdict, finding.observed_sha256) == \
        (rel, Verdict.UNAUTHORIZED_CHANGE, observed)
    assert _cli(tree, "--check") == 1
    out = capsys.readouterr().out
    assert f"1 UNAUTHORIZED: {rel}" in out
    assert f"authorize --artifact {rel} --sha256 {observed}" in out
    assert "python -m greg founder keygen" in out and "governance.integrity enroll" in out


def test_a_missing_artifact_is_caught(tree):
    (tree / "authority/reserved-matters.yaml").unlink()
    finding, = verify(tree).findings
    assert finding.verdict is Verdict.MISSING


@pytest.mark.parametrize("rel", ["constitution/second.ucl", "authority/shadow-matrix.yaml",
                                 "identity/extra-registry.yaml"])
def test_an_ungoverned_addition_is_caught(tree, rel):
    (tree / rel).write_text("rogue: true\n")
    finding, = verify(tree).findings
    assert (finding.artifact, finding.verdict) == (rel, Verdict.UNGOVERNED_ADDITION)


# -- the founder steps, end to end --------------------------------------------

def test_the_founder_steps_authorize_exactly_the_reviewed_bytes(tree, tmp_path, capsys):
    pem, public, _ = _key(tmp_path)
    previous = _sha((tree / GATE).read_bytes())
    observed = _edit(tree)
    assert _cli(tree, "--check") == 1
    assert _cli(tree, "authorize", "--artifact", GATE, "--sha256", observed, "--key", str(pem),
                "--no-passphrase", "--reason", "x") == 2, "nothing is authorized before enrollment"
    assert _cli(tree, "enroll", "--key", str(pem), "--label", "founder", "--no-passphrase") == 0
    _, other, _ = _key(tmp_path, "other")
    assert _cli(tree, "enroll", "--public-key", other, "--label", "again") == 2, \
        "a second genesis enrollment is refused"
    assert "already enrolled" in capsys.readouterr().err
    assert _cli(tree, "authorize", "--artifact", GATE, "--sha256", "0" * 64, "--key", str(pem),
                "--no-passphrase", "--reason", "x") == 2, "only the bytes on disk can be authorized"
    stranger_pem, _, _ = _key(tmp_path, "stranger-cli")
    assert _cli(tree, "authorize", "--artifact", GATE, "--sha256", observed, "--key", str(stranger_pem),
                "--no-passphrase", "--reason", "x") == 2
    assert "is not enrolled" in capsys.readouterr().err
    capsys.readouterr()
    assert _cli(tree, "authorize", "--artifact", GATE, "--sha256", observed, "--key", str(pem),
                "--no-passphrase", "--reason", "reviewed hardening") == 0
    assert _cli(tree, "--check") == 0
    report = json.loads(_json(tree, capsys))
    gate, = [s for s in report["statuses"] if s["artifact"] == GATE]
    assert (gate["authorized_sha256"], gate["authorizations"]) == (observed, 1)
    body = json.loads((tree / AUTHORIZATIONS).read_text())["authorizations"][0]["body"]
    assert body == {"artifact": GATE, "previous_sha256": previous, "new_sha256": observed,
                    "reason": "reviewed hardening"}
    # A later change to the same artifact is caught again: one signature
    # authorizes one digest, not the artifact.
    _edit(tree)
    assert verify(tree).findings[0].verdict is Verdict.UNAUTHORIZED_CHANGE


def _json(tree, capsys):
    capsys.readouterr()
    main(["--root", str(tree), "--check", "--json"])
    return capsys.readouterr().out


def test_an_ungoverned_addition_can_be_authorized_by_the_founder(tree, tmp_path):
    _, public, key = _key(tmp_path)
    _enroll(tree, public)
    (tree / "constitution/new-article.ucl").write_text("article {}\n")
    digest = _sha((tree / "constitution/new-article.ucl").read_bytes())
    _authorize(tree, key, "constitution/new-article.ucl", None, digest)
    assert verify(tree).intact


# -- nothing but a founder signature authorizes --------------------------------

def test_a_path_or_caller_string_never_authorizes(tree, tmp_path):
    """#87's record shape named a ruling document by path; REPOSITORY_RATIONALIZATION_PLAN
    forbids amendment by caller string. Neither shape is accepted."""
    observed = _edit(tree)
    previous = MANIFEST_RAW["artifacts"][-2]["baseline_sha256"]
    for forged in (
        {"artifact": GATE, "from_sha256": previous, "to_sha256": observed,
         "authorization": "docs/deliberations/FOUNDER-RULING-2026-08-23-infinite-goal-chase.md",
         "date": "2026-08-23", "reason": "cited as an authorised amendment"},
        {"version": 1, "kind": AUTHORIZE, "scope": integrity.SCOPE, "founder_key_id": "Alfonso Lopez",
         "issued_at": "2026-10-14T00:00:00Z", "nonce": "a" * 32,
         "body": {"artifact": GATE, "previous_sha256": previous, "new_sha256": observed, "reason": "x"},
         "signature": "0" * 128},
    ):
        (tree / AUTHORIZATIONS).write_text(json.dumps({"version": 1, "authorizations": [forged]}))
        with pytest.raises(IntegrityRecordError):
            verify(tree)
        assert _cli(tree, "--check") == 2


def test_a_signature_by_an_unenrolled_key_is_refused(tree, tmp_path):
    _, public, _ = _key(tmp_path, "founder")
    _, _, stranger = _key(tmp_path, "stranger")
    _enroll(tree, public)
    observed = _edit(tree)
    _authorize(tree, stranger, GATE, _sha(_git_show(SR002_WITNESS, GATE)), observed)
    with pytest.raises(IntegrityRecordError, match="not an enrolled founder key"):
        verify(tree)


@pytest.mark.parametrize("tamper", ["body", "scope", "kind", "nonce", "issued_at", "extra"])
def test_an_altered_signed_record_is_refused(tree, tmp_path, tamper):
    _, public, key = _key(tmp_path)
    _enroll(tree, public)
    observed = _edit(tree)
    envelope = _authorize(tree, key, GATE, _sha(_git_show(SR002_WITNESS, GATE)), observed)
    altered = dict(envelope)
    if tamper == "body":
        altered["body"] = {**envelope["body"], "artifact": "constitution/constitution.ucl"}
    elif tamper == "scope":
        altered["scope"] = "another/repository"
    elif tamper == "kind":
        altered["kind"] = KEYS
    elif tamper == "nonce":
        altered["nonce"] = "b" * 32
    elif tamper == "issued_at":
        altered["issued_at"] = "2030-01-01T00:00:00Z"
    else:
        altered["approved_by"] = "Alfonso Lopez"
    (tree / AUTHORIZATIONS).write_text(json.dumps({"version": 1, "authorizations": [altered]}))
    with pytest.raises(IntegrityRecordError):
        verify(tree)


def _signed_as_is(key, envelope):
    """Sign an arbitrary envelope exactly as given, so only the field under test differs."""
    envelope = {k: v for k, v in envelope.items() if k != "signature"}
    envelope["founder_key_id"] = integrity.key_id(integrity.public_hex_of(key))
    envelope["signature"] = key.sign(integrity.signing_bytes(envelope)).hex()
    return envelope


@pytest.mark.parametrize("variant", ["scope", "kind", "extra", "nonce"])
def test_a_validly_signed_record_of_the_wrong_shape_is_refused(tree, tmp_path, variant):
    """Signed by the enrolled key, yet for another repository, another record
    kind, with an extra field, or with a short nonce: none of them authorizes."""
    _, public, key = _key(tmp_path)
    _enroll(tree, public)
    observed = _edit(tree)
    good = sign_envelope(key, AUTHORIZE, {"artifact": GATE, "previous_sha256": _sha(_git_show(SR002_WITNESS, GATE)),
                                          "new_sha256": observed, "reason": "x"})
    shape = {"scope": {"scope": "dababiyoda/DALEOBANKS/governance/integrity"}, "kind": {"kind": KEYS},
             "extra": {"approved_by": "Alfonso Lopez"}, "nonce": {"nonce": "ab" * 4}}[variant]
    forged = _signed_as_is(key, {**good, **shape})
    (tree / AUTHORIZATIONS).write_text(json.dumps({"version": 1, "authorizations": [forged]}))
    with pytest.raises(IntegrityRecordError):
        verify(tree)
    (tree / AUTHORIZATIONS).write_text(json.dumps({"version": 1, "authorizations": [good]}))
    assert verify(tree).intact


def test_an_old_authorization_cannot_be_replayed_after_a_revert(tree, tmp_path):
    """base -> X, then X -> base, then the first record again: the chain is
    consistent, so only the nonce stops the replay."""
    _, public, key = _key(tmp_path)
    _enroll(tree, public)
    baseline = _sha(_git_show(SR002_WITNESS, GATE))
    changed = _edit(tree)
    one = _authorize(tree, key, GATE, baseline, changed)
    _authorize(tree, key, GATE, changed, baseline)
    _record(tree, AUTHORIZATIONS, lambda r: r["authorizations"].append(one))
    with pytest.raises(IntegrityRecordError, match="nonce reused"):
        verify(tree)


def test_an_authorization_must_follow_from_the_chain_and_cannot_be_replayed(tree, tmp_path):
    _, public, key = _key(tmp_path)
    _enroll(tree, public)
    baseline = _sha(_git_show(SR002_WITNESS, GATE))
    first = _edit(tree)
    second = _edit(tree)
    one = _authorize(tree, key, GATE, baseline, first)
    two = _authorize(tree, key, GATE, first, second)
    assert verify(tree).intact
    for chain in ([two, one], [one, two, one], [one, {**two, "body": {**two["body"]}}, two]):
        (tree / AUTHORIZATIONS).write_text(json.dumps({"version": 1, "authorizations": chain}))
        with pytest.raises(IntegrityRecordError):
            verify(tree)
    (tree / AUTHORIZATIONS).write_text(json.dumps({"version": 1, "authorizations": []}))
    _authorize(tree, key, GATE, "1" * 64, second)
    with pytest.raises(IntegrityRecordError, match="starts from"):
        verify(tree)


def test_authorizing_other_bytes_does_not_cover_the_live_file(tree, tmp_path):
    _, public, key = _key(tmp_path)
    _enroll(tree, public)
    observed = _edit(tree)
    _authorize(tree, key, GATE, _sha(_git_show(SR002_WITNESS, GATE)), "2" * 64)
    finding, = verify(tree).findings
    assert (finding.authorized_sha256, finding.observed_sha256) == ("2" * 64, observed)


def test_the_record_files_are_not_moved_by_authorization(tree, tmp_path):
    _, public, key = _key(tmp_path)
    _enroll(tree, public)
    for rel in (MANIFEST, FOUNDER_KEYS, AUTHORIZATIONS):
        (tree / AUTHORIZATIONS).write_text(json.dumps({"version": 1, "authorizations": []}))
        _authorize(tree, key, rel, None, "3" * 64)
        with pytest.raises(IntegrityRecordError, match="not moved by authorization"):
            verify(tree)


# -- the founder-key log --------------------------------------------------------

def _key_change(tree, signer, *, add=(), remove=(), reason="rotation"):
    keys = integrity.load_founder_keys(tree)
    body = {"previous_keys_sha256": key_set_digest(keys.keys, keys.labels),
            "add": [{"public_key": p, "label": "k"} for p in add], "remove": list(remove), "reason": reason}
    envelope = sign_envelope(signer, KEYS, body)
    _record(tree, FOUNDER_KEYS, lambda r: r["changes"].append(envelope))
    return envelope


def test_a_signed_key_change_by_an_enrolled_key_is_accepted(tree, tmp_path):
    _, public_a, key_a = _key(tmp_path, "a")
    pem_b, public_b, key_b = _key(tmp_path, "b")
    _enroll(tree, public_a)
    _key_change(tree, key_a, add=[public_b])
    observed = _edit(tree)
    _authorize(tree, key_b, GATE, _sha(_git_show(SR002_WITNESS, GATE)), observed)
    assert verify(tree).intact
    assert _cli(tree, "keys", "--key", str(pem_b), "--no-passphrase", "--remove",
                integrity.key_id(public_a), "--reason", "retire a") == 0
    assert verify(tree).intact
    assert list(integrity.load_founder_keys(tree).keys) == [integrity.key_id(public_b)]


def test_the_key_log_refuses_unsigned_or_out_of_order_changes(tree, tmp_path):
    _, public_a, key_a = _key(tmp_path, "a")
    _, public_b, key_b = _key(tmp_path, "b")
    _, public_x, key_x = _key(tmp_path, "x")
    _enroll(tree, public_a)
    _key_change(tree, key_a, add=[public_b])
    clean = (tree / FOUNDER_KEYS).read_text()

    def unsound(mutate):
        (tree / FOUNDER_KEYS).write_text(clean)
        _record(tree, FOUNDER_KEYS, mutate)
        with pytest.raises(IntegrityRecordError):
            verify(tree)

    # Replacing or extending the founder's genesis after a signed change.
    unsound(lambda r: r.__setitem__("genesis", [{"public_key": public_x, "label": "x"}]))
    unsound(lambda r: r["genesis"].append({"public_key": public_x, "label": "x"}))
    # A key added without a signature, or by a key that is not enrolled.
    unsound(lambda r: r["changes"].append({"add": [{"public_key": public_x, "label": "x"}]}))
    (tree / FOUNDER_KEYS).write_text(clean)
    _key_change(tree, key_x, add=[public_x])
    with pytest.raises(IntegrityRecordError, match="not an enrolled founder key"):
        verify(tree)
    # Removing every key would reopen enrollment; refused.
    (tree / FOUNDER_KEYS).write_text(clean)
    keys = integrity.load_founder_keys(tree)
    envelope = sign_envelope(key_a, KEYS, {"previous_keys_sha256": key_set_digest(keys.keys, keys.labels),
                                           "add": [], "remove": sorted(keys.keys), "reason": "empty"})
    _record(tree, FOUNDER_KEYS, lambda r: r["changes"].append(envelope))
    with pytest.raises(IntegrityRecordError, match="no founder key"):
        verify(tree)


def test_an_authorization_by_a_removed_key_stops_counting(tree, tmp_path):
    """Revocation is conservative: after a key is removed its signatures no
    longer authorize anything, so the founder re-signs with the current key."""
    _, public_a, key_a = _key(tmp_path, "a")
    _, public_b, key_b = _key(tmp_path, "b")
    _enroll(tree, public_a)
    observed = _edit(tree)
    _authorize(tree, key_a, GATE, _sha(_git_show(SR002_WITNESS, GATE)), observed)
    _key_change(tree, key_a, add=[public_b], remove=[integrity.key_id(public_a)])
    with pytest.raises(IntegrityRecordError, match="not an enrolled founder key"):
        verify(tree)


# -- unsound records give no verdict -------------------------------------------

@pytest.mark.parametrize("rel, content", [
    (MANIFEST, "{not json"),
    (MANIFEST, json.dumps({"version": 1, "artifacts": []})),
    (AUTHORIZATIONS, json.dumps({"version": 1, "authorizations": [], "approved": True})),
    (FOUNDER_KEYS, '{"version": 1, "genesis": [], "changes": [], "trusted": true}'),
    (FOUNDER_KEYS, '{"version": 1, "genesis": [], "changes": [], "purpose": NaN}'),
    (MANIFEST, json.dumps({**MANIFEST_RAW, "authorized_by": "Alfonso Lopez"})),
    (FOUNDER_KEYS, json.dumps({"version": 1, "genesis": [{"public_key": "zz", "label": "x"}], "changes": []})),
])
def test_an_unsound_record_gives_no_verdict(tree, rel, content):
    (tree / rel).write_text(content)
    with pytest.raises(IntegrityRecordError):
        verify(tree)
    assert _cli(tree, "--check") == 2


def test_removing_the_gate_from_the_manifest_is_caught_by_the_baseline_test(tree):
    """The manifest is a trust root the check cannot authenticate; the baseline
    test ties it to git history, and dropping an artifact is visible here."""
    _record(tree, MANIFEST, lambda r: r.__setitem__(
        "artifacts", [a for a in r["artifacts"] if a.get("path") != GATE]))
    assert GATE not in integrity.load_manifest(tree).protected
    assert GATE in integrity.load_manifest(ROOT).protected


# -- the two readings answer different questions -------------------------------

def test_the_historical_and_live_readings_may_disagree(tree):
    from evolution.repair.subjects import SR002
    _edit(tree)
    assert SR002.matches()                     # history still reproduces
    assert not verify(tree).intact             # the live tree is not authorized
    assert not SR002.matches(tree)
