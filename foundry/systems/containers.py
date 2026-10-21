"""#9 Containers: capabilities packaged as reproducible OCI images and run by OCI runtimes.

Mechanics are adopted, not rebuilt: the OCI image and runtime specifications,
the registry HTTP API, and two independent runtimes (runc, the reference
runtime, and runsc from gVisor, whose user-space kernel is a different
implementation of Linux). UNIIMENTE owns the parts that make it reproducible
and verifiable:

  pinned inputs   the base image is pinned by manifest digest; every blob is
                  fetched from any of several mirrors and accepted only if its
                  sha256 matches, then kept in the #36 content-addressed store
  deterministic   the capability layer is a normalized tar (fixed mtime, owners,
                  modes, order; gzip without timestamp) of owned source, so two
                  builds produce the same image digest
  layout          an OCI image layout (oci-layout, index.json, blobs/sha256/...)
                  any OCI tool can read
  unpack          layers applied in order with whiteouts; every path is resolved
                  inside the rootfs (the filepath-securejoin pattern containerd and
                  runc use), so absolute symlinks in an image cannot reach the host
  run             a generated runtime spec: read-only rootfs, no network, no
                  capabilities, no-new-privileges, non-root user, pids limit

"Runs identically in a second environment" is checked by running the same
image under runc and under gVisor from independently unpacked root filesystems
and comparing the capability's output.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
import shutil
import subprocess
import tarfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from foundry.systems import cas
from greg import egress

ROOT = Path(__file__).resolve().parents[2]
SOURCE_DATE_EPOCH = 1_788_000_000
CREATED = "2026-09-01T00:00:00Z"
BASE = {"name": "python:3.11-alpine", "platform": "linux/amd64",
        "manifest": "sha256:663669a264dae3d9cddeec4e131a8562b429c29054fa98cbdb3bdb234192284e"}
MIRRORS = [("https://mirror.gcr.io", "library/python"), ("https://public.ecr.aws", "docker/library/python"),
           ("https://registry-1.docker.io", "library/python")]
MANIFEST_TYPES = "application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json"
# Egress of the registry client, exact host names (greg/egress.py semantics: https only, every redirect hop
# re-checked, credentials kept only on their origin). The mirrors serve the registry API; a mirror may
# redirect a blob to the CDN it fronts (observed 2026-10-14: registry-1.docker.io -> production.cloudfront
# .docker.com, public.ecr.aws -> d2glxqk2uabbnd.cloudfront.net; mirror.gcr.io redirects on its own host).
# A redirect anywhere else is refused and the next mirror is tried. Blob bytes are digest-verified anyway;
# what the allowlist protects is where requests, and the pull token, may go.
REGISTRY_HOSTS = tuple(urllib.parse.urlsplit(registry).hostname for registry, _ in MIRRORS)
BLOB_REDIRECT_HOSTS = ("production.cloudfront.docker.com", "d2glxqk2uabbnd.cloudfront.net")
# Token realms a mirror's Bearer challenge may name. The realm arrives in a response header, so it is a
# target like any other: https, an exact member of this list, fetched with no credential.
TOKEN_REALM_HOSTS = ("auth.docker.io", "public.ecr.aws", "mirror.gcr.io")
CACHE = Path(os.environ.get("UNIIMENTE_OCI_CACHE", Path.home() / ".cache" / "uniimente" / "oci"))


class ContainerError(RuntimeError):
    pass


# -- registry client (anonymous pull, bearer-token challenge, digest-verified) ----------

def _bearer(challenge: str) -> str:
    """Anonymous pull token from the challenge's realm, refused unless the realm is an allowlisted https host.

    urllib.request.urlopen used to open whatever realm the response named, following any redirect."""
    fields = dict(part.split("=", 1) for part in challenge.removeprefix("Bearer ").split(","))
    fields = {k.strip(): v.strip().strip('"') for k, v in fields.items()}
    query = "&".join(f"{k}={fields[k]}" for k in ("service", "scope") if k in fields)
    request = urllib.request.Request(f"{fields.get('realm', '')}?{query}")
    with egress.open_checked(request, allowlist=TOKEN_REALM_HOSTS, timeout=60) as r:
        body = json.loads(r.read())
    return body.get("token") or body["access_token"]


def _fetch(url: str, accept: str | None = None) -> bytes:
    """GET through the shared egress opener (greg/egress.py), never urllib's default redirect handler.

    That handler copied ``Authorization`` onto every redirected request, so a registry 3xx handed the pull
    token to any host. Here each hop is re-checked against REGISTRY_HOSTS + BLOB_REDIRECT_HOSTS and the token
    stays on the registry's origin. A refusal raises ``egress.EgressRefused``; fetch_blob moves to the next
    mirror."""
    headers = {"Accept": accept} if accept else {}
    allowlist = REGISTRY_HOSTS + BLOB_REDIRECT_HOSTS
    try:
        with egress.open_checked(urllib.request.Request(url, headers=headers), allowlist=allowlist,
                                 timeout=120) as r:
            return r.read()
    except urllib.error.HTTPError as exc:
        if exc.code != 401 or "Bearer" not in exc.headers.get("WWW-Authenticate", ""):
            raise
        challenge = exc.headers["WWW-Authenticate"]
        exc.close()
    token = _bearer(challenge)
    request = urllib.request.Request(url, headers={**headers, "Authorization": f"Bearer {token}"})
    with egress.open_checked(request, allowlist=allowlist, timeout=120) as r:
        return r.read()


def fetch_blob(digest: str, *, kind: str = "blobs", accept: str | None = None, store: Path = CACHE) -> bytes:
    """Any mirror may serve a blob; only bytes whose sha256 matches the digest are accepted."""
    try:
        return cas.get(store, digest)
    except (FileNotFoundError, KeyError, ValueError, cas.IntegrityError):
        pass
    errors = []
    for registry, repo in MIRRORS:
        try:
            data = _fetch(f"{registry}/v2/{repo}/{kind}/{digest}", accept)
        except Exception as exc:  # unreachable, rate-limited, missing: try the next mirror
            errors.append(f"{registry}: {type(exc).__name__}")
            continue
        if "sha256:" + hashlib.sha256(data).hexdigest() != digest:
            errors.append(f"{registry}: digest mismatch (refused)")
            continue
        if cas.put(store, data) != digest:
            raise ContainerError("content store disagrees with the registry digest")
        return data
    raise ContainerError(f"no mirror served {digest}: {errors}")


def base_image(store: Path = CACHE) -> dict:
    manifest = json.loads(fetch_blob(BASE["manifest"], kind="manifests", accept=MANIFEST_TYPES, store=store))
    config = json.loads(fetch_blob(manifest["config"]["digest"], store=store))
    for layer in manifest["layers"]:
        fetch_blob(layer["digest"], store=store)
    return {"manifest": manifest, "config": config}


# -- deterministic capability layer and image ------------------------------------------

def _tar(files: dict[str, bytes], executable: frozenset = frozenset()) -> bytes:
    raw = io.BytesIO()
    dirs = sorted({str(Path(p).parents[i]) for p in files for i in range(len(Path(p).parents) - 1)})
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for d in dirs:
            info = tarfile.TarInfo(d + "/")
            info.type, info.mode, info.mtime, info.uid, info.gid = tarfile.DIRTYPE, 0o755, SOURCE_DATE_EPOCH, 0, 0
            tar.addfile(info)
        for path in sorted(files):
            data = files[path]
            info = tarfile.TarInfo(path)
            info.size, info.mtime, info.uid, info.gid = len(data), SOURCE_DATE_EPOCH, 0, 0
            info.mode = 0o755 if path in executable else 0o644
            tar.addfile(info, io.BytesIO(data))
    return raw.getvalue()


def _gzip(data: bytes) -> bytes:
    out = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=out, mtime=0, compresslevel=9) as gz:
        gz.write(data)
    return out.getvalue()


def _canon(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


CAPABILITY = '''import json, sys
sys.path.insert(0, "/opt/uniimente")
import dsl
cases = json.loads(sys.argv[1]) if len(sys.argv) > 1 else [
    {"base_price": 100, "units": 3, "customer_tier": 2, "cost_per_unit": 50},
    {"base_price": 80, "units": 10, "customer_tier": 0, "cost_per_unit": 70}]
rule = "max(base_price * units * (1 - 0.05 * customer_tier), cost_per_unit * units * 1.2)"
print(json.dumps({"rule": rule, "quotes": [dsl.run("pricing", rule, c) for c in cases]}, sort_keys=True))
'''


def capability_files() -> dict[str, bytes]:
    return {"opt/uniimente/dsl.py": (ROOT / "foundry" / "systems" / "dsl.py").read_bytes(),
            "opt/uniimente/capability.py": CAPABILITY.encode()}


def build(out: Path, *, store: Path = CACHE, files: dict[str, bytes] | None = None, name: str = "pricing") -> dict:
    """Write an OCI image layout for base + capability layer; the digest depends only on inputs."""
    base = base_image(store)
    files = files or capability_files()
    layer_tar = _tar(files)
    layer = _gzip(layer_tar)
    config = json.loads(json.dumps(base["config"]))
    config["created"] = CREATED
    sources = {p: hashlib.sha256(b).hexdigest() for p, b in sorted(files.items())}
    config["config"] = {**config.get("config", {}), "Entrypoint": ["python3", "/opt/uniimente/capability.py"],
                        "Cmd": [], "WorkingDir": "/opt/uniimente", "User": "65534:65534",
                        "Labels": {"org.opencontainers.image.title": f"uniimente/{name}",
                                   "uniimente.capability.sources": json.dumps(sources, sort_keys=True),
                                   "uniimente.base.manifest": BASE["manifest"]}}
    config["config"]["Env"] = sorted(set(config["config"].get("Env", [])) | {"PYTHONDONTWRITEBYTECODE=1"})
    config["rootfs"]["diff_ids"] = base["config"]["rootfs"]["diff_ids"] + [_digest(layer_tar)]
    config["history"] = base["config"].get("history", []) + [
        {"created": CREATED, "created_by": "uniimente foundry #9: capability layer", "comment": name}]
    config_bytes = _canon(config)
    manifest = {"schemaVersion": 2, "mediaType": "application/vnd.oci.image.manifest.v1+json",
                "config": {"mediaType": "application/vnd.oci.image.config.v1+json", "digest": _digest(config_bytes),
                           "size": len(config_bytes)},
                "layers": [{"mediaType": l["mediaType"], "digest": l["digest"], "size": l["size"]}
                           for l in base["manifest"]["layers"]]
                + [{"mediaType": "application/vnd.oci.image.layer.v1.tar+gzip", "digest": _digest(layer),
                    "size": len(layer)}],
                "annotations": {"org.opencontainers.image.base.digest": BASE["manifest"],
                                "org.opencontainers.image.base.name": BASE["name"]}}
    manifest_bytes = _canon(manifest)
    out = Path(out)
    blobs = out / "blobs" / "sha256"
    blobs.mkdir(parents=True, exist_ok=True)
    for data in [config_bytes, manifest_bytes, layer] + [cas.get(store, l["digest"]) for l in base["manifest"]["layers"]]:
        (blobs / hashlib.sha256(data).hexdigest()).write_bytes(data)
    (out / "oci-layout").write_text(json.dumps({"imageLayoutVersion": "1.0.0"}))
    index = {"schemaVersion": 2, "mediaType": "application/vnd.oci.image.index.v1+json",
             "manifests": [{"mediaType": manifest["mediaType"], "digest": _digest(manifest_bytes),
                            "size": len(manifest_bytes), "annotations": {"org.opencontainers.image.ref.name": name}}]}
    (out / "index.json").write_bytes(_canon(index))
    return {"image": _digest(manifest_bytes), "layers": len(manifest["layers"]), "capability_layer": _digest(layer),
            "base": BASE["manifest"]}


def verify_layout(layout: Path) -> dict:
    """Every blob in the layout hashes to its name, and the manifest reaches only present blobs."""
    layout = Path(layout)
    bad = [p.name for p in (layout / "blobs" / "sha256").iterdir() if hashlib.sha256(p.read_bytes()).hexdigest() != p.name]
    index = json.loads((layout / "index.json").read_text())
    manifest_digest = index["manifests"][0]["digest"]
    manifest = json.loads((layout / "blobs" / "sha256" / manifest_digest.split(":")[1]).read_bytes())
    missing = [d["digest"] for d in [manifest["config"], *manifest["layers"]]
               if not (layout / "blobs" / "sha256" / d["digest"].split(":")[1]).exists()]
    return {"valid": not bad and not missing, "corrupt": bad, "missing": missing, "image": manifest_digest}


# -- unpack and run --------------------------------------------------------------------

def secure_join(root: Path, path: str, *, follow_last: bool = False) -> Path:
    """Resolve ``path`` as if ``root`` were ``/`` (the filepath-securejoin pattern used by
    containerd/runc): symlinks, absolute or relative, are resolved inside ``root``, and no
    result can leave it. The last component is not followed unless ``follow_last``."""
    root = Path(root)
    parts = [p for p in Path("/" + path).parts[1:] if p not in ("", ".")]
    resolved: list[str] = []
    hops = 0
    while parts:
        part = parts.pop(0)
        if part == "..":
            if resolved:
                resolved.pop()
            continue
        candidate = root.joinpath(*resolved, part)
        if candidate.is_symlink() and (parts or follow_last):
            hops += 1
            if hops > 40:
                raise ContainerError(f"too many symlinks resolving {path}")
            target = os.readlink(candidate)
            if target.startswith("/"):
                resolved = []
            parts = [p for p in Path(target).parts if p not in ("", ".", "/")] + parts
            continue
        resolved.append(part)
    return root.joinpath(*resolved)


def _remove(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def _extract(tar: tarfile.TarFile, m: tarfile.TarInfo, rootfs: Path) -> None:
    name = m.name
    while name.startswith("./"):                                 # strip the "./" prefix only: ".profile" stays
        name = name[2:]
    name = name.lstrip("/")
    if not name or any(part == ".." for part in Path(name).parts):
        raise ContainerError(f"layer entry {m.name!r} escapes the root")
    parent = secure_join(rootfs, str(Path(name).parent), follow_last=True)
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / Path(name).name
    if m.isdir():
        if (target.exists() or target.is_symlink()) and not (target.is_dir() and not target.is_symlink()):
            _remove(target)
        target.mkdir(exist_ok=True)
    else:
        if target.exists() or target.is_symlink():
            _remove(target)
        if m.issym():
            os.symlink(m.linkname, target)                       # interpreted inside the container root
        elif m.islnk():
            os.link(secure_join(rootfs, m.linkname), target)
        elif m.isreg():
            with tar.extractfile(m) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
        elif m.isfifo():
            os.mkfifo(target)
        else:
            return                                               # device nodes are never created from images
    if not m.issym():
        os.chmod(target, m.mode & 0o1777)                        # setuid/setgid bits are dropped
        if os.geteuid() == 0:
            os.chown(target, m.uid, m.gid)
        os.utime(target, (m.mtime, m.mtime))


def unpack(layout: Path, rootfs: Path) -> dict:
    layout, rootfs = Path(layout), Path(rootfs)
    check = verify_layout(layout)
    if not check["valid"]:
        raise ContainerError(f"refusing to unpack a corrupt image: {check}")
    manifest = json.loads((layout / "blobs" / "sha256" / check["image"].split(":")[1]).read_bytes())
    rootfs.mkdir(parents=True, exist_ok=False)
    for layer in manifest["layers"]:
        data = (layout / "blobs" / "sha256" / layer["digest"].split(":")[1]).read_bytes()
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            for m in tar.getmembers():
                name = Path(m.name.lstrip("./").lstrip("/"))
                if name.name == ".wh..wh..opq":                 # opaque dir: hide lower layers' contents
                    target = secure_join(rootfs, str(name.parent), follow_last=True)
                    if target.is_dir():
                        for child in list(target.iterdir()):
                            _remove(child)
                elif name.name.startswith(".wh."):              # whiteout: delete the lower entry
                    _remove(secure_join(rootfs, str(name.parent), follow_last=True) / name.name[4:])
                else:
                    _extract(tar, m, rootfs)
    return {"image": check["image"], "rootfs": str(rootfs)}


def runtime_spec(args: list[str], *, env: list[str], user: tuple[int, int] = (65534, 65534), readonly: bool = True,
                 cwd: str = "/") -> dict:
    return {
        "ociVersion": "1.0.2",
        "process": {"terminal": False, "user": {"uid": user[0], "gid": user[1]}, "args": args, "env": env, "cwd": cwd,
                    "capabilities": {"bounding": [], "effective": [], "permitted": [], "ambient": []},
                    "rlimits": [{"type": "RLIMIT_NOFILE", "hard": 1024, "soft": 1024}], "noNewPrivileges": True},
        "root": {"path": "rootfs", "readonly": readonly},
        "hostname": "uniimente-capability",
        "mounts": [
            {"destination": "/proc", "type": "proc", "source": "proc"},
            {"destination": "/dev", "type": "tmpfs", "source": "tmpfs", "options": ["nosuid", "strictatime", "mode=755", "size=65536k"]},
            {"destination": "/dev/pts", "type": "devpts", "source": "devpts",
             "options": ["nosuid", "noexec", "newinstance", "ptmxmode=0666", "mode=0620"]},
            {"destination": "/dev/shm", "type": "tmpfs", "source": "shm", "options": ["nosuid", "noexec", "nodev", "mode=1777", "size=65536k"]},
            {"destination": "/sys", "type": "sysfs", "source": "sysfs", "options": ["nosuid", "noexec", "nodev", "ro"]},
            {"destination": "/tmp", "type": "tmpfs", "source": "tmpfs", "options": ["nosuid", "nodev", "mode=1777", "size=65536k"]},
        ],
        "linux": {"namespaces": [{"type": t} for t in ("pid", "network", "ipc", "uts", "mount")],
                  "resources": {"pids": {"limit": 128}},
                  "maskedPaths": ["/proc/kcore", "/proc/keys", "/proc/timer_list", "/sys/firmware"],
                  "readonlyPaths": ["/proc/bus", "/proc/fs", "/proc/irq", "/proc/sys", "/proc/sysrq-trigger"]},
    }


APPROVAL_ENV = "UNIIMENTE_PRIVILEGED_RUNTIME_HOST"


def privileged_runtime_approved() -> bool:
    """Privileged OCI runtimes run only on a host the founder approved for them, named exactly.

    The founder approves a dedicated, isolated test host (or a CI runner) by setting this variable to that host's
    name in its own environment. Anywhere else, including the development container where running runc/runsc as root
    was refused on 2026-09-30, the run is refused before any command is built. Setting it is the founder's decision,
    never an agent's."""
    import socket as _socket
    approved = os.environ.get(APPROVAL_ENV, "")
    return bool(approved) and approved == _socket.gethostname()


