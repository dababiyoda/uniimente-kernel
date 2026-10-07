"""Real OS child containment, independent of worker tool-permission promises."""
import errno
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

import pytest

from greg import worker_isolation as isolation


def prepare(tmp_path, monkeypatch, **kwargs):
    monkeypatch.setattr(isolation, "_backend", lambda **_: ("landlock", 3, None, []))
    cwd = tmp_path / "clone"
    cwd.mkdir(exist_ok=True)
    return isolation.prepare_worker([sys.executable], cwd, 30, "codex", reviewed=True, **kwargs)


def test_unsupported_host_refuses_before_staging_credentials(tmp_path, monkeypatch):
    def unavailable():
        raise isolation.WorkerIsolationError("Landlock ABI >= 3 unavailable: Function not implemented")
    monkeypatch.setattr(isolation, "_landlock_abi", unavailable)
    monkeypatch.setattr(isolation.shutil, "which", lambda _: None)
    cwd = tmp_path / "clone"
    cwd.mkdir()
    with pytest.raises(isolation.WorkerIsolationError, match="isolation unavailable") as refusal:
        isolation.prepare_worker([sys.executable], cwd, 30, "codex", reviewed=True)
    assert refusal.value.evidence["status"] == "unsupported"
    assert "Function not implemented" in refusal.value.evidence["reason"]
    assert not (tmp_path / ".worker-runtime").exists()


def test_unreviewed_provider_has_no_compatibility_escape(tmp_path):
    with pytest.raises(isolation.WorkerIsolationError, match="unreviewed"):
        isolation.prepare_worker([sys.executable], tmp_path, 30, "generated")
    with pytest.raises(TypeError, match="compatibility"):
        isolation.prepare_worker([sys.executable], tmp_path, 30, "generated", compatibility=True)


def test_only_selected_provider_and_transport_environment_survives(tmp_path, monkeypatch):
    source = {"HOME": "/private/founder", "GREG_ROOT_KEY": "body-fixture", "GITHUB_TOKEN": "git-fixture",
              "AWS_SECRET_ACCESS_KEY": "cloud-fixture", "PYTHONPATH": "/private/code", "LD_PRELOAD": "/private/loader",
              "BASH_ENV": "/private/hooks", "NODE_OPTIONS": "--require /private/hooks", "PATH": "/private/bin",
              "ANTHROPIC_API_KEY": "wrong-provider-fixture", "OPENAI_API_KEY": "provider-fixture",
              "HTTPS_PROXY": "http://proxy.fixture"}
    envelope = prepare(tmp_path, monkeypatch, source_env=source, config_files={})
    for name in source.keys() - {"HOME", "OPENAI_API_KEY", "HTTPS_PROXY", "PATH"}:
        assert name not in envelope["env"]
    assert envelope["env"]["OPENAI_API_KEY"] == "provider-fixture"
    assert envelope["env"]["HTTPS_PROXY"] == "http://proxy.fixture"
    assert not envelope["env"]["PATH"].startswith("/private")
    assert Path(envelope["env"]["HOME"]) == envelope["runtime_root"] / "home"
    assert envelope["runtime_root"].parent.parent == tmp_path
    assert envelope["evidence"]["network_isolated"] is False
    assert "provider-fixture" not in json.dumps(envelope["evidence"])


@pytest.mark.parametrize("provider,relative", [("codex", ".codex/auth.json"), ("claude-code", ".claude/.credentials.json")])
def test_narrow_credentials_are_private_copies_without_secret_evidence(tmp_path, monkeypatch, provider, relative):
    home = tmp_path / "founder-home"
    credential = home / relative
    credential.parent.mkdir(parents=True)
    credential.write_text('{"fixture": "synthetic-provider-secret"}')
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(isolation, "_backend", lambda **_: ("landlock", 3, None, []))
    cwd = tmp_path / "clone"
    cwd.mkdir()
    envelope = isolation.prepare_worker([sys.executable], cwd, 30, provider, reviewed=True,
                                        config_files={relative: credential}, source_env={})
    target = Path(envelope["env"]["HOME"]) / relative
    assert target.read_bytes() == credential.read_bytes()
    assert target.stat().st_mode & 0o777 == 0o600
    assert envelope["evidence"]["copied_config_files"] == [relative]
    assert "synthetic-provider-secret" not in json.dumps(envelope["evidence"])
    assert str(home) not in envelope["evidence"]["read_roots"]
    target.write_text("changed-private-copy")
    assert "synthetic-provider-secret" in credential.read_text()


