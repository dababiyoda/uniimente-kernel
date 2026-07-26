#!/usr/bin/env python3
"""Required check 2 — every document-local JSON Schema reference resolves.

Package 1 baseline implementation. Deliberately standalone: PR #45 carries a
fuller version (tests/unit/test_contract_schema_refs.py) which supersedes this
file when #45 is integrated at step 10. This exists so the baseline CI has the
check on day one without pre-merging #45.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"


def local_refs(node, path="$"):
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/"):
            yield ref, path
        for key, value in node.items():
            yield from local_refs(value, f"{path}.{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from local_refs(value, f"{path}[{i}]")


def resolve(document, ref):
    current = document
    for raw in ref.removeprefix("#/").split("/"):
        segment = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            current = current[int(segment)]
        elif isinstance(current, dict) and segment in current:
            current = current[segment]
        else:
            return False
    return True


def main():
    failures = []
    checked = 0
    for schema_path in sorted(CONTRACTS.rglob("*.json")):
        try:
            document = json.loads(schema_path.read_text())
        except json.JSONDecodeError as exc:
            failures.append(f"{schema_path.relative_to(ROOT)}: invalid JSON: {exc}")
            continue
        for ref, where in local_refs(document):
            checked += 1
            if not resolve(document, ref):
                failures.append(
                    f"{schema_path.relative_to(ROOT)}: unresolvable {ref} at {where}"
                )
        # A $defs block nested under properties is silently declared a legal
        # instance field whenever additionalProperties is false.
        if "$defs" in document.get("properties", {}):
            failures.append(
                f"{schema_path.relative_to(ROOT)}: $defs nested under properties "
                f"— declares '$defs' a legal instance property"
            )

    print(f"schemas scanned: {len(list(CONTRACTS.rglob('*.json')))}, local refs checked: {checked}")
    for failure in failures:
        print(f"FAIL {failure}")
    if failures:
        print(f"\n{len(failures)} schema reference failure(s)")
        return 1
    print("all document-local schema references resolve")
    return 0


if __name__ == "__main__":
    sys.exit(main())
