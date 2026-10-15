"""The hardware probe makes no enrollment claim and reports service absence honestly."""
from types import SimpleNamespace

from greg import doctor


def test_chromebook_doctor_ready_only_when_linux_user_service_is_available(monkeypatch):
    monkeypatch.setattr(doctor.platform, "system", lambda: "Linux")
    monkeypatch.setattr(doctor.shutil, "which", lambda binary: "/usr/bin/" + binary)
    calls = []
    def service(cmd, **kw):
        calls.append(cmd)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(doctor.subprocess, "run", service)
    ready = doctor.chromebook()
    service_probe = ["systemctl", "--user", "show-environment"]
    # the only other commands are the isolation probes: /usr/bin/true in a bubblewrap namespace, and a throwaway
    # child that installs the Kernel seccomp filter and exits (the #26 confined-egress probe)
    import sys
    from greg.capabilities import KERNEL_ROOT

    def seccomp_probe(c):
        return (c[:3] == [sys.executable, "-I", "-c"] and "install_filter()" in c[3]
                and c[4] == str(KERNEL_ROOT / "tools") and len(c) == 5)
    assert ready["ready_for_linux_service"] and calls[0] == service_probe
    assert all(c == service_probe or (c[0].endswith("bwrap") and c[-1] == "/usr/bin/true") or seccomp_probe(c)
               for c in calls)
    assert any(seccomp_probe(c) for c in calls) and ready["confined_egress"]["available"] is True
    assert "VM restart at login" in ready["not_verified"] and "founder identity" in ready["not_verified"]
    assert "ChromeOS host identity and ownership" in ready["not_verified"]
    monkeypatch.setattr(doctor.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=1))
    blocked = doctor.chromebook()
    assert not blocked["ready_for_linux_service"] and blocked["missing"] == ["user_service_available"]


def test_chromebook_doctor_does_not_probe_service_outside_linux(monkeypatch):
    monkeypatch.setattr(doctor.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(doctor.shutil, "which", lambda binary: "/usr/bin/" + binary)
    monkeypatch.setattr(doctor.subprocess, "run", lambda *a, **kw: 1 / 0)
    assert not doctor.chromebook()["ready_for_linux_service"]


def test_engines_are_reported_with_version_and_license_but_never_made_prerequisites(monkeypatch):
    monkeypatch.setattr(doctor.platform, "system", lambda: "Linux")
    monkeypatch.setattr(doctor.shutil, "which", lambda binary: "/usr/bin/" + binary)
    monkeypatch.setattr(doctor.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=0))
    from greg import mechanisms
    monkeypatch.setattr(mechanisms, "installed", lambda name: None)
    report = doctor.chromebook()
    assert report["ready_for_linux_service"] and report["missing"] == []          # N1 is not blocked by engines
    assert report["engines"]["present"] == 0 and report["engines"]["total"] == 5
    assert set(report["engines"]["missing"]) == {"z3-solver", "ortools", "scipy", "networkx", "sympy"}
    assert "never installs" in report["engines"]["note"]
    installed = SimpleNamespace(version="9.9", metadata={"License-Expression": "MIT"})
    monkeypatch.setattr(mechanisms, "installed", lambda name: installed)
    row = doctor.chromebook()["engines"]["engines"][0]
    assert row == {"distribution": "z3-solver", "installed": True, "version": "9.9", "license": "MIT",
                   "serves": doctor.ENGINE_USES["z3-solver"]}


def test_worker_isolation_is_reported_never_a_prerequisite(monkeypatch):
    from greg import worker_isolation as isolation
    monkeypatch.setattr(doctor.platform, "system", lambda: "Linux")
    monkeypatch.setattr(doctor.shutil, "which", lambda binary: "/usr/bin/" + binary)
    monkeypatch.setattr(doctor.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=0))

    def unavailable(**_):
        raise isolation.WorkerIsolationError("worker OS filesystem isolation unavailable: bubblewrap is unavailable")
    monkeypatch.setattr(isolation, "_backend", unavailable)
    report = doctor.chromebook()
    assert report["ready_for_linux_service"]                               # the body does not need workers
    assert report["worker_isolation"]["workers_can_run_confined"] is False
    assert "bubblewrap" in report["worker_isolation"]["fix"]
    monkeypatch.setattr(isolation, "_backend", lambda **_: ("bubblewrap", None, "/usr/bin/bwrap", []))
    assert doctor.chromebook()["worker_isolation"] == {"workers_can_run_confined": True, "mechanism": "bubblewrap"}


def test_confined_egress_is_reported_unavailable_with_its_fix_when_a_probe_fails(monkeypatch):
    monkeypatch.setattr(doctor.platform, "system", lambda: "Linux")
    monkeypatch.setattr(doctor.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=1, stderr="no libseccomp"))
    from greg import worker_isolation

    def no_namespaces(**kw):
        raise worker_isolation.WorkerIsolationError("bubblewrap not installed")
    monkeypatch.setattr(worker_isolation, "_backend", no_namespaces)
    report = doctor.confined_egress()
    assert report["available"] is False and "kernel filter" in report["why"] and "network namespaces" in report["why"]
    assert "bubblewrap" in report["fix"] and "libseccomp" in report["fix"]
    monkeypatch.setattr(doctor.platform, "system", lambda: "Darwin")
    assert doctor.confined_egress()["available"] is False
