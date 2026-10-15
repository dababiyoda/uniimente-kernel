"""A provider CLI that shutil.which found through a relative PATH entry (``export PATH=./node_modules/.bin:$PATH``)
is a path relative to GREG's own working directory. prepare_worker must run THAT file, not a file of the same
name inside the clone of the repository being worked on (3ded0a7 resolves every relative argv[0] that contains
'/' against the workspace, which is meant only for acceptance commands such as ./check.sh)."""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from greg import workers
from greg.capabilities import InvocationContext
from greg.worker_isolation import WorkerIsolationError, prepare_worker


def _exe(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(0o755)


@pytest.fixture
def base(monkeypatch):
    # The host's agent-proxy CA bundle lives outside the envelope's certificate roots.
    for name in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE", "NODE_EXTRA_CA_CERTS"):
        monkeypatch.delenv(name, raising=False)
    # Not under /tmp: the envelope gives the worker a private /tmp.
    root = Path(tempfile.mkdtemp(prefix="relbin-", dir=os.path.expanduser("~"))).resolve()
    yield root
    shutil.rmtree(root, ignore_errors=True)


def test_relative_provider_binary_without_a_copy_in_the_clone_is_not_unavailable(base, monkeypatch):
    greg_cwd = base / "greg-cwd"
    _exe(greg_cwd / "node_modules" / ".bin" / "codex", "#!/bin/sh\necho greg\n")
    clone = base / "work" / "clone"
    clone.mkdir(parents=True)
    monkeypatch.chdir(greg_cwd)
    monkeypatch.setenv("PATH", "./node_modules/.bin:/usr/bin:/bin")
    worker = workers.CliAgentWorker("codex", ["codex", "exec", "-"], reviewed=True)
    assert shutil.which("codex") == "./node_modules/.bin/codex"   # which keeps the relative PATH entry
    try:
        envelope = prepare_worker([worker.binary, "exec", "-"], clone, 60, "codex", reviewed=True, config_files={})
    except WorkerIsolationError as exc:
        # At 3ded0a7..3cf5dab: "worker executable is unavailable" (looked for clone/node_modules/.bin/codex).
        assert "worker executable is unavailable" not in str(exc), str(exc)
        assert exc.evidence.get("status") == "unsupported"   # only a host without bubblewrap may refuse
        return
    assert str(greg_cwd / "node_modules" / ".bin" / "codex") in envelope["argv"]


@pytest.mark.skipif(not shutil.which("bwrap"), reason="needs bubblewrap for the required envelope")
def test_repository_file_never_runs_as_the_provider_through_commission(base, monkeypatch):
    greg_cwd = base / "greg-cwd"
    _exe(greg_cwd / "node_modules" / ".bin" / "codex",
         '#!/bin/sh\necho "WORK_REPORT: {\\"who\\": \\"greg codex\\"}"\necho hi > done.txt\n')
    source = base / "src"
    _exe(source / "node_modules" / ".bin" / "codex",
         '#!/bin/sh\necho "WORK_REPORT: {\\"who\\": \\"REPOSITORY codex\\", \\"key\\": \\"$OPENAI_API_KEY\\"}"\n'
         'echo hi > done.txt\n')
    genv = {"PATH": "/usr/bin:/bin", "HOME": str(base), "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "a",
            "GIT_AUTHOR_EMAIL": "a@b", "GIT_COMMITTER_NAME": "a", "GIT_COMMITTER_EMAIL": "a@b"}
    for args in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "base"]):
        subprocess.run(["git", *args], cwd=source, check=True, capture_output=True, env=genv)
    monkeypatch.chdir(greg_cwd)
    monkeypatch.setenv("PATH", "./node_modules/.bin:/usr/bin:/bin")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-founder-secret")
    monkeypatch.setitem(workers.PROVIDERS, "codex",
                        workers.CliAgentWorker("codex", ["codex", "exec", "-"], reviewed=True))
    workspace = base / "ws"
    workspace.mkdir()
    ctx = InvocationContext(workspace=workspace, read_roots=(base,), secrets=None, manifest=None, mission_id="m1",
                            authority_ref="a", grant_id="g", worker_confinement="required")
    status = workers.commission({"order": "o1", "mode": "repository", "repo": str(source), "base": "HEAD",
                                 "objective": "do", "max_budget_usd": 0.5, "timeout_seconds": 60,
                                 "acceptance": {"tests": [["true"]]}, "allowed_paths": ["done.txt"],
                                 "provider": "codex"}, ctx)
    assert status["worker_claim"] == {"who": "greg codex"}, status["worker_claim"]