def test_wrong_config_source_and_symlink_credentials_refused(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    credential = home / ".codex/auth.json"
    credential.parent.mkdir()
    source = home / "other-secret"
    source.write_text("owned")
    with pytest.raises(isolation.WorkerIsolationError, match="exact credential"):
        prepare(tmp_path, monkeypatch, config_files={".codex/auth.json": source}, source_env={})
    credential.symlink_to(source)
    with pytest.raises(isolation.WorkerIsolationError, match="non-symlink"):
        prepare(tmp_path, monkeypatch, config_files={".codex/auth.json": credential}, source_env={})


def test_missing_optional_provider_config_is_ignored(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "founder-home"))
    envelope = prepare(tmp_path, monkeypatch, source_env={})
    assert envelope["evidence"]["copied_config_files"] == []


def test_workspace_runtime_and_config_directory_symlinks_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(isolation, "_backend", lambda **_: ("landlock", 3, None, []))
    target = tmp_path / "target"
    target.mkdir()
    linked = tmp_path / "clone"
    linked.symlink_to(target, target_is_directory=True)
    with pytest.raises(isolation.WorkerIsolationError, match="workspace"):
        isolation.prepare_worker([sys.executable], linked, 30, "codex", reviewed=True, source_env={})
    linked.unlink()
    linked.mkdir()
    runtime = tmp_path / ".worker-runtime"
    runtime.symlink_to(target, target_is_directory=True)
    with pytest.raises(isolation.WorkerIsolationError, match="runtime path"):
        isolation.prepare_worker([sys.executable], linked, 30, "codex", reviewed=True, source_env={})
    runtime.unlink()
    envelope = prepare(tmp_path, monkeypatch, source_env={}, config_files={})
    home = tmp_path / "founder-home"
    credential = home / ".codex/auth.json"
    credential.parent.mkdir(parents=True)
    credential.write_text("synthetic-original")
    monkeypatch.setenv("HOME", str(home))
    (Path(envelope["env"]["HOME"]) / ".codex").symlink_to(credential.parent)
    with pytest.raises(isolation.WorkerIsolationError, match="symlink"):
        prepare(tmp_path, monkeypatch, source_env={}, config_files={".codex/auth.json": credential})
    assert credential.read_text() == "synthetic-original"


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf"), True, 3601, "invalid"])
def test_timeout_must_be_bounded(tmp_path, timeout):
    with pytest.raises(isolation.WorkerIsolationError, match="timeout"):
        isolation.prepare_worker([sys.executable], tmp_path, timeout, "codex", reviewed=True)


@pytest.mark.parametrize("file_bytes", [0, -1, True, float("inf"), 512 * 1024 ** 2 + 1])
def test_output_file_limits_cannot_be_unbounded(tmp_path, file_bytes):
    with pytest.raises(isolation.WorkerIsolationError, match="file_bytes"):
        isolation.prepare_worker([sys.executable], tmp_path, 30, "codex", reviewed=True, file_bytes=file_bytes)


def support(network=True):
    try:
        return isolation._backend(require_bubblewrap=not network)
    except isolation.WorkerIsolationError as exc:
        if os.environ.get("GREG_REQUIRE_WORKER_ISOLATION") == "1":
            pytest.fail(str(exc))
        pytest.skip(str(exc))


def execute(envelope, cwd):
    return subprocess.run(envelope["argv"], cwd=cwd, env=envelope["env"], preexec_fn=envelope["preexec_fn"],
                          close_fds=True, capture_output=True, text=True, timeout=10)


