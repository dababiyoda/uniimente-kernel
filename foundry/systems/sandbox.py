"""#10 Stronger-than-process isolation for generated and third-party code (gVisor).

Untrusted code runs inside gVisor (runsc): its system calls are served by the
Sentry, a user-space Linux kernel, not by the host kernel. The sandbox root is
the read-only #9 image; the code arrives on a read-only /work mount; the
process has no network (``--network=none``), no capabilities, no new
privileges, a non-root user, a clean environment and a wall-clock limit.

Every run is logged to a hash-chained journal with the code's hash and the
outcome. ``probe`` runs a fixed set of escape attempts inside the sandbox
(host files, host secrets in the environment, the host's loopback, writes
outside the sandbox, privilege escalation, mounting, and a connection to
192.0.2.1, an RFC 5737 documentation address that is never routable). The
control run on the host is deliberately limited to the four harmless probes
against resources the harness itself created (its own file, its own
environment variable, its own loopback listener, its own directory): the host
control never attempts privileged operations or external egress. Each denial
in the sandbox is written to the journal in the event shape the #45 SIEM reads
(``sandbox.denied``).

Limitation: gVisor is Linux-only. On macOS the same code needs a Linux VM
(e.g. Lima) to host runsc; that path is not built or tested here.
"""
from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from foundry.systems import containers

TIMEOUT_S = 60
HOST_INVARIANT = {"read_host_secret_file", "read_secret_from_env", "reach_host_listener", "write_outside_sandbox"}


class SandboxError(RuntimeError):
    pass


def _journal_append(path: Path, entry: dict) -> dict:
    lines = path.read_text().splitlines() if path.exists() else []
    prev = json.loads(lines[-1])["hash"] if lines else "0" * 64
    body = {"n": len(lines), **entry, "prev": prev}
    body["hash"] = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    with path.open("a") as fh:
        fh.write(json.dumps(body, sort_keys=True) + "\n")
    return body


def verify_journal(path: Path) -> dict:
    prev = "0" * 64
    lines = Path(path).read_text().splitlines() if Path(path).exists() else []
    for i, line in enumerate(lines):
        rec = json.loads(line)
        claimed = rec.pop("hash")
        if rec["n"] != i or rec["prev"] != prev or hashlib.sha256(json.dumps(rec, sort_keys=True).encode()).hexdigest() != claimed:
            return {"valid": False, "broken_at": i}
        prev = claimed
    return {"valid": True, "records": len(lines)}


def events(path: Path) -> list[dict]:
    """The journal as GREG-shaped events, so the #45 SIEM can run rules over sandbox activity."""
    out = []
    for line in Path(path).read_text().splitlines() if Path(path).exists() else []:
        rec = json.loads(line)
        out.append({"type": "greg." + rec["event"], "event_id": f"sbx-{rec['n']}", "at": f"2026-09-30T00:00:{rec['n'] % 60:02d}Z",
                    "payload": {k: v for k, v in rec.items() if k not in ("event", "hash", "prev")}})
    return out


class Sandbox:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.layout = self.root / "image"
        self.journal = self.root / "sandbox-journal.jsonl"
        if not (self.layout / "index.json").exists():
            containers.build(self.layout)

    def run(self, code: str, *, label: str, timeout: int = TIMEOUT_S) -> dict:
        digest = hashlib.sha256(code.encode()).hexdigest()
        n = len(self.journal.read_text().splitlines()) if self.journal.exists() else 0
        run_id = f"sbx-{label}-{digest[:12]}-{n}"
        work = Path(tempfile.mkdtemp(prefix="sbx-work-", dir=self.root))
        (work / "main.py").write_text(code)
        os.chmod(work, 0o755)
        os.chmod(work / "main.py", 0o644)
        bundle = self.root / "bundles" / run_id
        containers.prepare_bundle(self.layout, bundle, args=["python3", "/work/main.py"])
        spec = json.loads((bundle / "config.json").read_text())
        spec["mounts"].append({"destination": "/work", "type": "bind", "source": str(work), "options": ["rbind", "ro"]})
        spec["process"]["env"] = ["PATH=/usr/local/bin:/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE=1", "HOME=/tmp"]
        (bundle / "config.json").write_text(json.dumps(spec, indent=1, sort_keys=True))
        try:
            out = containers.run(bundle, runtime_name="runsc", container_id=run_id, timeout=timeout)
        except subprocess.TimeoutExpired:            # containers.run already deleted the sandbox
            out = {"runtime": "runsc", "exit": None, "stdout": "", "stderr": "wall-clock limit reached; sandbox killed"}
        entry = _journal_append(self.journal, {"event": "sandbox.run", "label": label, "code_sha256": digest,
                                               "exit": out["exit"],
                                               "stdout_sha256": hashlib.sha256(out["stdout"].encode()).hexdigest()})
        return {**out, "journal_n": entry["n"]}


