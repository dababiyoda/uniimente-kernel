"""Build two real OCI artifacts and compare host/container capability behavior.

Only a disposable managed CI host runs Docker. GREG workers never receive its
socket, credentials or provider execution authority. No image is pushed.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from foundry.oci_entry import evaluate
from foundry.systems import oci
from tests.unit.test_greg_oci import package_with_body


def docker(*args, input=None, timeout=300):
    run = subprocess.run(["docker", *args], input=input, capture_output=True,
                         text=True, timeout=timeout, close_fds=True)
    if run.returncode:
        raise RuntimeError(f"docker {args[0]} failed: {run.stderr[-2000:]}")
    return run.stdout.strip()


def pinned(tag):
    docker("pull", "--platform", "linux/amd64", tag)
    addresses = json.loads(docker("image", "inspect", tag, "--format", "{{json .RepoDigests}}"))
    if len(addresses) != 1 or "@sha256:" not in addresses[0]:
        raise RuntimeError("image did not resolve to one immutable digest")
    return addresses[0]


def layout(archive):
    with tarfile.open(archive) as tar:
        files = {m.name: tar.extractfile(m).read() for m in tar if m.isfile()}
    if json.loads(files["oci-layout"]) != {"imageLayoutVersion": "1.0.0"}:
        raise RuntimeError("not an OCI layout")
    index = json.loads(files["index.json"])
    for name, body in files.items():
        if name.startswith("blobs/sha256/") and hashlib.sha256(body).hexdigest() != name.split("/")[-1]:
            raise RuntimeError("OCI content address mismatch")
    if len(index["manifests"]) != 1:
        raise RuntimeError("unexpected OCI index")
    descriptor = index["manifests"][0]
    digest = descriptor["digest"]
    manifest = json.loads(files["blobs/" + digest.replace(":", "/")])
    for part in [manifest["config"], *manifest["layers"]]:
        body = files["blobs/" + part["digest"].replace(":", "/")]
        if len(body) != part["size"]:
            raise RuntimeError("OCI descriptor size mismatch")
    return {"manifest_digest": digest, "config_digest": manifest["config"]["digest"],
            "layers": [p["digest"] for p in manifest["layers"]]}


def main():
    out = Path(sys.argv[1] if len(sys.argv) == 2 else "oci-evidence")
    out.mkdir(parents=True, exist_ok=False)
    # Tags discover commodity inputs only. Both addresses are resolved and
    # pinned BEFORE context generation or building; exact addresses are retained.
    base = pinned("python:3.11-slim-bookworm")
    builder = pinned("moby/buildkit:buildx-stable-1")
    report = {"base": base, "builder": builder, "docker": docker("version", "--format", "{{json .}}"),
              "buildx": docker("buildx", "version"), "source_date_epoch": oci.SOURCE_DATE_EPOCH,
              "authority_created": False, "pushed": False}
    docker("buildx", "create", "--name", "greg-oci-proof", "--driver", "docker-container",
           "--driver-opt", "image=" + builder, "--use")
    try:
        docker("buildx", "inspect", "--bootstrap")
        with tempfile.TemporaryDirectory() as temporary:
            scratch = Path(temporary)
            home = scratch / "body"; home.mkdir()
            package = package_with_body(home, base)
            report["context"] = oci.inspect(package)
            if not report["context"]["intact"]:
                raise RuntimeError("Body context integrity failed")
            (out / "context.tar").write_bytes((package / "context.tar").read_bytes())
            context = scratch / "context"; context.mkdir()
            with tarfile.open(package / "context.tar") as tar:
                tar.extractall(context, filter="data")
            shared = ["buildx", "build", "--builder", "greg-oci-proof", "--platform", "linux/amd64",
                      "--network", "none", "--provenance=false", "--build-arg",
                      "SOURCE_DATE_EPOCH=" + str(oci.SOURCE_DATE_EPOCH), "--tag", "greg-restricted:verified"]
            layouts = []
            for name in ("first", "second"):
                archive = (out / (name + ".oci.tar")).resolve()
                docker(*shared, "--no-cache", "--output", "type=oci,dest=" + str(archive), str(context))
                layouts.append(layout(archive))
            if layouts[0] != layouts[1]:
                raise RuntimeError("OCI independent rebuild differs")
            report["rebuilds"] = layouts
            docker(*shared, "--load", str(context))
            image = docker("image", "inspect", "greg-restricted:verified", "--format", "{{.Id}}")
            if image != layouts[0]["config_digest"]:
                raise RuntimeError("loaded image differs from retained OCI config")
            cases = [
                {"language": "pricing", "source": "max(base_price*units, cost_per_unit*units*1.2)",
                 "inputs": {"base_price": 7, "units": 4, "cost_per_unit": 3}},
                {"language": "budget", "source": "min(requested, remaining-reserve)",
                 "inputs": {"requested": 90, "remaining": 80, "reserve": 10}},
                {"language": "capital", "source": "max(0,surplus-obligations-surplus*reserve_pct)",
                 "inputs": {"surplus": 100, "obligations": 20, "reserve_pct": 0.1}},
                {"language": "pricing", "source": "__import__('os').system('id')", "inputs": {}},
                {"language": "budget", "source": "requested*2", "inputs": {"requested": 60, "remaining": 90}},
                {"language": "pricing", "source": "base_price.real", "inputs": {"base_price": 5}},
            ]
            observed = []
            for request in cases:
                try:
                    expected = evaluate(request, ROOT / "foundry/systems/dsl.py")
                except ValueError as exc:
                    expected = {"error": str(exc)[:200]}
                result = json.loads(docker("run", "--rm", "-i", "--pull=never", "--network=none",
                                          "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges",
                                          "--user=10001:10001", "--memory=128m", "--memory-swap=128m",
                                          "--cpus=1", "--pids-limit=64", image,
                                          input=json.dumps(request), timeout=20))
                if result != expected:
                    raise RuntimeError(f"container result differs: {result!r} != {expected!r}")
                observed.append({"request": request, "host": expected, "container": result})
            report.update(image=image, cases=observed, reproduced=True, identical_second_environment=True)
    finally:
        docker("buildx", "rm", "greg-oci-proof")
        (out / "report.json").write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"reproduced": True, "image": report["image"], "cases": len(report["cases"])}))


if __name__ == "__main__":
    main()
