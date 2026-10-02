"""#35 Canon-bound local media production, using GREG's immutable ArtifactStore.

Produces real SVG/PNG, WAV, uncompressed AVI and an interactive HTML card.
These are deterministic graphic compositions and tone cues, not synthesized
speech, cinematic generation or external distribution. Input rights/provenance
are declarations; integrity never grants publishing authority.
"""
from __future__ import annotations

import hashlib
import html
import io
import json
import math
from pathlib import Path
import struct
import wave
import zlib

from greg.artifacts import ArtifactStore
from greg.capabilities import CapabilityError

WIDTH, HEIGHT, FPS, FRAMES = 96, 54, 4, 8
VERSION = "canon-media/1"


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def canon(value):
    if not isinstance(value, dict) or set(value) != {"canon_id", "title", "body", "source_refs", "rights"}:
        raise ValueError("canon needs canon_id, title, body, source_refs and declared rights")
    for key, limit in (("canon_id", 128), ("title", 256), ("body", 4096), ("rights", 256)):
        if not isinstance(value[key], str) or not value[key].strip() or len(value[key]) > limit:
            raise ValueError(f"invalid canon {key}")
    if not isinstance(value["source_refs"], list) or not 1 <= len(value["source_refs"]) <= 32 or any(
            not isinstance(r, str) or not r or len(r) > 256 for r in value["source_refs"]):
        raise ValueError("bounded provenance references required")
    return value


def _chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def _pixels(seed, frame=0):
    return bytes(seed[(x // 8 + y // 6 + frame + c) % len(seed)]
                 for y in range(HEIGHT) for x in range(WIDTH) for c in range(3))


def _png(seed, title):
    pixels = _pixels(seed)
    rows = b"".join(b"\0" + pixels[y * WIDTH * 3:(y + 1) * WIDTH * 3] for y in range(HEIGHT))
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", struct.pack(">IIBBBBB", WIDTH, HEIGHT, 8, 2, 0, 0, 0)) +
            _chunk(b"tEXt", b"Title\0" + title.encode("latin-1", "replace")) +
            _chunk(b"IDAT", zlib.compress(rows, 9)) + _chunk(b"IEND", b""))


def _wav(seed):
    stream = io.BytesIO()
    with wave.open(stream, "wb") as out:
        out.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
        frequency = 220 + seed[0]
        samples = [int(4000 * math.sin(2 * math.pi * frequency * i / 8000) *
                       min(1, i / 200, (16000 - i) / 200)) for i in range(16000)]
        out.writeframes(struct.pack("<" + "h" * len(samples), *samples))
    return stream.getvalue()


def _riff(kind, data):
    return kind + struct.pack("<I", len(data)) + data + (b"\0" if len(data) % 2 else b"")


def _avi(seed):
    frame_size = WIDTH * HEIGHT * 3
    avih = struct.pack("<14I", 1000000 // FPS, frame_size * FPS, 0, 0x10, FRAMES,
                       0, 1, frame_size, WIDTH, HEIGHT, 0, 0, 0, 0)
    strh = struct.pack("<4s4sIHH8I4h", b"vids", b"DIB ", 0, 0, 0, 0, 1, FPS,
                       0, FRAMES, frame_size, 0xffffffff, 0, 0, 0, WIDTH, HEIGHT)
    strf = struct.pack("<IiiHHIIiiII", 40, WIDTH, HEIGHT, 1, 24, 0, frame_size, 0, 0, 0, 0)
    hdrl = _riff(b"LIST", b"hdrl" + _riff(b"avih", avih) +
                 _riff(b"LIST", b"strl" + _riff(b"strh", strh) + _riff(b"strf", strf)))
    frames, indexes, offset = [], [], 4
    for frame in range(FRAMES):
        rgb = _pixels(seed, frame)
        bgr = b"".join(bytes((rgb[i + 2], rgb[i + 1], rgb[i])) for y in reversed(range(HEIGHT))
                       for i in range(y * WIDTH * 3, (y + 1) * WIDTH * 3, 3))
        part = _riff(b"00db", bgr)
        frames.append(part)
        indexes.append(struct.pack("<4sIII", b"00db", 0x10, offset, frame_size))
        offset += len(part)
    return _riff(b"RIFF", b"AVI " + hdrl + _riff(b"LIST", b"movi" + b"".join(frames)) +
                 _riff(b"idx1", b"".join(indexes)))


def _contents(value):
    seed = hashlib.sha256(_json(value)).digest()
    title, body = html.escape(value["title"]), html.escape(value["body"])
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360">'
           f'<rect width="640" height="360" fill="#162535"/>'
           f'<text x="24" y="80" fill="white" font-size="24">{title}</text>'
           f'<desc>{body}</desc></svg>').encode()
    interactive = (f'<!doctype html><meta charset="utf-8"><title>{title}</title>'
                   f'<h1>{title}</h1><p>{body}</p><label>Preview intensity '
                   '<input type="range" min="0" max="100" value="50" '
                   'oninput="document.getElementById(\'value\').textContent=this.value"></label>'
                   '<output id="value">50</output><p>Local preview; no publication or network.</p>').encode()
    return (("image.svg", "image/svg+xml", svg), ("image.png", "image/png", _png(seed, value["title"])),
                                ("audio.wav", "audio/wav", _wav(seed)), ("video.avi", "video/x-msvideo", _avi(seed)),
                                ("interactive.html", "text/html", interactive))


