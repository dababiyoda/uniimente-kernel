"""Capability broker and authority office: bounded, mediated, receipted, no leakage."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import sys

import pytest

from greg.body import Body
from greg.capabilities import (BUILTINS, CapabilityError, CapabilityManifest, InvocationContext, SecretBroker,
                               fs_read, fs_write, http_get, run_cli, run_isolated)
from greg.lightcone import LightCone
from tests.greg_fixtures import make_body


def _ctx(tmp_path, manifest_id="fs.read", **kw):
    secrets = SecretBroker(tmp_path / "secrets.json")
    return InvocationContext(workspace=tmp_path / "ws", read_roots=(tmp_path / "data",), secrets=secrets,
                             manifest=kw.pop("manifest", BUILTINS[manifest_id][0]))


def test_filesystem_reads_stay_inside_permitted_roots(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "ok.txt").write_text("fine")
    (tmp_path / "secret.txt").write_text("founder secret")
    ctx = _ctx(tmp_path)
    assert fs_read({"path": str(tmp_path / "data" / "ok.txt")}, ctx)["text"] == "fine"
    with pytest.raises(CapabilityError, match="outside permitted roots"):
        fs_read({"path": str(tmp_path / "secret.txt")}, ctx)
    os.symlink(tmp_path / "secret.txt", tmp_path / "data" / "link.txt")
    with pytest.raises(CapabilityError, match="outside permitted roots"):
        fs_read({"path": str(tmp_path / "data" / "link.txt")}, ctx)  # symlink escape refused


def test_writes_land_only_in_the_mission_workspace(tmp_path):
    ctx = replace(_ctx(tmp_path, "fs.write"), target="workspace:notes/a.txt")   # the Gate sets the signed target
    out = fs_write({"relative_path": "notes/a.txt", "content": "x"}, ctx)
    assert Path(out["path"]).read_text() == "x"
    with pytest.raises(CapabilityError, match="outside permitted roots"):
        fs_write({"relative_path": "../../escape.txt", "content": "x"}, ctx)
    with pytest.raises(CapabilityError, match="does not match the signed target"):
        fs_write({"relative_path": "notes/b.txt", "content": "x"}, ctx)          # data never picks the file
    assert not (tmp_path / "ws" / "notes" / "b.txt").exists()


def test_cli_runs_only_declared_binaries_without_network(tmp_path):
    manifest = replace(BUILTINS["git.inspect"][0], binaries=("/usr/bin/true",))
    ctx = _ctx(tmp_path, manifest=manifest)
    with pytest.raises(CapabilityError, match="not in this capability's manifest"):
        run_cli({"argv": ["/bin/sh", "-c", "echo pwned"]}, ctx)
    probe = "import socket\ntry:\n socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n print('NETWORK')\nexcept OSError:\n print('DENIED')"
    proc = run_isolated([sys.executable, "-I", "-c", probe], cwd=tmp_path)
    assert proc.stdout.decode().strip() == "DENIED", proc.stderr.decode()[-300:]


def test_secrets_resolve_only_for_declared_handles(tmp_path):
    broker = SecretBroker(tmp_path / "secrets.json")
    broker.put("github_token", "ghp_supersecret")
    assert oct(os.stat(tmp_path / "secrets.json").st_mode & 0o777) == "0o600"
    assert broker.resolve("github_token", declared=("github_token",)) == "ghp_supersecret"
    with pytest.raises(CapabilityError, match="not declared"):
        broker.resolve("github_token", declared=())


def test_egress_is_allowlisted_and_https_only(tmp_path):
    ctx = _ctx(tmp_path, "http.get")
    for url in ("https://evil.example.net/x", "http://example.com/", "file:///etc/passwd"):
        with pytest.raises(CapabilityError, match="not in allowlist"):
            http_get({"url": url}, ctx)


def test_platform_bound_capabilities_report_unavailable_instead_of_faking():
    ok, why = BUILTINS["mac.screenshot"][0].available()
    if sys.platform != "darwin":
        assert not ok and "requires darwin" in why


def test_manifest_rejects_unbounded_or_mislabelled_capabilities():
    base = BUILTINS["fs.read"][0]
    assert replace(base, target_prefix="*").validate()
    assert replace(base, consequence_class="internal_write", retry_safe=True).validate()
    assert replace(base, route="telepathy").validate()
    assert replace(base, network="egress-allowlist").validate()


def _office_body(tmp_path):
    home, key, body_id, data = make_body(tmp_path)
    body = Body(home).open()
    return body, data


def _cone(capabilities, ceiling="internal_write", budget=1.0):
    return LightCone.from_dict({"capabilities": capabilities, "targets": ["fs:*", "workspace:*", "https:*"],
                                "max_consequence_class": ceiling, "budget_usd": budget,
                                "horizon": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()})


def test_actions_outside_the_founder_cone_get_no_grant(tmp_path):
    body, data = _office_body(tmp_path)
    try:
        manifest, adapter = BUILTINS["fs.write"]
        ctx = InvocationContext(workspace=tmp_path / "ws", read_roots=(data,), secrets=body.secrets, manifest=manifest)
        grants_before = len(body.office.grants._grants)
        out = body.office.act(mission_id="m:t", cone=_cone(["fs.read"]), command_digest="sha256:x", manifest=manifest,
                              adapter=adapter, ctx=ctx, params={"relative_path": "a", "content": "b"},
                              target="workspace:a", cost_usd=0.0, expected_outcome="written", evidence_refs=[],
                              attempt=0, spent_usd=0.0, approved_scopes=set())
        assert out.status == "OUTSIDE_SCOPE" and len(body.office.grants._grants) == grants_before
        assert not (tmp_path / "ws" / "a").exists()
        # The exact scope approved by the founder is admitted, and only that scope.
        out2 = body.office.act(mission_id="m:t", cone=_cone(["fs.read"]), command_digest="sha256:x",
                               manifest=manifest, adapter=adapter, ctx=ctx,
                               params={"relative_path": "a", "content": "b"}, target="workspace:a", cost_usd=0.0,
                               expected_outcome="written", evidence_refs=[], attempt=0, spent_usd=0.0,
                               approved_scopes={out.scope_digest})
        assert out2.status == "DONE" and (tmp_path / "ws" / "a").read_text() == "b"
        receipt = body.ledger.find(out2.receipt_hash)
        assert receipt.record_type == "receipt" and receipt.payload["grant_id"] == out2.grant_id
    finally:
        body.close()


def test_consequence_class_comes_from_manifest_not_caller(tmp_path):
    body, data = _office_body(tmp_path)
    try:
        manifest, adapter = BUILTINS["fs.write"]  # internal_write
        ctx = InvocationContext(workspace=tmp_path / "ws", read_roots=(data,), secrets=body.secrets, manifest=manifest)
        out = body.office.act(mission_id="m:t", cone=_cone(["fs.write"], ceiling="read_only"),
                              command_digest="sha256:x", manifest=manifest, adapter=adapter, ctx=ctx,
                              params={"relative_path": "a", "content": "b"}, target="workspace:a", cost_usd=0.0,
                              expected_outcome="written", evidence_refs=[], attempt=0, spent_usd=0.0,
                              approved_scopes=set())
        assert out.status == "OUTSIDE_SCOPE"
        assert any("exceeds scope ceiling" in r for r in out.reasons)
    finally:
        body.close()


def test_crash_after_dispatch_is_uncertain_and_receipts_are_reused(tmp_path):
    body, data = _office_body(tmp_path)
    try:
        manifest, adapter = BUILTINS["fs.write"]
        ctx = InvocationContext(workspace=tmp_path / "ws", read_roots=(data,), secrets=body.secrets, manifest=manifest)
        kwargs = dict(mission_id="m:t", cone=_cone(["fs.write"]), command_digest="sha256:x", manifest=manifest,
                      adapter=adapter, ctx=ctx, params={"relative_path": "a", "content": "b"}, target="workspace:a",
                      cost_usd=0.0, expected_outcome="written", evidence_refs=[], spent_usd=0.0,
                      approved_scopes=set())
        done = body.office.act(attempt=0, **kwargs)
        again = body.office.act(attempt=0, **kwargs)
        assert again.status == "DONE" and again.receipt_hash == done.receipt_hash
        assert len(body.ledger.by_type("receipt")) == 1  # no duplicate consequence

        def exploding(params, ctx):
            raise RuntimeError("power lost mid-effect")
        crash = body.office.act(attempt=1, **{**kwargs, "adapter": exploding})
        assert crash.status == "UNCERTAIN"
        retry = body.office.act(attempt=1, **kwargs)
        assert retry.status == "UNCERTAIN"  # never a blind redispatch of the same effect
    finally:
        body.close()


def test_secret_values_never_enter_the_ledger(tmp_path):
    body, data = _office_body(tmp_path)
    try:
        body.secrets.put("api_key", "sk-live-DO-NOT-LEAK")
        manifest = CapabilityManifest(capability_id="demo.secret", version="1.0.0", provider="test",
                                      function="demo.secret", description="uses a secret", route="api",
                                      consequence_class="read_only", inputs={"x": "str"}, outputs={"ok": "bool"},
                                      target_prefix="fs:", credentials=("api_key",), strengthens=("proof",))
        body.registry.register(manifest, lambda p, c: {"ok": c.secret("api_key") == "sk-live-DO-NOT-LEAK"},
                               state="ATTACHED")
        ctx = InvocationContext(workspace=tmp_path / "ws", read_roots=(data,), secrets=body.secrets, manifest=manifest)
        out = body.office.act(mission_id="m:t", cone=_cone(["demo.secret"]), command_digest="sha256:x",
                              manifest=manifest, adapter=body.registry.adapters["demo.secret"], ctx=ctx, params={},
                              target="fs:x", cost_usd=0.0, expected_outcome="ok", evidence_refs=[], attempt=0,
                              spent_usd=0.0, approved_scopes=set())
        assert out.status == "DONE" and out.output == {"ok": True}
        assert "sk-live-DO-NOT-LEAK" not in Path(body.layout.ledger).read_text()
    finally:
        body.close()


def test_git_inspect_runs_nothing_the_inspected_repository_configures(tmp_path):
    """git.inspect is a read-only sensor (and the appraiser re-observes with it): a repository's own config must not
    make it execute anything. Measured before the fix: a planted core.fsmonitor ran on every inspection. A clean
    filter is the other route git status takes into repository-chosen code. Dirtiness is still reported."""
    import subprocess as sp
    from greg.capabilities import BUILTINS, InvocationContext, SecretBroker, git_inspect
    repo, marker = tmp_path / "repo", tmp_path / "ran"
    repo.mkdir()
    git = lambda *a: sp.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *a],
                            check=True, capture_output=True)
    git("init", "-q")
    (repo / ".gitattributes").write_text("*.txt filter=planted\n")
    (repo / "a.txt").write_text("one\n")
    git("add", "-A")
    git("commit", "-q", "-m", "first")
    script = tmp_path / "planted.sh"
    script.write_text(f"#!/bin/sh\necho \"$0 $*\" >> {marker}\ncat\n")
    script.chmod(0o755)
    git("config", "core.fsmonitor", str(script))
    git("config", "filter.planted.clean", f"{script} clean")
    git("config", "filter.planted.process", f"{script} process")
    (repo / "a.txt").write_text("two\n")                      # forces git status to look at the content
    ctx = InvocationContext(workspace=tmp_path / "ws", read_roots=(tmp_path,), secrets=SecretBroker(tmp_path / "v"),
                            manifest=BUILTINS["git.inspect"][0])
    out = git_inspect({"path": str(repo)}, ctx)
    assert not marker.exists(), marker.read_text()
    assert out["dirty"] is True and len(out["head"]) == 40


# -- #26 redirect hardening: a 3xx is a new request, re-checked or refused ---------
# The transport below the redirect handler is replaced (tests/fake_web.py); urllib's
# own redirect machinery runs, so the old default-follow behaviour is what is tested.

def _web(monkeypatch, routes):
    from tests.fake_web import FakeWeb
    return FakeWeb(routes).install(monkeypatch)


def test_http_get_redirect_off_the_allowlist_is_refused_before_it_is_sent(tmp_path, monkeypatch):
    web = _web(monkeypatch, {"https://example.com/a": (302, "https://evil.example.net/steal", b""),
                             "https://evil.example.net/steal": (200, None, b"attacker page")})
    with pytest.raises(CapabilityError, match="not in allowlist"):
        http_get({"url": "https://example.com/a"}, _ctx(tmp_path, "http.get"))
    assert web.hosts() == ["example.com"]                     # evil.example.net received nothing


@pytest.mark.parametrize("location", ["http://example.com/plain", "https://user:pw@example.com/x",
                                      "https://example.com:99999/x", "file:///etc/passwd"])
def test_http_get_redirect_downgrade_userinfo_or_bad_port_is_refused(tmp_path, monkeypatch, location):
    web = _web(monkeypatch, {"https://example.com/a": (301, location, b"")})
    with pytest.raises(CapabilityError):
        http_get({"url": "https://example.com/a"}, _ctx(tmp_path, "http.get"))
    assert len(web.seen) == 1


def test_http_get_redirect_chain_of_four_is_refused(tmp_path, monkeypatch):
    routes = {f"https://example.com/{i}": (302, f"https://example.com/{i + 1}", b"") for i in range(4)}
    routes["https://example.com/4"] = (200, None, b"too far")
    web = _web(monkeypatch, routes)
    with pytest.raises(CapabilityError, match="exceeds 3 hops"):
        http_get({"url": "https://example.com/0"}, _ctx(tmp_path, "http.get"))
    assert [r["url"] for r in web.seen] == [f"https://example.com/{i}" for i in range(4)]


def test_http_get_follows_three_allowlisted_hops_and_reports_where_it_read(tmp_path, monkeypatch):
    routes = {f"https://example.com/{i}": (307, f"/{i + 1}", b"") for i in range(3)}
    routes["https://example.com/3"] = (200, None, b"final page")
    _web(monkeypatch, routes)
    out = http_get({"url": "https://example.com/0"}, _ctx(tmp_path, "http.get"))
    assert out["text"] == "final page" and out["url"] == "https://example.com/0"
    assert out["final_url"] == "https://example.com/3"


def test_credentials_are_never_forwarded_to_another_host(monkeypatch):
    import urllib.request
    from greg import egress
    web = _web(monkeypatch, {"https://a.example/x": (302, "https://a.example/y", b""),
                             "https://a.example/y": (308, "https://b.example/z", b""),
                             "https://b.example/z": (302, "https://a.example/back", b""),
                             "https://a.example/back": (200, None, b"ok")})
    request = urllib.request.Request("https://a.example/x", headers={"Authorization": "Bearer secret",
                                                                     "Cookie": "s=1", "Accept": "x/y"})
    with egress.open_checked(request, allowlist=("a.example", "b.example"), timeout=5) as response:
        assert response.read() == b"ok"
    sent = [(r["url"], "authorization" in r["headers"], "cookie" in r["headers"]) for r in web.seen]
    assert sent == [("https://a.example/x", True, True), ("https://a.example/y", True, True),
                    ("https://b.example/z", False, False), ("https://a.example/back", False, False)]
    assert all(r["headers"].get("accept") == "x/y" for r in web.seen)
    # each hop names its own host: a stale Host header would misroute the hop
    assert [r["headers"]["host"] for r in web.seen] == ["a.example", "a.example", "b.example", "a.example"]


def test_a_redirected_post_is_never_resent(monkeypatch):
    import urllib.request
    from greg import egress
    web = _web(monkeypatch, {"https://a.example/post": (303, "https://a.example/get", b"")})
    request = urllib.request.Request("https://a.example/post", data=b"payload", method="POST")
    with pytest.raises(egress.EgressRefused, match="POST"):
        egress.open_checked(request, allowlist=("a.example",), timeout=5)
    assert [r["url"] for r in web.seen] == ["https://a.example/post"]