def _privileged(cmd: list[str]) -> list[str]:
    if not privileged_runtime_approved():
        raise ContainerError(f"privileged OCI runtimes are not approved on this host (set {APPROVAL_ENV} to this "
                             "host's name only on a dedicated host the founder approved)")
    if os.geteuid() == 0:
        return cmd
    if shutil.which("sudo"):
        return ["sudo", "-n", "--", *cmd]
    raise ContainerError("OCI runtimes here need root (or passwordless sudo)")


def runtime(name: str) -> str:
    path = os.environ.get(f"UNIIMENTE_{name.upper()}") or shutil.which(name)
    if not path:
        raise ContainerError(f"{name} is not installed (CI installs a pinned gVisor release; see canonical-ci.yml)")
    return path


def _cleanup(runtime_path: str, state: Path, container_id: str) -> None:
    """Delete the container and anything the runtime left mounted in its state directory."""
    subprocess.run(_privileged([runtime_path, "--root", str(state), "delete", "--force", container_id]),
                   capture_output=True, timeout=60)
    if state.exists():
        for leftover in state.rglob("*"):
            if os.path.ismount(leftover):
                subprocess.run(_privileged(["umount", "-l", str(leftover)]), capture_output=True, timeout=30)
        subprocess.run(_privileged(["rm", "-rf", str(state)]), capture_output=True, timeout=60)