def produce(root: Path, value: dict):
    value = canon(value)
    store = ArtifactStore(Path(root) / "artifacts")
    source, _ = store.put(_json(value))
    assets = []
    for name, mime, content in _contents(value):
        address, _ = store.put(content)
        assets.append({"name": name, "mime": mime, "address": address, "bytes": len(content)})
    manifest = {"version": VERSION, "canon": source, "canon_id": value["canon_id"], "assets": assets,
                "provenance": {"source_refs": value["source_refs"], "rights": value["rights"],
                               "status": "declared_not_independently_verified"},
                "limitations": "graphic compositions and tone cues; no synthesized narration, live distribution or commercial proof",
                "authority_created": False}
    address, _ = store.put(_json(manifest))
    return {"manifest": address, "assets": assets, "authority_created": False}


def inspect(root, address):
    store = ArtifactStore(Path(root) / "artifacts")
    manifest = json.loads(store.read(address))
    if manifest["version"] != VERSION:
        raise ValueError("unknown media manifest")
    value = canon(json.loads(store.read(manifest["canon"])))
    if set(manifest) != {"version", "canon", "canon_id", "assets", "provenance", "limitations", "authority_created"} or \
            manifest["limitations"] != "graphic compositions and tone cues; no synthesized narration, live distribution or commercial proof" or \
            manifest["canon_id"] != value["canon_id"] or manifest["authority_created"] is not False or \
            manifest["provenance"] != {"source_refs": value["source_refs"], "rights": value["rights"],
                                      "status": "declared_not_independently_verified"}:
        raise ValueError("media manifest differs from canonical provenance")
    expected = _contents(value)
    if not isinstance(manifest["assets"], list) or len(manifest["assets"]) != len(expected):
        raise ValueError("media manifest does not contain every canonical format")
    for asset, (name, mime, content) in zip(manifest["assets"], expected):
        if set(asset) != {"name", "mime", "address", "bytes"} or asset["name"] != name or asset["mime"] != mime or \
                asset["bytes"] != len(content) or store.read(asset["address"]) != content:
            raise ValueError("media asset differs from its canonical production contract")
    return {"intact": True, "canon_id": value["canon_id"], "assets": len(manifest["assets"]),
            "manifest": address, "authority_created": False}


def observed(root, address):
    try:
        return inspect(root, address)
    except (CapabilityError, KeyError, ValueError, TypeError) as exc:
        return {"intact": False, "assets": 0, "manifest": address, "reason": type(exc).__name__,
                "authority_created": False}


QUERY_OPS = {"inspect": lambda a, r: observed(r, a["manifest"])}
APPLY_OPS = {"produce": lambda a, r: produce(r, a["canon"])}


def exercise(root):
    value = {"canon_id": "owned-note-v1", "title": "One machine", "body": "Prove, integrate, continue.",
             "source_refs": ["fixture:full-machine"], "rights": "synthetic owned fixture"}
    output = produce(root, value)
    return {"manifest": output["manifest"], "verified": inspect(root, output["manifest"]),
            "deduplicated": output == produce(root, value), "formats": [a["mime"] for a in output["assets"]]}
