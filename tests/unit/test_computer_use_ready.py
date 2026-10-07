"""Read-only extraction from WorkOrder PR #150, with its optional-certutil defect repaired."""
import importlib.util

import pytest

from greg import computer
from greg.capabilities import CapabilityError


def patch_prerequisites(monkeypatch, *, playwright=True, chromium="/x/chrome", certutil=False):
    monkeypatch.delenv(computer.TRUST_BUNDLE_ENV, raising=False)
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object() if playwright else None)
    def find_chromium():
        if chromium is None:
            raise CapabilityError("none")
        return chromium
    monkeypatch.setattr(computer, "chromium", find_chromium)
    monkeypatch.setattr(computer.os, "access", lambda path, mode: certutil)
    def no_subprocess(*args, **kwargs):
        raise AssertionError("readiness must never spawn processes")
    monkeypatch.setattr(computer.subprocess, "run", no_subprocess)
    monkeypatch.setattr(computer.subprocess, "Popen", no_subprocess)


def test_certutil_is_optional_without_a_configured_trust_bundle(monkeypatch):
    patch_prerequisites(monkeypatch)
    assert computer.computer_use_ready() == {
        "ready": True, "playwright": True, "chromium": "/x/chrome", "certutil": False,
        "certutil_required": False, "trust_bundle_available": True, "missing": []}


@pytest.mark.parametrize("playwright, chromium, missing", [(False, "/x/chrome", "playwright"),
                                                          (True, None, "chromium")])
def test_missing_browser_dependencies_block_readiness(monkeypatch, playwright, chromium, missing):
    patch_prerequisites(monkeypatch, playwright=playwright, chromium=chromium)
    result = computer.computer_use_ready()
    assert not result["ready"] and result["missing"] == [missing]


def test_configured_trust_bundle_requires_certutil_and_an_existing_bundle(monkeypatch, tmp_path):
    patch_prerequisites(monkeypatch)
    bundle = tmp_path / "missing.pem"
    monkeypatch.setenv(computer.TRUST_BUNDLE_ENV, str(bundle))
    assert computer.computer_use_ready()["missing"] == ["trust_bundle", "certutil"]
    bundle.write_text("certificate")
    assert computer.computer_use_ready()["missing"] == ["certutil"]
    monkeypatch.setattr(computer.os, "access", lambda path, mode: True)
    assert computer.computer_use_ready()["ready"]


def test_missing_trust_bundle_does_not_silently_fall_back_to_system_trust(monkeypatch, tmp_path):
    monkeypatch.setenv(computer.TRUST_BUNDLE_ENV, str(tmp_path / "missing.pem"))
    with pytest.raises(CapabilityError, match="missing trust bundle"):
        computer._trust_profile(tmp_path / "profile")


def test_configured_chromium_is_used_and_invalid_explicit_path_refuses(monkeypatch, tmp_path):
    binary = tmp_path / "chromium"
    binary.write_text("#!/bin/sh\nexit 0\n")
    binary.chmod(0o700)
    monkeypatch.setenv("GREG_CHROMIUM", str(binary))
    assert computer.chromium() == str(binary)
    monkeypatch.setenv("GREG_CHROMIUM", str(tmp_path / "missing"))
    with pytest.raises(CapabilityError, match="GREG_CHROMIUM"):
        computer.chromium()


@pytest.mark.parametrize("configured", [False, True])
def test_chromium_discovers_installed_playwright_cache_without_starting_driver(monkeypatch, tmp_path, configured):
    monkeypatch.delenv("GREG_CHROMIUM", raising=False)
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    cache = tmp_path / "cache"
    monkeypatch.setenv("XDG_CACHE_HOME", str(cache))
    root = tmp_path / "custom-browsers" if configured else cache / "ms-playwright"
    if configured:
        monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(root))
    browser = root / "chromium-9999" / "chrome-linux64" / "chrome"
    browser.parent.mkdir(parents=True)
    browser.write_text("#!/bin/sh\nexit 0\n")
    browser.chmod(0o700)
    monkeypatch.setattr(computer.glob, "glob", lambda pattern: [str(browser)] if pattern.startswith(str(root)) else [])
    def no_subprocess(*args, **kwargs):
        raise AssertionError("browser discovery cannot launch a process")
    monkeypatch.setattr(computer.subprocess, "run", no_subprocess)
    monkeypatch.setattr(computer.subprocess, "Popen", no_subprocess)
    assert computer.chromium() == str(browser)
