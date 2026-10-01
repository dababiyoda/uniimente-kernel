"""Reviewed Foundry operations, never a general caller-supplied code runner.

Seccomp is installed by the parent before exec. Audit hooks constrain reviewed
Python filesystem calls, not arbitrary Python or native code. Subprocesses and
unreviewed source/child execution fail closed until an OS filesystem sandbox is available.
Three exact reviewed recipes are allowed: restricted-DSL recomputation,
owned-source packaging and the first-party read-only MCP server.
Read-only calls operate on disposable copies and cannot mutate persistent state.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import resource
import sys


def source_files():
    code = Path(__file__).resolve().parents[1]
    inventory = json.loads((code / "foundry" / "owned-source.json").read_text())
    if inventory.get("version") != "owned-source/1" or not isinstance(inventory.get("files"), list) or len(inventory["files"]) > 4096:
        raise ValueError("invalid owned source inventory")
    paths = []
    for relative in inventory["files"]:
        if not isinstance(relative, str) or Path(relative).is_absolute() or any(p in {"", ".", ".."} for p in relative.split("/")):
            raise ValueError("invalid owned source path")
        path = code / relative
        if path.resolve() != path or not path.is_file() or path.stat().st_nlink != 1:
            raise ValueError("owned source must be an existing unlinked file")
        paths.append(path)
    return paths


def guard(root: Path, source_data=()):
    root = root.resolve()
    code = Path(__file__).resolve().parents[1]
    schemas = code / "contracts"
    published = set()
    source_data = set(source_data)
    libraries = [Path(p).resolve() for p in sys.path if p and Path(p).is_dir() and Path(p).resolve() != code]

    def allowed(path, *, write=False, unlink=False):
        if isinstance(path, int):
            return
        p = Path(os.fsdecode(path)).resolve()
        if p == root or root in p.parents:
            if not unlink and p.is_file() and p.stat().st_nlink > 1 and p not in published:
                raise PermissionError("hard-linked workspace file refused")
            return
        if not write and (p in source_data or ((p == code or code in p.parents) and (p.is_dir() or p.suffix in {".py", ".pyc"})) or
                          (schemas in p.parents and p.suffix == ".json") or
                          any(p == lib or lib in p.parents for lib in libraries)):
            return
        raise PermissionError(f"Foundry workspace access refused: {p}")

    def audit(event, args):
        if event == "open":
            _, mode, flags = args
            allowed(args[0], write=bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)))
        elif event == "os.remove":
            allowed(args[0], write=True, unlink=True)
        elif event in {"os.mkdir", "os.rmdir", "os.chmod", "os.utime", "os.truncate"}:
            allowed(args[0], write=True)
        elif event == "os.symlink":
            raise PermissionError("workspace link creation refused")
        elif event == "os.link":
            # ArtifactStore uses a same-root temporary hardlink for atomic
            # no-overwrite publication, then removes the temporary name.
            allowed(args[0], write=True); allowed(args[1], write=True)
            if not Path(args[0]).name.startswith(".pending-"):
                raise PermissionError("only ArtifactStore temporary publication links are permitted")
            published.update(Path(p).resolve() for p in args[:2])
        elif event == "os.rename":
            allowed(args[0], write=True); allowed(args[1], write=True)
        elif event in {"os.listdir", "os.scandir"}:
            allowed(args[0] or ".")
        elif event == "sqlite3.connect":
            allowed(args[0], write=True)
        elif event == "subprocess.Popen":
            executable, argv, cwd, env = args
            reviewed = [sys.executable, "-s", "-m", "greg.foundry_protocol_worker"]
            environment = dict(os.environ) if env is None else env
            if list(argv)[:-1] != reviewed or list(argv)[-1:] not in (["dsl-verify"], ["build-owned"], ["mcp-foundry"]) or executable != sys.executable or cwd is None or Path(cwd).resolve() != code or \
                    environment.get("PYTHONPATH") != str(code) or environment.get("GREG_FOUNDRY_STORE") != str(root) or \
                    environment.get("PYTHONDONTWRITEBYTECODE") != "1" or \
                    set(environment) - ({"PATH", "LANG", "PYTHONPATH", "PYTHONDONTWRITEBYTECODE", "GREG_FOUNDRY_STORE"} |
                        ({"HOME", "FOUNDRY_MCP_ROOT"} if list(argv)[-1:] == ["mcp-foundry"] else set())):
                raise PermissionError("child execution requires OS filesystem confinement")
            if list(argv)[-1:] == ["mcp-foundry"] and (
                    environment.get("HOME") != os.environ.get("HOME") or
                    environment.get("FOUNDRY_MCP_ROOT") != str(root)):
                raise PermissionError("child execution requires OS filesystem confinement")
        elif event in {"os.system", "os.exec", "os.fork", "os.posix_spawn"}:
            raise PermissionError("child execution requires OS filesystem confinement")
        elif event == "exec" and args[0].co_filename == "<target>":
            raise PermissionError("caller source execution requires OS filesystem confinement")
    sys.addaudithook(audit)


def main():
    resource.setrlimit(resource.RLIMIT_CPU, (12, 12))
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    resource.setrlimit(resource.RLIMIT_FSIZE, (8 * 1048576, 8 * 1048576))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    request = json.loads(sys.stdin.buffer.read(131073))
    from foundry.systems import module
    system = request["system"]
    root = Path(request["root"])
    # A composition cannot bypass this by selecting #52 in a child stage.
    if system == 52:
        print(json.dumps({"error": "caller source execution requires OS filesystem confinement"}))
        return
    mod = module(system)
    try:
        store = root.parent
        root.mkdir(parents=True, exist_ok=True)
        os.environ["GREG_FOUNDRY_STORE"] = str(store.resolve())
        guard(store, source_files() if system == 53 else ())
        answer = {"result": getattr(mod, request["table"])[request["op"]](request["args"], root)}
    except Exception as exc:
        answer = {"error": f"{type(exc).__name__}: {str(exc)[:300]}"}
    print(json.dumps(answer, allow_nan=False))


if __name__ == "__main__":
    main()
