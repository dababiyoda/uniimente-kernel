"""Capability broker: every tool, API, plugin and computer-use route GREG can use.

A capability is data plus one adapter function. Its manifest declares what it
does, what it can touch and how it fails; the embedded kernel CapabilityGenome is
validated by the canonical GenomeRegistry, so there is one capability-validation
owner. The broker never grants authority: invocation happens only through
``greg.authority.AuthorityOffice`` and the Kernel ConsequenceGate.

Lifecycle (building != installation != activation != authority):

    DISCOVERED -> VERIFIED -> ATTACHED  (usable inside a mission light cone)
                         \\-> QUARANTINED / DETACHED (retained, never deleted)

Computer-use route preference (structured before visual):
    api -> app_integration -> cli -> browser -> os_automation -> visual
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
import glob
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request

from capabilities.genome import AuthorityEnvelope, CapabilityGenome, GenomeRegistry, CONSEQUENCE_CLASSES

ROUTES = ("api", "app_integration", "cli", "browser", "os_automation", "visual", "internal")
# Spider-Web Compounding Rule (INTENT-2026-09-25-SPIDER-WEB-COMPOUNDING): every
# capability must strengthen at least one control point of the founder-intent ->
# verified-outcome transaction. The seven nodes are the rule's seven items.
SUPER_NODES = ("eligibility", "routing", "proof", "settlement", "reliability", "capability_formation",
               "compounding")
# evolution/spider_web.py judges strategies against four of them under older names;
# this is the one translation between the two vocabularies (tested, not imported).
STRATEGY_SUPER_NODES = {"eligibility": "eligibility", "default_routing": "routing",
                        "proof_and_truth": "proof", "cashflow_and_settlement": "settlement"}
STATES = ("DISCOVERED", "VERIFIED", "ATTACHED", "DETACHED", "QUARANTINED")
MAX_READ_BYTES = 256 * 1024
KERNEL_ROOT = Path(__file__).resolve().parents[1]


class CapabilityError(RuntimeError):
    """Capability unavailable, malformed, outside its manifest or failed."""


@dataclass
class CapabilityManifest:
    capability_id: str                 # e.g. "fs.read"
    version: str
    provider: str                      # "greg-builtin", "installed:/usr/bin/sha256sum", "api:github"
    function: str                      # functional tag used by Capability Genesis search
    description: str
    route: str
    consequence_class: str
    inputs: dict
    outputs: dict
    target_prefix: str                 # every target this capability touches starts with this
    network: str = "none"              # none | egress-allowlist
    egress_allowlist: tuple = ()
    filesystem: str = "none"           # none | read-scoped | workspace-write
    credentials: tuple = ()            # secret handle names; values never enter manifests or ledger
    binaries: tuple = ()               # exact executables a CLI capability may run
    data_classes: tuple = ()
    budget_ceiling_usd: float = 0.0
    platforms: tuple = ("linux", "darwin")
    retry_safe: bool = False           # read-only and idempotent: an unknown outcome may be re-attempted
    strengthens: tuple = ()            # SUPER_NODES this capability reinforces (Spider-Web rule; required)
    target_from: str = ""              # param holding the URL whose host the signed target must name
    tests: tuple = ()
    provenance: dict = field(default_factory=dict)
    attach: str = "founder command or pre-authorized mission light cone"
    detach: str = "founder CAPABILITY_DETACH; in-flight work reconciles first"
    rollback: str = "detach; retained history is never rewritten"

    def validate(self) -> list[str]:
        problems = []
        if self.route not in ROUTES:
            problems.append(f"unknown route {self.route!r}")
        if self.consequence_class not in CONSEQUENCE_CLASSES:
            problems.append(f"unknown consequence class {self.consequence_class!r}")
        if self.network not in ("none", "egress-allowlist", "target-host-only"):
            problems.append("network must be none, egress-allowlist or target-host-only")
        if (self.network == "target-host-only") != bool(self.target_from):
            problems.append("target-host-only network requires target_from (and only it may use target_from)")
        if self.network == "egress-allowlist" and not self.egress_allowlist:
            problems.append("egress allowlist required")
        if self.filesystem not in ("none", "read-scoped", "workspace-write"):
            problems.append("unknown filesystem class")
        if self.route == "cli" and not self.binaries:
            problems.append("cli capability must name exact binaries")
        if self.retry_safe and self.consequence_class != "read_only":
            problems.append("only read_only capabilities may be retry_safe")
        if not self.target_prefix or self.target_prefix == "*":
            problems.append("bounded target prefix required")
        if not self.strengthens:
            problems.append("Spider-Web rule: capability must declare which control points it strengthens")
        unknown = set(self.strengthens) - set(SUPER_NODES)
        if unknown:
            problems.append(f"unknown super-nodes {sorted(unknown)}")
        problems.extend(self.genome().validate())
        return problems

    def genome(self) -> CapabilityGenome:
        return CapabilityGenome(
            name=self.capability_id, version=self.version, description=self.description,
            interface={"inputs": self.inputs, "outputs": self.outputs}, contracts=[],
            authority=AuthorityEnvelope(max_consequence_class=self.consequence_class,
                                        budget_ceiling_usd=self.budget_ceiling_usd,
                                        requires_human=self.consequence_class in ("financial", "irreversible")),
            acceptance_tests=list(self.tests) or ["declared-by-builder"],
            failure_modes=["unavailable", "refused", "timeout", "outcome_unknown"],
            recovery_path=self.rollback)

    def digest(self) -> str:
        return "sha256:" + hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True).encode()).hexdigest()

    def to_dict(self) -> dict:
        value = asdict(self)
        for key, item in value.items():
            if isinstance(item, tuple):
                value[key] = list(item)
        if not value["target_from"]:
            value.pop("target_from")  # absent when unused: every earlier manifest digest is unchanged
        return value

    @classmethod
    def from_dict(cls, value: dict) -> "CapabilityManifest":
        known = set(cls.__dataclass_fields__)
        if set(value) - known:
            raise CapabilityError(f"unknown manifest fields {sorted(set(value) - known)}")
        data = dict(value)
        for key in ("egress_allowlist", "credentials", "binaries", "data_classes", "platforms", "tests",
                    "strengthens"):
            if key in data:
                data[key] = tuple(data[key])
        return cls(**data)

    def available(self) -> tuple[bool, str]:
        platform = "darwin" if sys.platform == "darwin" else "linux"
        if platform not in self.platforms:
            return False, f"requires {'/'.join(self.platforms)}; this body runs {platform}"
        for binary in self.binaries:
            if not Path(binary).is_absolute() or not os.access(binary, os.X_OK):
                return False, f"binary {binary} not installed or not executable"
        return True, "available"


# -- secret broker ------------------------------------------------------------------

class SecretBroker:
    """Resolves named credential handles at call time only.

    Backends: a mode-0600 JSON file inside the body (development) and, on macOS,
    the login Keychain via /usr/bin/security (read-only lookup; Alfonso adds
    items himself). A worker never receives the vault, only a handle it declared.
    """

    def __init__(self, path: Path, *, keychain_service: str = "uniimente.greg"):
        self.path, self.keychain_service = Path(path), keychain_service

    def _file(self) -> dict:
        if not self.path.exists():
            return {}
        mode = self.path.stat().st_mode & 0o777
        if mode & 0o077:
            raise CapabilityError("secret file must be mode 0600")
        return json.loads(self.path.read_text())

    def put(self, name: str, value: str) -> None:
        data = self._file()
        data[name] = value
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as fh:
            json.dump(data, fh)

    def names(self) -> list[str]:
        return sorted(self._file())

    def resolve(self, name: str, *, declared: tuple) -> str:
        if name not in declared:
            raise CapabilityError(f"credential {name!r} not declared by this capability")
        data = self._file()
        if name in data:
            return data[name]
        if sys.platform == "darwin" and Path("/usr/bin/security").exists():
            proc = subprocess.run(["/usr/bin/security", "find-generic-password", "-s",
                                   self.keychain_service, "-a", name, "-w"],
                                  capture_output=True, text=True, timeout=10)
            if proc.returncode == 0:
                return proc.stdout.rstrip("\n")
        raise CapabilityError(f"credential {name!r} unavailable")


# -- invocation context and adapters ---------------------------------------------

@dataclass
class InvocationContext:
    workspace: Path                    # the only place internal writes may land
    read_roots: tuple[Path, ...]       # filesystem roots this mission may read
    secrets: SecretBroker
    manifest: CapabilityManifest

    def secret(self, name: str) -> str:
        return self.secrets.resolve(name, declared=self.manifest.credentials)


def _inside(path: Path, roots) -> Path:
    resolved = path.resolve()
    for root in roots:
        root = Path(root).resolve()
        if resolved == root or root in resolved.parents:
            return resolved
    raise CapabilityError(f"path {path} outside permitted roots")


def fs_read(params, ctx: InvocationContext) -> dict:
    path = _inside(Path(params["path"]), ctx.read_roots + (ctx.workspace,))
    if not path.is_file():  # absence is a measurement of the world, not a sensor failure
        return {"path": str(path), "exists": False}
    data = path.read_bytes()
    if len(data) > MAX_READ_BYTES:
        raise CapabilityError("file exceeds read ceiling")
    return {"path": str(path), "exists": True, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "text": data.decode("utf-8", errors="replace")}


def fs_list(params, ctx: InvocationContext) -> dict:
    path = _inside(Path(params["path"]), ctx.read_roots + (ctx.workspace,))
    if not path.is_dir():
        return {"path": str(path), "exists": False, "entries": []}
    entries = sorted(p.name + ("/" if p.is_dir() else "") for p in path.iterdir())[:1000]
    return {"path": str(path), "entries": entries}


def fs_write(params, ctx: InvocationContext) -> dict:
    ctx.workspace.mkdir(parents=True, exist_ok=True)
    path = _inside(ctx.workspace / params["relative_path"], (ctx.workspace,))
    content = params["content"]
    if not isinstance(content, str) or len(content.encode()) > MAX_READ_BYTES:
        raise CapabilityError("content must be text under the write ceiling")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(content)
    temporary.replace(path)
    return {"path": str(path), "sha256": hashlib.sha256(content.encode()).hexdigest()}


def _no_network_preexec():
    # Reuse the Kernel's reviewed seccomp filter where libseccomp exists.
    try:
        sys.path.insert(0, str(KERNEL_ROOT / "tools"))
        from offline_test import install_filter  # type: ignore
        install_filter()
    except Exception:
        os._exit(97)  # fail closed: never run an isolated command without isolation


MACOS_NO_NETWORK = "(version 1)(allow default)(deny network*)"


def run_isolated(argv: list, *, cwd: Path, isolate_network: bool = True, timeout: int = 30,
                 extra_env: dict | None = None) -> subprocess.CompletedProcess:
    """Run one command with a scrubbed environment and, by default, no network.

    Linux: the Kernel's seccomp filter (tools/offline_test.py). macOS: the system
    sandbox-exec profile denying network. No isolation available -> refusal.
    """
    env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "HOME": str(cwd), **(extra_env or {})}
    preexec = None
    if isolate_network:
        if sys.platform == "darwin":
            if not Path("/usr/bin/sandbox-exec").exists():
                raise CapabilityError("network isolation unavailable; command refused")
            argv = ["/usr/bin/sandbox-exec", "-p", MACOS_NO_NETWORK, *argv]
        else:
            preexec = _no_network_preexec
    proc = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, timeout=timeout,
                          stdin=subprocess.DEVNULL, preexec_fn=preexec)
    if isolate_network and preexec is not None and proc.returncode == 97:
        raise CapabilityError("network isolation unavailable; command refused")
    return proc


def run_cli(params, ctx: InvocationContext, *, isolate_network: bool = True, timeout: int = 30) -> dict:
    argv = params["argv"]
    if not isinstance(argv, list) or not argv or not all(isinstance(a, str) for a in argv):
        raise CapabilityError("argv must be a non-empty list of strings")
    if argv[0] not in ctx.manifest.binaries:
        raise CapabilityError(f"executable {argv[0]} not in this capability's manifest")
    ctx.workspace.mkdir(parents=True, exist_ok=True)
    proc = run_isolated(argv, cwd=ctx.workspace, isolate_network=isolate_network, timeout=timeout)
    return {"argv": argv, "returncode": proc.returncode,
            "stdout": proc.stdout[:MAX_READ_BYTES].decode("utf-8", errors="replace"),
            "stderr": proc.stderr[-4000:].decode("utf-8", errors="replace")}


def git_inspect(params, ctx: InvocationContext) -> dict:
    repo = _inside(Path(params["path"]), ctx.read_roots)
    def git(*args):
        return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                              timeout=20, env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8",
                                               "GIT_CONFIG_NOSYSTEM": "1", "HOME": str(ctx.workspace)})
    head, status, log = git("rev-parse", "HEAD"), git("status", "--porcelain"), git("log", "--oneline", "-10")
    if head.returncode:
        raise CapabilityError("not a git repository")
    return {"path": str(repo), "head": head.stdout.strip(), "dirty": bool(status.stdout.strip()),
            "recent": log.stdout.strip().splitlines()}


def http_get(params, ctx: InvocationContext) -> dict:
    url = params["url"]
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in ctx.manifest.egress_allowlist:
        raise CapabilityError(f"egress to {parts.hostname!r} not in allowlist")
    request = urllib.request.Request(url, headers={"User-Agent": "uniimente-greg/0.1"})
    with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 - allowlisted https only
        body = response.read(MAX_READ_BYTES + 1)
    if len(body) > MAX_READ_BYTES:
        raise CapabilityError("response exceeds read ceiling")
    return {"url": url, "status": response.status, "sha256": hashlib.sha256(body).hexdigest(),
            "text": body.decode("utf-8", errors="replace"), "trust": "untrusted-external-data"}


CHROME_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
)


def chrome_binary() -> str:
    """The browser GREG drives: an installed Chrome/Chromium (founder-chosen via GREG_CHROMIUM)."""
    for candidate in (os.environ.get("GREG_CHROMIUM", ""), *CHROME_CANDIDATES,
                      *sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))):
        if candidate and Path(candidate).is_file() and os.access(candidate, os.X_OK):
            return candidate
    return CHROME_CANDIDATES[0]


class _VisibleText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts, self.title, self._skip, self._in_title = [], "", 0, False

    def handle_starttag(self, tag, attrs):
        self._skip += tag in ("script", "style", "noscript", "template")
        self._in_title = self._in_title or tag == "title"

    def handle_endtag(self, tag):
        self._skip -= tag in ("script", "style", "noscript", "template") and self._skip > 0
        self._in_title = self._in_title and tag != "title"

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self._skip and data.strip():
            self.parts.append(" ".join(data.split()))


def browser_render(params, ctx: InvocationContext) -> dict:
    """Load a page in a real headless browser, run its JavaScript, return what a person would see.

    The signed target must be ``web:<host>`` of this URL (enforced by the authority office via
    ``target_from``), and the browser may resolve ONLY that host: every other name maps to
    NOTFOUND, so page scripts cannot reach third parties. https, or http on loopback only.
    Fresh profile per call, no extensions, no sync, no background networking.
    """
    import tempfile
    url = str(params["url"])
    parts = urllib.parse.urlsplit(url)
    host = parts.hostname or ""
    loopback = host in ("127.0.0.1", "localhost", "::1")
    authority = f"{host}:{parts.port or (443 if parts.scheme == 'https' else 80)}"
    if parts.scheme != "https" and not (parts.scheme == "http" and loopback):
        raise CapabilityError("browser.render loads https pages (http only on this machine's loopback)")
    binary = chrome_binary()
    with tempfile.TemporaryDirectory(prefix="greg-browser-") as profile:
        argv = [binary, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
                "--disable-extensions", "--disable-background-networking", "--disable-sync",
                "--disable-component-update", "--disable-default-apps", "--mute-audio", "--hide-scrollbars",
                f"--user-data-dir={profile}", f"--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE {host}",
                # Every request goes to a dead proxy except the exact target origin, so page scripts
                # cannot reach third parties even by IP literal (implicit loopback bypass removed).
                "--proxy-server=http://127.0.0.1:9", f"--proxy-bypass-list=<-loopback>;{authority}",
                "--virtual-time-budget=5000", "--dump-dom", url]
        sandboxed = not (sys.platform.startswith("linux") and os.geteuid() == 0)
        if not sandboxed:
            argv.insert(1, "--no-sandbox")  # Chromium cannot sandbox itself as root on Linux; reported below
        env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "HOME": profile}
        try:
            proc = subprocess.run(argv, capture_output=True, timeout=45, env=env, cwd=profile)
        except subprocess.TimeoutExpired as exc:
            raise CapabilityError("browser did not finish rendering within 45 seconds") from exc
    dom = proc.stdout[:MAX_READ_BYTES * 4]
    if proc.returncode or not dom.strip():
        raise CapabilityError("browser could not render the page: " + proc.stderr.decode("utf-8", "replace")[-300:])
    parser = _VisibleText()
    parser.feed(dom.decode("utf-8", errors="replace"))
    text = "\n".join(parser.parts)[:MAX_READ_BYTES]
    return {"url": url, "title": parser.title.strip()[:300], "text": text, "dom_sha256": hashlib.sha256(dom).hexdigest(),
            "dom_bytes": len(dom), "browser": Path(binary).name, "os_sandboxed": sandboxed,
            "egress": f"only {authority} reachable", "trust": "untrusted-external-data"}


def mac_notify(params, ctx: InvocationContext) -> dict:
    text, title = str(params["text"])[:200], str(params.get("title", "GREG"))[:60]
    script = f"display notification {json.dumps(text)} with title {json.dumps(title)}"
    proc = subprocess.run(["/usr/bin/osascript", "-e", script], capture_output=True, text=True, timeout=10)
    if proc.returncode:
        raise CapabilityError("osascript failed: " + proc.stderr[-300:])
    return {"delivered": True}


def mac_screenshot(params, ctx: InvocationContext) -> dict:
    ctx.workspace.mkdir(parents=True, exist_ok=True)
    out = _inside(ctx.workspace / params.get("name", "screen.png"), (ctx.workspace,))
    proc = subprocess.run(["/usr/sbin/screencapture", "-x", str(out)], capture_output=True, timeout=20)
    if proc.returncode or not out.exists():
        raise CapabilityError("screencapture failed; Screen Recording permission may be missing")
    return {"path": str(out), "sha256": hashlib.sha256(out.read_bytes()).hexdigest()}


def mac_frontmost_app(params, ctx: InvocationContext) -> dict:
    script = 'tell application "System Events" to get name of first application process whose frontmost is true'
    proc = subprocess.run(["/usr/bin/osascript", "-e", script], capture_output=True, text=True, timeout=10)
    if proc.returncode:
        raise CapabilityError("Accessibility/Automation permission missing: " + proc.stderr[-300:])
    return {"frontmost": proc.stdout.strip()}


def repo_pin_audit(params, ctx: InvocationContext) -> dict:
    """Read-only contract-consistency audit of real local repositories.

    Metabolized from #101 (egregore/repository_audit.py): the exact-object Git
    reads and the semantic derive() are reused unchanged; the fixed 60-second
    proof mission around them is not. Observes each repository's cached
    origin/main itself, so it can run every night without a pre-known commit.
    """
    repositories, report = _repo_report(params, ctx, profile=None)
    return {"compatible": report["compatible"], "rows": report["rows"],
            "commits": {r["role"]: r["commit"] for r in repositories},
            "drift": [r for r in report["rows"] if not r["matches"]], "source_scope": report["source_scope"]}


def _repo_report(params, ctx: InvocationContext, *, profile):
    from egregore.repository_audit import capture, derive, git_read
    repositories = []
    for repo in params["repositories"]:
        path = _inside(Path(repo["path"]), ctx.read_roots)
        commit = git_read(str(path), "rev-parse", "refs/remotes/origin/main").decode().strip()
        repositories.append({"role": repo["role"], "path": str(path), "commit": commit})
    sources = capture(repositories, profile) if profile else capture(repositories)
    return repositories, derive(sources, params["expected_pin"], params["expected_version"], profile)


def repo_integration_audit(params, ctx: InvocationContext) -> dict:
    """Bounded static integration findings across the organs (read-only).

    Ported from PR #112 (repository_audit integration-v1 profile): exact Git
    blobs of the boundary files plus the Gate/runtime/reflection/bridge sources,
    AST-level checks such as "resume accepts a hash without the Gate". Findings
    are evidence for the founder's morning brief, never authority.
    """
    repositories, report = _repo_report(params, ctx, profile="integration-v1")
    findings = [{k: f[k] for k in ("id", "kind", "summary", "next_action")} | {
        "evidence": {k: f["evidence"].get(k) for k in ("role", "commit", "file", "blob", "line") if k in f["evidence"]}}
        for f in report["findings"]]
    return {"compatible": report["compatible"], "commits": {r["role"]: r["commit"] for r in repositories},
            "finding_ids": sorted(f["id"] for f in findings), "count": len(findings), "findings": findings,
            "authority_findings": sorted(f["id"] for f in findings if f["kind"] == "authority"),
            "coverage": report["coverage"], "limits": report["limits"]}


STRENGTHENS = {
    "fs.read": ("proof",), "fs.list": ("proof",), "fs.write": ("settlement",),
    "git.inspect": ("proof",), "http.get": ("proof", "capability_formation"),
    "mac.notify": ("settlement", "eligibility"), "mac.screenshot": ("proof",),
    "mac.frontmost_app": ("proof", "routing"), "repo.pin_audit": ("proof", "eligibility", "reliability"),
    "repo.integration_audit": ("proof", "eligibility", "reliability"),
    "browser.render": ("proof", "capability_formation"),
}


def _builtin(capability_id, function, description, route, consequence, target_prefix, inputs, outputs, **kw):
    kw.setdefault("strengthens", STRENGTHENS[capability_id])
    kw.setdefault("provenance", {"source": "uniimente-kernel/greg/capabilities.py"})
    return CapabilityManifest(capability_id=capability_id, version="1.0.0", provider="greg-builtin",
                              function=function, description=description, route=route,
                              consequence_class=consequence, inputs=inputs, outputs=outputs,
                              target_prefix=target_prefix,
                              tests=(f"tests/unit/test_greg_capabilities.py::{capability_id}",), **kw)


BUILTINS: dict[str, tuple[CapabilityManifest, object]] = {
    "fs.read": (_builtin("fs.read", "filesystem.read", "Read one file inside permitted roots", "api",
                         "read_only", "fs:", {"path": "str"}, {"sha256": "str", "text": "str"},
                         filesystem="read-scoped", retry_safe=True), fs_read),
    "fs.list": (_builtin("fs.list", "filesystem.list", "List one directory inside permitted roots", "api",
                         "read_only", "fs:", {"path": "str"}, {"entries": "list"},
                         filesystem="read-scoped", retry_safe=True), fs_list),
    "fs.write": (_builtin("fs.write", "filesystem.write", "Write one text file inside the mission workspace",
                          "api", "internal_write", "workspace:", {"relative_path": "str", "content": "str"},
                          {"sha256": "str"}, filesystem="workspace-write"), fs_write),
    "git.inspect": (_builtin("git.inspect", "repository.inspect", "Read HEAD, dirtiness and recent log", "cli",
                             "read_only", "fs:", {"path": "str"}, {"head": "str"}, filesystem="read-scoped",
                             binaries=tuple(b for b in ("/usr/bin/git",) if Path(b).exists()) or ("/usr/bin/git",),
                             retry_safe=True), git_inspect),
    "http.get": (_builtin("http.get", "web.fetch", "HTTPS GET from an explicit egress allowlist", "api",
                          "read_only", "https:", {"url": "str"}, {"text": "str"},
                          network="egress-allowlist", egress_allowlist=("example.com",),
                          data_classes=("public_web",), retry_safe=True), http_get),
    "browser.render": (_builtin("browser.render", "web.render",
                                "Render a page in a real headless browser (JavaScript executed) and read it",
                                "browser", "read_only", "web:", {"url": "str"},
                                {"title": "str", "text": "str", "dom_sha256": "str"},
                                network="target-host-only", data_classes=("public_web",), retry_safe=True,
                                binaries=(chrome_binary(),), target_from="url",
                                provenance={"source": "uniimente-kernel/greg/capabilities.py",
                                            "mechanism_from": "installed Chrome/Chromium --headless --dump-dom"}),
                       browser_render),
    "mac.notify": (_builtin("mac.notify", "founder.notify", "Local macOS notification to the founder",
                            "os_automation", "internal_write", "founder:", {"text": "str"}, {"delivered": "bool"},
                            binaries=("/usr/bin/osascript",), platforms=("darwin",)), mac_notify),
    "mac.screenshot": (_builtin("mac.screenshot", "screen.capture", "Capture the screen into the workspace",
                                "visual", "read_only", "screen:", {"name": "str"}, {"sha256": "str"},
                                binaries=("/usr/sbin/screencapture",), platforms=("darwin",),
                                data_classes=("screen_content",)), mac_screenshot),
    "mac.frontmost_app": (_builtin("mac.frontmost_app", "desktop.observe", "Name the frontmost application",
                                   "os_automation", "read_only", "desktop:", {"none": "no parameters"}, {"frontmost": "str"},
                                   binaries=("/usr/bin/osascript",), platforms=("darwin",),
                                   retry_safe=True), mac_frontmost_app),
    "repo.pin_audit": (_builtin("repo.pin_audit", "repository.contract_audit",
                                "Verify organs pin the same Kernel boundary package (real Git objects, read-only)",
                                "cli", "read_only", "repo:",
                                {"repositories": "list[{role,path}]", "expected_pin": "sha",
                                 "expected_version": "str"}, {"compatible": "bool", "drift": "list"},
                                filesystem="read-scoped", retry_safe=True,
                                binaries=tuple(b for b in ("/usr/bin/git",) if Path(b).exists()) or ("/usr/bin/git",),
                                provenance={"source": "uniimente-kernel/greg/capabilities.py",
                                            "mechanism_from": "PR #101 egregore/repository_audit.py (capture, derive)"}),
                       repo_pin_audit),
    "repo.integration_audit": (_builtin("repo.integration_audit", "repository.integration_audit",
                                        "Static integration findings across Kernel/DALEOBANKS/WMI (exact Git blobs, read-only)",
                                        "cli", "read_only", "repo:",
                                        {"repositories": "list[{role,path}]", "expected_pin": "sha",
                                         "expected_version": "str"},
                                        {"finding_ids": "list[str]", "count": "int", "findings": "list"},
                                        filesystem="read-scoped", retry_safe=True,
                                        binaries=tuple(b for b in ("/usr/bin/git",) if Path(b).exists()) or ("/usr/bin/git",),
                                        provenance={"source": "uniimente-kernel/greg/capabilities.py",
                                                    "mechanism_from": "PR #112 egregore/repository_audit.py integration-v1"}),
                               repo_integration_audit),
}


class CapabilityRegistry:
    """In-memory projection of capability events retained on the canonical spine."""

    def __init__(self):
        self.manifests: dict[str, CapabilityManifest] = {}
        self.adapters: dict[str, object] = {}
        self.state: dict[str, str] = {}
        self.genomes = GenomeRegistry()

    def register(self, manifest: CapabilityManifest, adapter, *, state: str) -> None:
        if state not in STATES:
            raise CapabilityError(f"unknown state {state}")
        problems = manifest.validate()
        if problems:
            raise CapabilityError(f"invalid manifest {manifest.capability_id}: {problems}")
        self.genomes.register(manifest.genome())
        self.manifests[manifest.capability_id] = manifest
        self.adapters[manifest.capability_id] = adapter
        self.state[manifest.capability_id] = state

    def set_state(self, capability_id: str, state: str) -> None:
        if capability_id not in self.manifests or state not in STATES:
            raise CapabilityError("unknown capability or state")
        self.state[capability_id] = state

    def usable(self, capability_id: str) -> tuple[bool, str]:
        if capability_id not in self.manifests:
            return False, "not registered"
        if self.state[capability_id] != "ATTACHED":
            return False, f"state {self.state[capability_id]}"
        return self.manifests[capability_id].available()

    def by_function(self, function: str) -> list[CapabilityManifest]:
        return [m for m in self.manifests.values() if m.function == function]

    def inventory(self) -> list[dict]:
        rows = []
        for cid, manifest in sorted(self.manifests.items()):
            ok, why = manifest.available()
            rows.append({"capability_id": cid, "function": manifest.function, "route": manifest.route,
                         "consequence_class": manifest.consequence_class, "state": self.state[cid],
                         "provider": manifest.provider, "health": "available" if ok else why,
                         "credentials": list(manifest.credentials), "network": manifest.network,
                         "strengthens": list(manifest.strengthens)})
        return rows


def installed_binary(name: str) -> str | None:
    """Locate an installed executable on the standard system path only."""
    found = shutil.which(name, path="/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin")
    return str(Path(found).resolve()) if found else None