def test_native_child_confines_reads_writes_truncation_symlinks_git_and_secrets(tmp_path, monkeypatch):
    support()
    cwd = tmp_path / "clone"
    cwd.mkdir()
    metadata = cwd / ".git"
    metadata.mkdir()
    (metadata / "config").write_text("trusted-metadata")
    private = tmp_path / "body-key.fixture"
    private.write_text("synthetic-body-secret")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "private-fixture")
    script = r'''
import ctypes,json,os,resource,sys
from pathlib import Path
root,private=map(Path,sys.argv[1:])
libc=ctypes.CDLL(None,use_errno=True)
libc.open.argtypes=[ctypes.c_char_p,ctypes.c_int]; libc.open.restype=ctypes.c_int
native_read=libc.open(os.fsencode(private),os.O_RDONLY); native_errno=ctypes.get_errno()
(root/'link').symlink_to(private)
linked_read=libc.open(os.fsencode(root/'link'),os.O_RDONLY)
def denied(action):
    try: action(); return False
    except OSError: return True
write_denied=denied(lambda: private.write_text('escaped'))
truncate_denied=denied(lambda: os.truncate(private,0))
metadata_denied=denied(lambda: (root/'.git/config').write_text('injected-clean-filter'))
(root/'owned').write_text('owned')
(Path(os.environ['TMPDIR'])/'temp-file').write_text('private-tmp')
print(json.dumps({'native_read':native_read,'native_errno':native_errno,'linked_read':linked_read,
    'write_denied':write_denied,'truncate_denied':truncate_denied,'metadata_denied':metadata_denied,
    'owned':(root/'owned').read_text(),'home':os.environ['HOME'],'core':resource.getrlimit(resource.RLIMIT_CORE),
    'cpu':resource.getrlimit(resource.RLIMIT_CPU),'memory':resource.getrlimit(resource.RLIMIT_AS),
    'processes':resource.getrlimit(resource.RLIMIT_NPROC),'private_env':'AWS_SECRET_ACCESS_KEY' in os.environ}))
'''
    argv = [sys.executable, "-I", "-c", script, str(cwd), str(private)]
    envelope = isolation.prepare_worker(argv, cwd, 30, "codex", reviewed=True, config_files={})
    result = execute(envelope, cwd)
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)
    assert observed["native_read"] == -1 and observed["native_errno"] in (errno.ENOENT, errno.EACCES)
    assert observed["linked_read"] == -1
    # An empty /tmp may contain a new shadow file at the same absolute name;
    # the original host victim must remain unreadable and unchanged.
    if envelope["evidence"]["mechanism"] == "landlock":
        assert observed["write_denied"] and observed["truncate_denied"]
    if envelope["evidence"]["mechanism"] == "bubblewrap":
        assert observed["metadata_denied"]
    assert observed["owned"] == "owned" and private.read_text() == "synthetic-body-secret"
    assert Path(observed["home"]) == envelope["runtime_root"] / "home"
    assert observed["core"] == [0, 0] and observed["cpu"][0] <= 30
    assert observed["memory"][0] <= 16 * 1024 ** 3 and observed["processes"][0] <= 4096
    assert observed["private_env"] is False


def test_acceptance_child_has_no_host_network_credentials_or_body_access(tmp_path):
    support(network=False)
    cwd = tmp_path / "clone"
    cwd.mkdir()
    victim = tmp_path / "outside-secret"
    victim.write_text("synthetic-body-secret")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0)); listener.listen()
        script = '''
import json,os,socket,sys
from pathlib import Path
s=socket.socket(); s.settimeout(0.2)
try: s.connect(('127.0.0.1',int(sys.argv[1]))); reachable=True
except OSError: reachable=False
print(json.dumps({'reachable':reachable,'outside':Path(sys.argv[2]).exists(),
                  'auth':'OPENAI_API_KEY' in os.environ,'pid':os.getpid()}))
'''
        argv = [sys.executable, "-I", "-c", script, str(listener.getsockname()[1]), str(victim)]
        envelope = isolation.prepare_worker(argv, cwd, 30, "acceptance-tests", reviewed=True,
                                            source_env={"OPENAI_API_KEY": "synthetic-auth"}, network=False)
        result = execute(envelope, cwd)
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)
    assert not observed["reachable"] and not observed["outside"] and not observed["auth"]
    assert observed["pid"] < 10 and envelope["evidence"]["network_isolated"] is True


def test_acceptance_refuses_landlock_only_host(tmp_path, monkeypatch):
    monkeypatch.setattr(isolation, "_landlock_abi", lambda: 3)
    monkeypatch.setattr(isolation.shutil, "which", lambda _: None)
    cwd = tmp_path / "clone"
    cwd.mkdir()
    with pytest.raises(isolation.WorkerIsolationError, match="acceptance processes/network"):
        isolation.prepare_worker([sys.executable], cwd, 30, "acceptance-tests", reviewed=True, source_env={}, network=False)


def test_confined_interpreter_retains_virtualenv_and_installed_pytest(tmp_path):
    support(network=False)
    cwd = tmp_path / "clone"
    cwd.mkdir()
    script = "import json,sys,pytest; print(json.dumps({'prefix':sys.prefix,'pytest':pytest.__version__}))"
    envelope = isolation.prepare_worker([sys.executable, "-I", "-c", script], cwd, 30, "acceptance-tests",
                                        reviewed=True, source_env={}, network=False)
    result = execute(envelope, cwd)
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)
    assert observed["prefix"] == sys.prefix and observed["pytest"] == pytest.__version__
