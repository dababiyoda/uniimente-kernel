"""Native file validation plus signed GREG production/appraisal; synthetic canon."""
import io
import json
import shutil
import subprocess
import wave
import xml.etree.ElementTree as ET

import pytest

from foundry.systems import media
from greg.artifacts import ArtifactStore
from greg.body import Body
from greg.capabilities import CapabilityError
from tests.greg_fixtures import Clock, drop, make_body, mission, signed, workspace
from tests.unit.test_greg_foundry_worker import context
from greg import foundry_bridge


def canon():
    return {"canon_id": "note-1", "title": "A machine", "body": "Prove, integrate, continue.",
            "source_refs": ["fixture:founder-note"], "rights": "synthetic owned test canon"}


def test_real_media_decodes_independently_and_tracks_canon(tmp_path):
    output = media.produce(tmp_path, canon())
    store = ArtifactStore(tmp_path / "artifacts")
    manifest = json.loads(store.read(output["manifest"]))
    assert json.loads(store.read(manifest["canon"])) == canon()
    assets = {a["name"]: store.read(a["address"]) for a in output["assets"]}
    assert ET.fromstring(assets["image.svg"]).tag.endswith("svg")
    with wave.open(io.BytesIO(assets["audio.wav"])) as audio:
        assert (audio.getnframes(), audio.getframerate(), audio.getnchannels()) == (16000, 8000, 1)
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        pytest.skip("independent PNG/AVI decoder unavailable; XML/WAV checks ran")
    for name, codec in (("image.png", "png"), ("video.avi", "rawvideo")):
        path = tmp_path / name
        path.write_bytes(assets[name])
        result = subprocess.run([ffprobe, "-v", "error", "-show_streams", "-of", "json", str(path)],
                                capture_output=True, text=True, timeout=10, check=True)
        stream = json.loads(result.stdout)["streams"][0]
        assert (stream["codec_name"], stream["width"], stream["height"]) == (codec, media.WIDTH, media.HEIGHT)
        if name.endswith("avi"):
            assert int(stream["nb_frames"]) == media.FRAMES


def test_interactive_output_escapes_input_and_integrity_refuses_tampering(tmp_path):
    value = canon()
    value["body"] = '<script>fetch("https://example.test")</script>'
    output = media.produce(tmp_path, value)
    store = ArtifactStore(tmp_path / "artifacts")
    asset = next(a for a in output["assets"] if a["name"] == "interactive.html")
    assert b"<script>" not in store.read(asset["address"])
    assert b"&lt;script&gt;" in store.read(asset["address"])
    store.path(asset["address"]).write_bytes(b"substituted")
    with pytest.raises(CapabilityError, match="disagree"):
        media.inspect(tmp_path, output["manifest"])


def test_bounded_worker_produces_media_and_query_rechecks_retained_bytes(tmp_path):
    result = foundry_bridge.apply({"system": 35, "op": "produce", "args": {"canon": canon()}}, context(tmp_path))
    check = foundry_bridge.query({"system": 35, "op": "inspect", "args": {"manifest": result["result"]["manifest"]}},
                                  context(tmp_path, "foundry.query"))
    assert check["result"]["intact"] and check["result"]["assets"] == 5
    assert result["execution"]["arbitrary_source"] == "refused"


def test_signed_body_production_is_independently_appraised_and_corruption_refuted(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    expected = media.produce(tmp_path / "reference", canon())["manifest"]
    check = {"check_id": "media", "description": "all five retained media assets verify",
             "sensor": {"capability": "foundry.query", "target": "foundry:media",
                        "params": {"system": 35, "op": "inspect", "args": {"manifest": expected}}},
             "predicate": {"op": "equals", "field": "result.intact", "value": True}}
    strategy = {"action_id": "produce", "capability": "foundry.apply", "target": "foundry:media",
                "params": {"system": 35, "op": "produce", "args": {"canon": canon()}},
                "advances": ["media"], "rationale": "produce local private assets from the signed canon"}
    spec = mission("m:media", checks=[check], strategies=[strategy],
                   capabilities=["foundry.query", "foundry.apply"], targets=("foundry:*",), ceiling="internal_write")
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        for _ in range(4):
            body.tick(); clock.advance(30)
        initial = body.appraise("m:media")
        assert initial["verdict"] == "VERIFIED", (initial, [(e.type, e.payload) for e in body.journal.replay() if e.type.startswith(("greg.command.", "greg.mission."))])
        store = ArtifactStore(workspace(home, "m:media") / "foundry" / "system-35" / "artifacts")
        manifest = json.loads(store.read(expected))
        store.path(manifest["assets"][0]["address"]).write_bytes(b"substituted")
        verdict = body.appraise("m:media")
        assert verdict["verdict"] == "REFUTED"
        assert not verdict["checks"]["world_reobserved"]
