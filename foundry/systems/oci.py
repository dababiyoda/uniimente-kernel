"""#9 Digest-pinned OCI context for an existing owned restricted-rule capability.

The guarded worker packages reviewed bytes; it has no Docker socket or build
authority. A managed host builds and verifies the OCI artifact independently.
Context creation alone is not an image or execution proof.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import re
import tarfile

from foundry.systems.build import ROOT, SOURCE_DATE_EPOCH

BASE = re.compile(r"(?:docker\.io/library/)?python@sha256:[0-9a-f]{64}\Z")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def context(base):
    if not isinstance(base, str) or not BASE.fullmatch(base):
        raise ValueError("official Python base must be pinned by sha256 digest")
    base = "docker.io/library/" + base if base.startswith("python@") else base
    files = {
        "owned/dsl.py": (ROOT / "foundry/systems/dsl.py").read_bytes(),
        "owned/entry.py": (ROOT / "foundry/oci_entry.py").read_bytes(),
        "Dockerfile": (f"FROM {base}\n"
                       "COPY owned/ /owned/\n"
                       "USER 10001:10001\n"
                       'ENTRYPOINT ["python", "-I", "-B", "/owned/entry.py"]\n').encode(),
    }
    manifest = {"version": "greg-oci/1", "capability": "restricted-dsl",
                "base": base, "platform": "linux/amd64", "source_date_epoch": SOURCE_DATE_EPOCH,
                "files": {name: hashlib.sha256(data).hexdigest() for name, data in files.items()},
                "authority_created": False, "image_built": False}
    files["CONTEXT-MANIFEST.json"] = canonical(manifest)
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        for name, data in sorted(files.items()):
            info = tarfile.TarInfo(name)
            info.size, info.mode, info.mtime = len(data), 0o644, SOURCE_DATE_EPOCH
            tar.addfile(info, io.BytesIO(data))
    return output.getvalue(), manifest


def package(args, root):
    if set(args) != {"base"}:
        raise ValueError("only pinned base is accepted")
    body, manifest = context(args["base"])
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    (root / "context.tar").write_bytes(body)
    (root / "context.json").write_bytes(canonical(manifest))
    return {"context_sha256": hashlib.sha256(body).hexdigest(), "manifest": manifest}


def inspect(root):
    try:
        root = Path(root)
        manifest = json.loads((root / "context.json").read_bytes())
        expected, wanted = context(manifest["base"])
        body = (root / "context.tar").read_bytes()
        return {"intact": manifest == wanted and body == expected,
                "context_sha256": hashlib.sha256(body).hexdigest(), "manifest": manifest}
    except (OSError, ValueError, KeyError, TypeError):
        return {"intact": False}


QUERY_OPS = {"inspect": lambda a, r: inspect(r)}
APPLY_OPS = {"package": package}


def exercise(root):
    # A fixture digest exercises packaging only; no image claim follows.
    made = package({"base": "python@sha256:" + "0" * 64}, root)
    return {"context_intact": inspect(root)["intact"], "image_built": False,
            "context_sha256": made["context_sha256"]}
