"""The CLI's result files are replaced through a temporary file nobody else could have planted (review of #238).

Each command that writes a result (`greg compute benchmark --out`, `greg cognition package --out`,
`greg anchor export --out`) wrote ``<name>.tmp`` beside the target and renamed it over. That fixed name was never
checked: ``write_text`` follows a symlink planted there, so a benchmark could overwrite a file inside the body home
(its ledger) despite the --out guard, and any regular ``<name>.tmp`` was clobbered silently. holder.json, which
holds every undisclosed claim, also existed at 0644 until its chmod. ``cli._replace_with`` creates the temporary
file with mkstemp: a fresh name, O_EXCL, the final mode from the start.
"""
from __future__ import annotations

import json
import os
import stat

import pytest

from greg import cli
from tests.unit.test_greg_compute_closure import make_body


def test_a_benchmark_never_writes_through_a_planted_temporary_name(tmp_path):
    home, *_ = make_body(tmp_path)
    ledger = home / "ledger.jsonl"
    held = ledger.read_bytes()
    out_dir = tmp_path / "results"
    out_dir.mkdir()
    (out_dir / "b.json.tmp").symlink_to(ledger)                            # aimed at the body's ledger
    assert cli.main(["--home", str(home), "compute", "benchmark", "--runs", "1", "--out", str(out_dir / "b.json")]) == 0
    assert ledger.read_bytes() == held
    assert json.loads((out_dir / "b.json").read_text())["kind"] == "compute.benchmark"
    assert os.readlink(out_dir / "b.json.tmp") == str(ledger)              # left as it was found


def test_a_benchmark_leaves_a_regular_file_at_the_temporary_name_alone(tmp_path):
    home, *_ = make_body(tmp_path)
    out_dir = tmp_path / "results"
    out_dir.mkdir()
    (out_dir / "b.json.tmp").write_text("someone else's notes\n")
    assert cli.main(["--home", str(home), "compute", "benchmark", "--runs", "1", "--out", str(out_dir / "b.json")]) == 0
    assert (out_dir / "b.json.tmp").read_text() == "someone else's notes\n"


@pytest.mark.parametrize("mode", [0o600, 0o644])
def test_the_replacement_has_its_final_mode_from_creation_and_leaves_no_temporary(tmp_path, monkeypatch, mode):
    target = tmp_path / "holder.json"
    seen = []
    real_write = os.write

    def observed(fd, data):                     # the mode while the content is being written
        seen.append(stat.S_IMODE(os.fstat(fd).st_mode))
        return real_write(fd, data)

    monkeypatch.setattr(os, "write", observed)
    cli._replace_with(target, "secret\n", mode)
    assert target.read_text() == "secret\n" and stat.S_IMODE(target.stat().st_mode) == mode
    assert seen and all(m & 0o077 == 0 for m in seen)                    # never wider than the owner while written
    assert sorted(p.name for p in tmp_path.iterdir()) == ["holder.json"]


def test_a_failed_replacement_removes_its_temporary_and_keeps_the_target(tmp_path, monkeypatch):
    target = tmp_path / "w.json"
    target.write_text("old\n")

    def refuse(src, dst):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(os, "replace", refuse)
    with pytest.raises(OSError):
        cli._replace_with(target, "new\n")
    assert target.read_text() == "old\n" and sorted(p.name for p in tmp_path.iterdir()) == ["w.json"]