def run(bundle: Path, *, runtime_name: str, container_id: str, timeout: int = 120) -> dict:
    if not privileged_runtime_approved():           # refused before any command or state directory exists
        raise ContainerError(f"privileged OCI runtimes are not approved on this host ({APPROVAL_ENV})")
    bundle = Path(bundle)
    state = bundle.parent / f".{runtime_name}-state-{container_id}"
    if runtime_name == "runsc":
        path = runtime("runsc")
        cmd = [path, "--root", str(state), "--network=none", "--platform=systrap", "--ignore-cgroups",
               "run", "--bundle", str(bundle), container_id]
    elif runtime_name == "runc":
        path = runtime("runc")
        cmd = [path, "--root", str(state), "run", "--bundle", str(bundle), container_id]
    else:
        raise ContainerError(f"unknown runtime {runtime_name!r}")
    try:
        proc = subprocess.run(_privileged(cmd), capture_output=True, text=True, timeout=timeout)
    finally:
        _cleanup(path, state, container_id)
    return {"runtime": runtime_name, "exit": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr[-2000:]}


def prepare_bundle(layout: Path, bundle: Path, *, args: list[str] | None = None) -> dict:
    bundle = Path(bundle)
    unpacked = unpack(layout, bundle / "rootfs")
    manifest = json.loads((Path(layout) / "blobs" / "sha256" / unpacked["image"].split(":")[1]).read_bytes())
    config = json.loads((Path(layout) / "blobs" / "sha256" / manifest["config"]["digest"].split(":")[1]).read_bytes())
    c = config["config"]
    user = tuple(int(x) for x in (c.get("User") or "65534:65534").split(":"))
    if len(user) != 2 or 0 in user:
        raise ContainerError("an image that asks to run as root (uid or gid 0) is refused")
    spec = runtime_spec(args or (c["Entrypoint"] + c.get("Cmd", [])), env=c["Env"], user=user,
                        cwd=c.get("WorkingDir") or "/")
    (bundle / "config.json").write_text(json.dumps(spec, indent=1, sort_keys=True))
    return {"image": unpacked["image"], "bundle": str(bundle)}


