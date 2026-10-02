"""The hardware probe makes no enrollment claim and reports service absence honestly."""
from types import SimpleNamespace
from pathlib import Path
import importlib.metadata

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


def package_fixture(monkeypatch, *, version="4.15.4.0"):
    def distribution(name):
        if name == "z3-solver":
            return SimpleNamespace(version=version, metadata={"License-Expression": "MIT"})
        raise importlib.metadata.PackageNotFoundError(name)
    monkeypatch.setattr(doctor.importlib.metadata, "distribution", distribution)
    monkeypatch.setattr(doctor.importlib.util, "find_spec", lambda name: object() if name in ("ensurepip", "z3") else None)
    monkeypatch.setattr(doctor, "_reviewed_pins", lambda: {"z3-solver": {"version": "4.15.4.0", "recipe": "requirements-cognition.txt"}})


def test_engine_presence_never_establishes_native_qualification_attachment_or_authority(monkeypatch, tmp_path):
    package_fixture(monkeypatch)
    monkeypatch.setattr(doctor.subprocess, "run", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("doctor engine probe executed a command")))
    home = tmp_path / "absent-body"
    report = doctor.engines(home)
    assert report["present"] == 1 and report["authority_created"] is False and not home.exists()
    z3 = next(r for r in report["engines"] if r["distribution"] == "z3-solver")
    assert z3["package_present"] is True and z3["version"] == "4.15.4.0"
    assert z3["dependency_available"] is True and z3["native_execution_verified"] is None
    assert z3["license_verification"].startswith("metadata only")
    assert z3["capabilities"][0]["attached"] is None
    assert z3["capabilities"][0]["qualified_for_task"] is None
    assert z3["capabilities"][0]["authorized_for_task"] is None


def test_wrong_package_version_is_present_but_dependency_unavailable(monkeypatch):
    package_fixture(monkeypatch, version="0.0.1")
    report = doctor.engines()
    z3 = next(r for r in report["engines"] if r["distribution"] == "z3-solver")
    assert z3["installed"] is True and z3["version_matches_reviewed_pin"] is False
    assert z3["dependency_available"] is False and report["version_mismatches"] == ["z3-solver"]


def test_missing_module_is_not_treated_as_available_by_metadata(monkeypatch):
    package_fixture(monkeypatch)
    monkeypatch.setattr(doctor.importlib.util, "find_spec", lambda name: None)
    z3 = next(r for r in doctor.engines()["engines"] if r["distribution"] == "z3-solver")
    assert z3["package_present"] is True and z3["module_path_present"] is False
    assert z3["dependency_available"] is False


def test_native_doctor_reads_signed_detachment_without_mutating_body(monkeypatch, tmp_path):
    from greg.body import Body
    from tests.greg_fixtures import make_body, signed
    home, key, body_id, _ = make_body(tmp_path)
    with Body(home) as body:
        body.apply(signed(key, body_id, "CAPABILITY_DETACH", {"capability_id": "cognition.formal"}))
    package_fixture(monkeypatch)
    before = {str(p.relative_to(home)): p.read_bytes() for p in Path(home).rglob("*") if p.is_file()}
    report = doctor.engines(home)
    after = {str(p.relative_to(home)): p.read_bytes() for p in Path(home).rglob("*") if p.is_file()}
    assert after == before and report["body_registry"]["inspected"] is True
    formal = next(r for r in report["engines"] if r["distribution"] == "z3-solver")["capabilities"][0]
    assert formal["lifecycle_state"] == "DETACHED" and formal["attached"] is False
    assert formal["available"] is True and formal["authorized_for_task"] is None


def test_doctor_uses_exact_reviewed_recipes_without_treating_them_as_native_evidence():
    pins = doctor._reviewed_pins()
    assert pins["z3-solver"]["version"] == "4.15.4.0"
    assert pins["ortools"]["version"] == "9.15.6755"
    assert pins["protobuf"]["version"] == "6.33.5"
