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
    service_calls = [c for c in calls if c[0] == "systemctl"]          # the other call is the engine import probe
    assert ready["ready_for_linux_service"] and service_calls == [["systemctl", "--user", "show-environment"]]
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
    monkeypatch.setattr(doctor, "importable", lambda modules: {m: None for m in modules})
    row = doctor.chromebook()["engines"]["engines"][0]
    assert row == {"distribution": "z3-solver", "installed": True, "version": "9.9", "license": "MIT",
                   "serves": doctor.ENGINE_USES["z3-solver"], "importable": True, "import_error": None}


def test_an_installed_engine_the_isolated_worker_cannot_import_is_not_counted_present(monkeypatch):
    # Seen in a container: pandas found dateutil only in ~/.local, which ``python -I`` ignores, so
    # OR-Tools' metadata said installed while every CP-SAT worker failed to import it.
    from greg import mechanisms
    installed = SimpleNamespace(version="9.9", metadata={"License-Expression": "MIT"})
    monkeypatch.setattr(mechanisms, "installed", lambda name: installed)
    broken = "ImportError: Unable to import required dependency dateutil."
    monkeypatch.setattr(doctor, "importable", lambda modules: {
        m: broken if m.startswith("ortools.sat") else None for m in modules})
    report = doctor.engines()
    assert report["present"] == 4 and report["unusable"] == ["ortools"] and report["missing"] == []
    row = next(r for r in report["engines"] if r["distribution"] == "ortools")
    assert row["installed"] and not row["importable"] and "dateutil" in row["import_error"]


def test_the_import_probe_runs_isolated_and_names_the_failing_module():
    probed = doctor.importable(["json", "greg_no_such_module_for_probe"])
    assert probed["json"] is None
    assert probed["greg_no_such_module_for_probe"].startswith("ModuleNotFoundError")


def test_a_probe_that_cannot_run_is_reported_not_raised(monkeypatch):
    monkeypatch.setattr(doctor.subprocess, "run", lambda *a, **kw: 1 / 0)
    assert doctor.importable(["json"]) == {"json": "probe failed: ZeroDivisionError"}
