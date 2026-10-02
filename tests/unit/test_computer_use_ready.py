from greg import computer
from greg.capabilities import CapabilityError


def _patch(monkeypatch, playwright, chromium, certutil):
    import importlib.util
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object() if playwright else None)

    def fake_chromium():
        if chromium is None:
            raise CapabilityError("none")
        return chromium
    monkeypatch.setattr(computer, "chromium", fake_chromium)
    monkeypatch.setattr(computer.os, "access", lambda path, mode: certutil)


def test_all_present(monkeypatch):
    _patch(monkeypatch, True, "/x/chrome", True)
    assert computer.computer_use_ready() == {
        "ready": True, "playwright": True, "chromium": "/x/chrome", "certutil": True}


def test_each_missing_piece_blocks_ready(monkeypatch):
    for pw, ch, ce in [(False, "/x", True), (True, None, True), (True, "/x", False)]:
        _patch(monkeypatch, pw, ch, ce)
        report = computer.computer_use_ready()
        assert report["ready"] is False
        assert (report["playwright"], report["chromium"], report["certutil"]) == (pw, ch, ce)


def test_does_not_launch_anything(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("must not spawn processes")
    monkeypatch.setattr(computer.subprocess, "run", boom)
    monkeypatch.setattr(computer.subprocess, "Popen", boom)
    assert isinstance(computer.computer_use_ready()["ready"], bool)
