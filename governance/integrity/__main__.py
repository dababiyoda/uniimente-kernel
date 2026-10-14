"""``python -m governance.integrity`` — the live constitutional-integrity check and
the founder's signing commands.

    python -m governance.integrity --check            exit 0 / 1 / 2
    python -m governance.integrity enroll    --key PEM --label L      (founder, once)
    python -m governance.integrity authorize --artifact P --sha256 D --key PEM --reason R
    python -m governance.integrity keys      --key PEM (--add HEX --label L | --remove KEY_ID) --reason R

Exit codes of ``--check``: 0 every protected artifact is as authorized;
1 at least one finding (each is named, with the founder's exact steps);
2 the record of what is authorized is unsound, so no verdict is given.

The signing commands run on the device that holds the founder key and write
only the record files; the founder commits them. They never run in CI and an
agent has no key to run them with. Keys come from ``python -m greg founder
keygen`` (PKCS8 Ed25519, mode 0600, optionally passphrase-encrypted; the
passphrase is read from GREG_FOUNDER_PASSPHRASE or a hidden prompt).
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import stat
import sys

from . import (AUTHORIZATIONS, AUTHORIZE, FOUNDER_KEYS, KEYS, KERNEL_ROOT, IntegrityRecordError,
               Verdict, authorization_body, authorizations_from, authorized_state,
               founder_keys_from, key_id, key_set_digest, load_founder_keys, load_manifest,
               public_hex_of, sign_envelope, verify)

DEFAULT_KEY = "~/.greg-founder.pem"


def founder_steps(report, *, key: str = DEFAULT_KEY) -> list[str]:
    """The exact steps that make a finding authorized, or reject it. Only Alfonso
    can take them: each needs a signature by an enrolled founder key."""
    findings = report.findings
    if not findings:
        return []
    steps, n = [], 1
    if not report.founder_keys.enrolled:
        steps += [f"{n}. On your own device, create your founder key once (or reuse your GREG founder key):",
                  f"     python -m greg founder keygen --key {key}",
                  f"{n + 1}. Enroll its public key, then commit {FOUNDER_KEYS} yourself (trust on first use;",
                  "   later key changes need a signature by an enrolled key):",
                  f"     python -m governance.integrity enroll --key {key} --label alfonso"]
        n += 2
    for status in findings:
        if status.verdict in (Verdict.UNAUTHORIZED_CHANGE, Verdict.UNGOVERNED_ADDITION):
            steps += [f"{n}. Review {status.artifact} at sha256 {status.observed_sha256}. To authorize exactly",
                      f"   those bytes, sign and then commit {AUTHORIZATIONS}:",
                      f"     python -m governance.integrity authorize --artifact {status.artifact} "
                      f"--sha256 {status.observed_sha256} --key {key} --reason \"<why>\""]
            if status.authorized_sha256:
                steps.append(f"   To reject instead, restore {status.artifact} to the bytes with sha256 "
                             f"{status.authorized_sha256}.")
            else:
                steps.append(f"   To reject instead, remove {status.artifact}.")
        elif status.verdict is Verdict.MISSING:
            steps.append(f"{n}. {status.artifact} is missing: restore the bytes with sha256 "
                         f"{status.authorized_sha256} (removal cannot be authorized in record version 1).")
        n += 1
    steps.append(f"{n}. Re-run: python -m governance.integrity --check   (exit 0 when every finding is resolved)")
    return steps


def _check(args) -> int:
    try:
        report = verify(args.root)
    except IntegrityRecordError as exc:
        if args.json:
            print(json.dumps({"intact": False, "unsound_record": str(exc)}, indent=1))
        else:
            print("LIVE CONSTITUTIONAL INTEGRITY: RECORD UNSOUND, no verdict given")
            print(f"  {exc}")
            print("  The record of what is authorized does not follow from itself. This is not")
            print("  a report that an artifact changed; it means none can be judged either way.")
        return 2
    if args.json:
        print(json.dumps({**report.to_dict(), "founder_steps": founder_steps(report)}, indent=1))
        return 0 if report.intact else 1
    keys = report.founder_keys
    source = report.manifest.source
    print("LIVE CONSTITUTIONAL INTEGRITY (reads the live tree; CONTRADICTION-0002 Option A)")
    print(f"  baseline: {source.get('subject_id', '?')} @ {str(source.get('source_commit', '?'))[:12]}"
          f"  authorizations on record: {report.authorizations}")
    print(f"  founder keys: {', '.join(sorted(keys.keys)) if keys.enrolled else 'none enrolled'}")
    print()
    for status in report.statuses:
        mark = "ok     " if status.ok else "FINDING"
        trail = f"  ({status.authorizations} authorization(s))" if status.authorizations else ""
        print(f"  [{mark}] {status.artifact}{trail}"
              + ("" if status.ok else f"  {status.verdict.value}"))
        if status.note:
            print(f"            {status.note}")
        if not status.ok:
            print(f"            authorized {status.authorized_sha256}")
            print(f"            observed   {status.observed_sha256}")
    print()
    if report.intact:
        print(f"{len(report.statuses)} protected artifacts, all as authorized.")
        return 0
    names = ", ".join(s.artifact for s in report.findings)
    print(f"{len(report.findings)} UNAUTHORIZED: {names}")
    print()
    print("Founder steps (only a signature by an enrolled founder key authorizes; no agent,")
    print("workflow, path, hash or caller string can):")
    for line in founder_steps(report):
        print(f"  {line}")
    return 1


def _passphrase(args) -> bytes | None:
    env = os.environ.get("GREG_FOUNDER_PASSPHRASE")
    if env is not None:
        return env.encode() or None
    if args.no_passphrase:
        return None
    return getpass.getpass("founder key passphrase: ").encode() or None


def _private_key(args):
    """Load a founder key the way greg/founder.py does: owner-only file, Ed25519."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    path = os.path.expanduser(args.key)
    mode = stat.S_IMODE(os.stat(path).st_mode)
    if mode & 0o077:
        raise IntegrityRecordError(f"founder key {path} is readable by others (mode {oct(mode)})")
    with open(path, "rb") as handle:
        key = serialization.load_pem_private_key(handle.read(), password=_passphrase(args))
    if not isinstance(key, Ed25519PrivateKey):
        raise IntegrityRecordError("founder key is not Ed25519")
    return key