def _build_op(args, root):
    return build(Path(root) / "layout")


def _run_op(args, root):
    root = Path(root)
    bundle = root / "bundles" / args["container_id"]
    if bundle.exists():
        raise ContainerError(f"bundle {args['container_id']} exists; containers are not reused")
    prepare_bundle(root / "layout", bundle)
    out = run(bundle, runtime_name=args.get("runtime", "runsc"), container_id=args["container_id"])
    return {**out, "stdout_sha256": hashlib.sha256(out["stdout"].encode()).hexdigest()}


QUERY_OPS = {"verify": lambda a, r: verify_layout(Path(r) / "layout")}
APPLY_OPS = {"build": _build_op, "run": _run_op}


def exercise(root) -> dict:
    root = Path(root)
    a = build(root / "image-a")
    b = build(root / "image-b")
    checked = verify_layout(root / "image-a")
    outputs = {}
    for runtime_name, layout in (("runc", root / "image-a"), ("runsc", root / "image-b")):
        prepare_bundle(layout, root / f"bundle-{runtime_name}")
        out = run(root / f"bundle-{runtime_name}", runtime_name=runtime_name, container_id=f"cap-{runtime_name}-{a['image'][7:19]}")
        if out["exit"] != 0:
            raise ContainerError(f"{runtime_name} failed: {out['stderr'][-600:]}")
        outputs[runtime_name] = out["stdout"].strip()
    changed = build(root / "image-c", files={**capability_files(),
                                             "opt/uniimente/capability.py": (CAPABILITY + "#\n").encode()})
    tampered = root / "image-a" / "blobs" / "sha256" / a["capability_layer"].split(":")[1]
    blob = bytearray(tampered.read_bytes())
    blob[len(blob) // 2] ^= 0xFF                      # a real bit flip (a gzip trailer can already end in 0x00)
    tampered.write_bytes(bytes(blob))
    refused = None
    try:
        unpack(root / "image-a", root / "tampered-rootfs")
    except ContainerError as exc:
        refused = str(exc)[:80]
    return {"image": a["image"], "reproducible": a["image"] == b["image"], "layout_valid": checked["valid"],
            "outputs_identical": outputs["runc"] == outputs["runsc"],
            "output_sha256": hashlib.sha256(outputs["runsc"].encode()).hexdigest(),
            "quotes": json.loads(outputs["runsc"])["quotes"], "one_byte_change_new_image": changed["image"] != a["image"],
            "tampered_blob_refused": refused is not None, "base_pinned": a["base"]}
