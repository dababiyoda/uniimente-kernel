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
    assert ready["ready_for_linux_service"] and calls == [["systemctl", "--user", "show-environment"]]
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


def test_doctor_reports_frontier_workers_without_running_them(monkeypatch):
    monkeypatch.setattr(doctor.platform, "system", lambda: "Linux")
    present = ("git", "systemctl", "codex")
    monkeypatch.setattr(doctor.shutil, "which", lambda binary: "/usr/bin/" + binary if binary in present else None)
    calls = []
    monkeypatch.setattr(doctor.subprocess, "run", lambda cmd, **kw: calls.append(cmd) or SimpleNamespace(returncode=0))
    report = doctor.chromebook()
    assert report["frontier_workers_installed"] == {"claude": False, "codex": True, "aider": False}
    assert calls == [["systemctl", "--user", "show-environment"]]  # no worker was executed
    assert report["ready_for_linux_service"] and "frontier_workers_installed" not in report["checks"]