def _rewrite(root: str, relative: str, update, validate) -> None:
    """Apply ``update`` to a record file, validate the result, and only then write it."""
    path = os.path.join(root, relative)
    with open(path, encoding="utf-8") as handle:
        record = json.load(handle)
    update(record)
    validate(record)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(record, indent=1, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def _enroll(args) -> int:
    keys = load_founder_keys(args.root)
    if keys.enrolled:
        raise IntegrityRecordError("a founder key is already enrolled; a key change needs a signature "
                                   "by it: python -m governance.integrity keys ...")
    public = args.public_key or public_hex_of(_private_key(args))
    kid = key_id(public)
    _rewrite(args.root, FOUNDER_KEYS,
             lambda r: r["genesis"].append({"public_key": public, "label": args.label}),
             founder_keys_from)
    print(f"enrolled {kid} in {FOUNDER_KEYS} as genesis (trust on first use).")
    print("Compare this key id with the key on your device, then commit the file yourself.")
    return 0


def _authorize(args) -> int:
    key = _private_key(args)
    keys = load_founder_keys(args.root)
    kid = key_id(public_hex_of(key))
    if kid not in keys.keys:
        raise IntegrityRecordError(f"{kid} is not enrolled in {FOUNDER_KEYS}; enroll first")
    body = authorization_body(args.root, args.artifact, args.sha256, args.reason)
    with open(os.path.join(args.root, body["artifact"]), "rb") as handle:
        live = hashlib.sha256(handle.read()).hexdigest()
    if live != body["new_sha256"]:
        raise IntegrityRecordError(f"{args.artifact} is {live} on disk, not {args.sha256}: authorize "
                                   "the bytes you reviewed")
    envelope = sign_envelope(key, AUTHORIZE, body)
    manifest = load_manifest(args.root)
    _rewrite(args.root, AUTHORIZATIONS, lambda r: r["authorizations"].append(envelope),
             lambda r: authorized_state(manifest, keys, authorizations_from(r)))
    print(f"signed {AUTHORIZE} for {args.artifact}: {body['previous_sha256']} -> {body['new_sha256']}")
    print(f"Commit {AUTHORIZATIONS} yourself, then run: python -m governance.integrity --check")
    return 0


def _keys(args) -> int:
    key = _private_key(args)
    keys = load_founder_keys(args.root)
    kid = key_id(public_hex_of(key))
    if kid not in keys.keys:
        raise IntegrityRecordError(f"{kid} is not an enrolled founder key")
    if bool(args.add) == bool(args.remove):
        raise IntegrityRecordError("give exactly one of --add or --remove")
    add = [{"public_key": args.add, "label": args.label}] if args.add else []
    if args.add:
        key_id(args.add)
    body = {"previous_keys_sha256": key_set_digest(keys.keys, keys.labels), "add": add,
            "remove": [args.remove] if args.remove else [], "reason": args.reason}
    envelope = sign_envelope(key, KEYS, body)
    _rewrite(args.root, FOUNDER_KEYS, lambda r: r["changes"].append(envelope), founder_keys_from)
    after = load_founder_keys(args.root)
    print(f"signed {KEYS}; enrolled keys now: {', '.join(sorted(after.keys))}")
    print(f"Commit {FOUNDER_KEYS} yourself.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m governance.integrity",
                                     description="Live constitutional integrity (CONTRADICTION-0002 Option A)")
    parser.add_argument("--check", action="store_true", help="read the live tree (the default action)")
    parser.add_argument("--json", action="store_true", help="machine-readable --check output")
    parser.add_argument("--root", default=KERNEL_ROOT, help=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="cmd")
    signing = argparse.ArgumentParser(add_help=False)
    signing.add_argument("--key", required=True, help="founder private key (PEM) from greg founder keygen")
    signing.add_argument("--no-passphrase", action="store_true")
    enroll = sub.add_parser("enroll", help="founder's initial enrollment (only while no key is enrolled)")
    enroll.add_argument("--key", help="derive the public key from this founder key")
    enroll.add_argument("--public-key", help="64-hex Ed25519 public key, as greg founder keygen prints it")
    enroll.add_argument("--label", required=True)
    enroll.add_argument("--no-passphrase", action="store_true")
    authorize = sub.add_parser("authorize", parents=[signing], help="sign one artifact digest")
    authorize.add_argument("--artifact", required=True)
    authorize.add_argument("--sha256", required=True)
    authorize.add_argument("--reason", required=True)
    keys = sub.add_parser("keys", parents=[signing], help="signed change to the founder key set")
    keys.add_argument("--add", help="public key hex to enroll")
    keys.add_argument("--label", default="founder")
    keys.add_argument("--remove", help="key id to remove")
    keys.add_argument("--reason", required=True)
    args = parser.parse_args(argv)
    args.root = str(args.root)
    try:
        if args.cmd is None:
            return _check(args)
        if args.check:
            parser.error("--check does not combine with a signing command")
        if args.cmd == "enroll":
            if bool(args.key) == bool(args.public_key):
                parser.error("enroll needs exactly one of --key or --public-key")
            return _enroll(args)
        return {"authorize": _authorize, "keys": _keys}[args.cmd](args)
    except (IntegrityRecordError, OSError, ValueError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