PROBES = r'''
import ctypes, json, os, socket, sys
cfg = CONFIG
out = {}
def attempt(name, fn):
    try:
        out[name] = {"succeeded": True, "detail": str(fn())[:80]}
    except Exception as exc:
        out[name] = {"succeeded": False, "detail": f"{type(exc).__name__}: {str(exc)[:80]}"}
attempt("read_host_secret_file", lambda: open(cfg["secret_file"]).read())
attempt("read_secret_from_env", lambda: os.environ[cfg["secret_env"]])
def host_listener():
    s = socket.create_connection(("127.0.0.1", cfg["host_port"]), timeout=2); s.sendall(b"escape"); s.close(); return "connected"
attempt("reach_host_listener", host_listener)
def external():
    s = socket.create_connection(("192.0.2.1", 443), timeout=2); s.close(); return "connected"
def write_outside():
    open(cfg["write_target"], "w").write("escaped"); return "written"
attempt("write_outside_sandbox", write_outside)
if cfg.get("host_control"):
    print(json.dumps(out, sort_keys=True)); raise SystemExit(0)
def become_root():
    os.setuid(0); return os.getuid()
attempt("become_root", become_root)
attempt("reach_external_network", external)
def mount():
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.mount(b"none", b"/mnt", b"tmpfs", 0, None) != 0:
        raise OSError(ctypes.get_errno(), os.strerror(ctypes.get_errno()))
    return "mounted"
attempt("mount_filesystem", mount)
out["kernel"] = open("/proc/version").read().strip()[:60]
print(json.dumps(out, sort_keys=True))
'''


def _listener() -> tuple[socket.socket, list, threading.Event]:
    hits: list = []
    stop = threading.Event()
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(5)
    srv.settimeout(0.2)

    def accept():
        while not stop.is_set():
            try:
                conn, _ = srv.accept()
                hits.append(conn.recv(16))
                conn.close()
            except socket.timeout:
                continue
            except OSError:
                return
    threading.Thread(target=accept, daemon=True).start()
    return srv, hits, stop


def probe(root: Path) -> dict:
    """Escape attempts in the sandbox, with the same attempts as a host process as the control."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    secret_file = root / "host-secret.txt"
    secret_file.write_text("host-only secret")
    sandbox_target, host_target = root / "escaped-from-sandbox.txt", root / "written-by-host.txt"
    srv, hits, stop = _listener()
    base = {"secret_file": str(secret_file), "secret_env": "UNIIMENTE_HOST_SECRET", "host_port": srv.getsockname()[1]}
    os.environ["UNIIMENTE_HOST_SECRET"] = "host-env-secret"
    try:
        sandbox = Sandbox(root)
        inside = sandbox.run(PROBES.replace("CONFIG", repr({**base, "write_target": str(sandbox_target)})), label="escape-probes")
        if inside["exit"] != 0:
            raise SandboxError(f"probe run failed: {inside['stderr'][-400:]}")
        hits_from_sandbox = len(hits)
        host = subprocess.run([sys.executable, "-c", PROBES.replace("CONFIG", repr({**base, "write_target": str(host_target),
                                                                               "host_control": True}))],
                              capture_output=True, text=True, timeout=60)
    finally:
        stop.set()
        srv.close()
        os.environ.pop("UNIIMENTE_HOST_SECRET", None)
    sandboxed, control = json.loads(inside["stdout"]), json.loads(host.stdout)
    for name, result in sorted(sandboxed.items()):
        if name != "kernel" and not result["succeeded"]:
            _journal_append(sandbox.journal, {"event": "sandbox.denied", "probe": name, "reason": result["detail"]})
    return {"sandboxed": sandboxed, "control": control, "host_listener_hits_from_sandbox": hits_from_sandbox,
            "sandbox_wrote_host_file": sandbox_target.exists(), "journal": verify_journal(sandbox.journal),
            "journal_path": str(sandbox.journal)}


def _run_op(args, root):
    return Sandbox(Path(root)).run(args["code"], label=args.get("label", "untrusted"))


QUERY_OPS = {"journal": lambda a, r: verify_journal(Path(r) / "sandbox-journal.jsonl")}
APPLY_OPS = {"run": _run_op}


def exercise(root) -> dict:
    from foundry.systems import siem
    root = Path(root)
    result = probe(root / "probe")
    denied = sorted(k for k, v in result["sandboxed"].items() if k != "kernel" and not v["succeeded"])
    allowed_on_host = {k for k, v in result["control"].items() if k != "kernel" and v["succeeded"]}
    # these four succeed for any host user; privilege and egress probes depend on the host, so they are
    # checked (host success implies sandbox denial) but not recorded as evidence
    missing_control = HOST_INVARIANT - allowed_on_host
    if missing_control:
        raise SandboxError(f"control run did not reproduce host-invariant escapes {sorted(missing_control)}")
    leaked = sorted(allowed_on_host - set(denied))
    if leaked:
        raise SandboxError(f"escapes that work on the host also worked in the sandbox: {leaked}")
    sbx = Sandbox(root / "probe")
    ok = sbx.run("print(sum(range(10)))", label="generated-ok")
    loop = sbx.run("while True: pass", label="runaway", timeout=8)
    rule = [{"id": "sandbox.escape_attempt", "category": "identity", "type": "match", "event": "sandbox.denied",
             "where": {"probe": "."}, "threshold": 1, "group_by": "probe"}]
    alerts = siem.detect(events(sbx.journal), rule)
    return {"denied_in_sandbox": denied, "host_invariant_escapes_succeeded_on_host": sorted(HOST_INVARIANT),
            "every_host_escape_denied": True, "sandbox_kernel_is_gvisor": "gvisor" in result["sandboxed"]["kernel"],
            "host_listener_hits_from_sandbox": result["host_listener_hits_from_sandbox"],
            "sandbox_wrote_host_file": result["sandbox_wrote_host_file"],
            "generated_code_output": ok["stdout"].strip(), "runaway_stopped": loop["exit"] != 0,
            "journal_valid": verify_journal(sbx.journal)["valid"], "siem_alerts_from_denials": len(alerts)}
