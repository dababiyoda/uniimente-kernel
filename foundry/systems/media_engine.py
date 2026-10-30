"""#35 Media engine: image, audio, video and interactive assets rendered from the canon, content-addressed with
signed provenance, and verified by decoding what was produced.

  canon       the only inputs a render takes are the canon (palette, mark, voice, disclosure text, editorial rules
              from the media company charter in foundry/company.py and the DALEOBANKS persona) and a brief; the
              canon hash and the brief hash are ingredients of every asset, so an asset can always be traced to
              the rules it was made under
  engines     adopted, not rebuilt: Pillow draws frames and stills; FFmpeg (libx264, gif, wav, mp4 muxers from the
              imageio-ffmpeg static build) encodes video; audio is synthesized as 16-bit PCM from the brief's
              notes; the interactive asset is a self-contained HTML/SVG document with no external resources
  disclosure  the editorial constitution's synthetic-identity rule is enforced, not advised: an engine refuses a
              canon without the rule or the text, visual assets carry the disclosure in-frame, the interactive
              asset shows it, every manifest asserts it, and a brief that asks to omit it is refused
  provenance  each asset is stored by content (#36) with a C2PA-shaped manifest: claim generator, engine versions,
              ingredients (canon, brief), assertions (disclosure, dimensions, duration, frames), the asset's hash,
              and the engine's Ed25519 signature; verify() recomputes the hash and checks the signature
  verification the engine does not trust its own encoder: a video is decoded back and its frame count, resolution
              and a sampled pixel are checked; audio is re-read for duration and peak; an image is re-opened

Remotion and Godot remain the adopted routes for programmatic motion design and interactive worlds beyond this;
nothing here contacts a network.
"""
from __future__ import annotations

import html
import io
import json
import math
import struct
import subprocess
import wave
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from foundry.company import REQUIRED_EDITORIAL_RULES
from foundry.systems import cas
from provenance.digests import compact_json_bytes as _canon, sha256_tagged as _sha

SAMPLE_RATE = 22050
KINDS = ("image", "audio", "video", "interactive")
MEDIA_TYPES = {"image": "image/png", "audio": "audio/wav", "video": "video/mp4", "interactive": "text/html"}
CLAIM_GENERATOR = "uniimente-foundry-media/1"
NOTE_HZ = {"C4": 261.63, "D4": 293.66, "E4": 329.63, "F4": 349.23, "G4": 392.0, "A4": 440.0, "B4": 493.88, "C5": 523.25, "rest": 0.0}


class MediaError(ValueError):
    pass


def _rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def ffmpeg_exe() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def engine_versions() -> dict:
    import PIL
    out = subprocess.run([ffmpeg_exe(), "-version"], capture_output=True, text=True).stdout.splitlines()[0]
    return {"pillow": PIL.__version__, "ffmpeg": out.split(" Copyright")[0]}


class Engine:
    def __init__(self, root: Path, *, key_seed: bytes, canon: dict, clock):
        from greg.founder import public_bytes
        self.root, self.clock = Path(root), clock
        self.root.mkdir(parents=True, exist_ok=True)
        problems = []
        for key in ("name", "palette", "mark", "voice", "disclosure", "editorial_rules"):
            if not canon.get(key):
                problems.append(f"canon missing {key}")
        if "synthetic_identity_disclosed" not in canon.get("editorial_rules", []):
            problems.append("editorial constitution lacks synthetic_identity_disclosed; the engine will not render under it")
        missing = sorted(set(REQUIRED_EDITORIAL_RULES) - set(canon.get("editorial_rules", [])))
        if missing:
            problems.append(f"editorial constitution missing required rules {missing}")
        for c in ("bg", "fg", "accent"):
            if c not in canon.get("palette", {}):
                problems.append(f"palette missing {c}")
        if problems:
            raise MediaError("; ".join(problems))
        self.canon = canon
        self.canon_hash = _sha(_canon(canon))
        self.key = Ed25519PrivateKey.from_private_bytes(key_seed)
        self.public_key = public_bytes(self.key.public_key()).hex()
        self.versions = engine_versions()

    # -- renderers -------------------------------------------------------------------------------
    def _frame(self, title: str, lines: list[str], size: tuple[int, int], *, progress: float = 1.0):
        from PIL import Image, ImageDraw, ImageFont
        pal = self.canon["palette"]
        w, h = size
        img = Image.new("RGB", (w, h), _rgb(pal["bg"]))
        d = ImageDraw.Draw(img)
        font = ImageFont.load_default()
        d.rectangle([0, 0, w - 1, max(2, h // 24)], fill=_rgb(pal["accent"]))                  # canon mark bar
        d.text((w // 20, h // 10), f"{self.canon['mark']} · {title}", fill=_rgb(pal["fg"]), font=font)
        shown = lines[: max(0, int(round(progress * len(lines))))]
        for i, line in enumerate(shown):
            d.text((w // 20, h // 10 + (i + 2) * max(12, h // 14)), line, fill=_rgb(pal["fg"]), font=font)
        d.rectangle([w // 20, h - h // 8, w // 20 + int((w - w // 10) * progress), h - h // 8 + 3], fill=_rgb(pal["accent"]))
        d.text((w // 20, h - h // 14), self.canon["disclosure"], fill=_rgb(pal["accent"]), font=font)   # in-frame disclosure
        return img

    def render_image(self, brief: dict) -> bytes:
        img = self._frame(brief["title"], list(brief.get("lines", [])), tuple(brief.get("size", (640, 360))))
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=False)
        return buf.getvalue()

    def render_audio(self, brief: dict) -> bytes:
        notes, bpm = brief.get("notes") or ["C4", "E4", "G4"], int(brief.get("bpm", 90))
        unknown = sorted(set(notes) - set(NOTE_HZ))
        if unknown:
            raise MediaError(f"unknown notes {unknown}")
        beat = 60.0 / bpm
        frames = bytearray()
        for note in notes:
            hz, n = NOTE_HZ[note], int(SAMPLE_RATE * beat)
            for i in range(n):
                env = min(1.0, i / (SAMPLE_RATE * 0.01), (n - i) / (SAMPLE_RATE * 0.05))        # click-free attack and release
                sample = 0.0 if hz == 0 else 0.6 * env * math.sin(2 * math.pi * hz * i / SAMPLE_RATE)
                frames += struct.pack("<h", int(round(sample * 32767)))
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SAMPLE_RATE)
            wf.writeframes(bytes(frames))
        return buf.getvalue()

    def render_video(self, brief: dict) -> bytes:
        size, fps, seconds = tuple(brief.get("size", (320, 180))), int(brief.get("fps", 12)), float(brief.get("seconds", 3))
        if size[0] % 2 or size[1] % 2:
            raise MediaError("video dimensions must be even for yuv420p")
        total = int(round(fps * seconds))
        lines = list(brief.get("lines", []))
        raw = b"".join(self._frame(brief["title"], lines, size, progress=(i + 1) / total).tobytes() for i in range(total))
        work = self.root / "work"
        work.mkdir(exist_ok=True)
        audio = work / "track.wav"
        audio.write_bytes(self.render_audio({"notes": brief.get("notes") or ["C4", "E4", "G4", "C5"], "bpm": int(60 * len(brief.get("notes") or [1] * 4) / seconds)}))
        out = work / "out.mp4"
        argv = [ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{size[0]}x{size[1]}",
                "-r", str(fps), "-i", "pipe:0", "-i", str(audio), "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-pix_fmt", "yuv420p", "-threads", "1", "-c:a", "aac", "-b:a", "96k", "-fflags", "+bitexact", "-flags", "+bitexact",
                "-map_metadata", "-1", "-movflags", "+faststart", str(out)]
        proc = subprocess.run(argv, input=raw, capture_output=True, timeout=120)
        if proc.returncode:
            raise MediaError(f"ffmpeg failed: {proc.stderr.decode(errors='replace')[-300:]}")
        return out.read_bytes()

    def render_interactive(self, brief: dict) -> str:
        pal = self.canon["palette"]
        lines = "".join(f'<li data-step="{i}" hidden>{html.escape(line)}</li>' for i, line in enumerate(brief.get("lines", [])))
        return (f"<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><title>{html.escape(brief['title'])}</title>"
                f"<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'\">"
                f"<style>body{{background:{pal['bg']};color:{pal['fg']};font:16px/1.5 system-ui;margin:0;padding:2rem}}"
                f"h1 span{{color:{pal['accent']}}}button{{background:{pal['accent']};border:0;padding:.5rem 1rem;color:{pal['bg']}}}"
                f"footer{{color:{pal['accent']};margin-top:2rem;font-size:.85rem}}</style></head><body>"
                f"<h1><span>{html.escape(self.canon['mark'])}</span> · {html.escape(brief['title'])}</h1>"
                f"<svg width=\"120\" height=\"12\" role=\"img\" aria-label=\"canon mark\"><rect width=\"120\" height=\"12\" fill=\"{pal['accent']}\"/></svg>"
                f"<ol id=\"steps\">{lines}</ol><button id=\"next\">Reveal next</button>"
                f"<footer>{html.escape(self.canon['disclosure'])}</footer>"
                "<script>var i=0,s=document.querySelectorAll('#steps li');document.getElementById('next').onclick=function(){"
                "if(i<s.length){s[i].hidden=false;i++;}if(i>=s.length){this.disabled=true;}};</script></body></html>")

    # -- produce, store, prove -------------------------------------------------------------------
    def produce(self, kind: str, brief: dict) -> dict:
        if kind not in KINDS:
            raise MediaError(f"kind must be one of {KINDS}")
        if not brief.get("title"):
            raise MediaError("a brief names its title")
        if brief.get("disclosure") is False:
            raise MediaError("the synthetic-identity disclosure is not optional in any asset")
        render = {"image": self.render_image, "audio": self.render_audio, "video": self.render_video, "interactive": self.render_interactive}[kind]
        data = render(brief)
        data = data.encode() if isinstance(data, str) else data
        address = cas.put(self.root / "cas", data)
        checks = self.inspect(kind, data)
        manifest = {"claim_generator": CLAIM_GENERATOR, "engines": self.versions, "kind": kind, "created_at": self.clock(),
                    "asset": {"hash": address, "media_type": MEDIA_TYPES[kind], "bytes": len(data)},
                    "ingredients": [{"role": "canon", "hash": self.canon_hash, "name": self.canon["name"]}, {"role": "brief", "hash": _sha(_canon(brief))}],
                    "assertions": {"synthetic_identity_disclosed": True, "disclosure_text": self.canon["disclosure"],
                                   "editorial_rules": sorted(self.canon["editorial_rules"]), **checks},
                    "signing_key": self.public_key}
        manifest["signature"] = self.key.sign(_canon({k: v for k, v in manifest.items() if k != "signature"})).hex()
        manifest_address = cas.put(self.root / "cas", _canon(manifest))
        index = self._index()
        index.append({"kind": kind, "asset": address, "manifest": manifest_address, "title": brief["title"]})
        (self.root / "assets.json").write_text(json.dumps(index, indent=1))
        return {"asset": address, "manifest": manifest, "manifest_address": manifest_address}

    def _index(self) -> list:
        p = self.root / "assets.json"
        return json.loads(p.read_text()) if p.exists() else []

    def inspect(self, kind: str, data: bytes) -> dict:
        """Re-open what was produced and report what it actually is."""
        if kind == "image":
            from PIL import Image
            img = Image.open(io.BytesIO(data)); img.load()
            w, h = img.size
            return {"width": w, "height": h, "format": img.format, "bg_pixel": list(img.getpixel((w // 2, h // 2))),
                    "mark_pixel": list(img.getpixel((w // 2, 1)))}
        if kind == "audio":
            with wave.open(io.BytesIO(data)) as wf:
                frames, rate = wf.getnframes(), wf.getframerate()
                pcm = wf.readframes(frames)
            peak = max(abs(v) for v in struct.unpack(f"<{frames}h", pcm)) if frames else 0
            return {"duration_s": round(frames / rate, 3), "sample_rate": rate, "channels": 1, "peak": peak}
        if kind == "video":
            work = self.root / "work"; work.mkdir(exist_ok=True)
            path = work / "inspect.mp4"; path.write_bytes(data)
            info = subprocess.run([ffmpeg_exe(), "-hide_banner", "-i", str(path)], capture_output=True, text=True).stderr
            dims = next((s for s in info.replace(",", " ").split() if "x" in s and s.replace("x", "").isdigit()), "0x0")
            w, h = (int(x) for x in dims.split("x"))
            decoded = subprocess.run([ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-i", str(path), "-map", "0:v:0", "-f", "rawvideo",
                                      "-pix_fmt", "rgb24", "pipe:1"], capture_output=True, timeout=120).stdout
            frames = len(decoded) // (w * h * 3) if w and h else 0
            centre = (h // 2 * w + w // 2) * 3
            return {"width": w, "height": h, "frames": frames, "has_audio": "Audio:" in info, "video_codec": "h264" if "h264" in info else "unknown",
                    "first_frame_centre_pixel": list(decoded[centre:centre + 3]) if decoded else []}
        text = data.decode()
        return {"self_contained": "http://" not in text and "https://" not in text, "has_disclosure": html.escape(self.canon["disclosure"]) in text,
                "interactive_steps": text.count("data-step=")}

    @staticmethod
    def verify(data: bytes, manifest: dict) -> dict:
        body = {k: v for k, v in manifest.items() if k != "signature"}
        try:
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(manifest["signing_key"])).verify(bytes.fromhex(manifest["signature"]), _canon(body))
            signed = True
        except (InvalidSignature, ValueError, KeyError):
            signed = False
        return {"hash_matches": _sha(data) == manifest.get("asset", {}).get("hash"), "signature_ok": signed,
                "disclosed": bool(manifest.get("assertions", {}).get("synthetic_identity_disclosed"))}


def canon_from_persona(persona: dict, *, palette: dict, mark: str, editorial_rules: list[str]) -> dict:
    """The DALEOBANKS persona (beliefs, doctrine, tone) becomes the voice of a visual canon."""
    return {"name": persona.get("handle", "persona"), "palette": palette, "mark": mark,
            "voice": {"beliefs": persona.get("beliefs", [])[:3], "doctrine": persona.get("doctrine", []), "mission": persona.get("mission", "")},
            "disclosure": "Synthetic identity: machine-authored under a human legal operator.", "editorial_rules": list(editorial_rules)}


def _store(root: Path) -> list:
    p = Path(root) / "engine" / "assets.json"
    return json.loads(p.read_text()) if p.exists() else []


QUERY_OPS = {"assets": lambda a, r: {"assets": _store(r)},
             "manifest": lambda a, r: {"manifest": json.loads(cas.get(Path(r) / "engine" / "cas", a["manifest"]))},
             "verify": lambda a, r: Engine.verify(cas.get(Path(r) / "engine" / "cas", a["asset"]), json.loads(cas.get(Path(r) / "engine" / "cas", a["manifest"])))}
APPLY_OPS: dict = {}      # rendering is an operator act under a ratified canon; publishing an asset is a separate gated act


def demo_persona() -> dict:
    return {"handle": "DaLeoBanks", "mission": "Provoke thought, challenge systemic issues, and inspire critical thinking while remaining kind.",
            "beliefs": ["Everything should be treated situationally.", "All systems are flawed; solutions must be tailored.",
                        "Ethics evolve and must be balanced with speed and innovation, provided no harm is done."],
            "doctrine": ["Challenge", "Analyze", "Propose", "Inspire"]}


def exercise(root) -> dict:
    root = Path(root)
    palette = {"bg": "#0b1f3a", "fg": "#f5f1e8", "accent": "#e3a72f"}
    canon = canon_from_persona(demo_persona(), palette=palette, mark="GREG", editorial_rules=list(REQUIRED_EDITORIAL_RULES))
    refusals = {}

    def refused(label, fn):
        try:
            fn()
            refusals[label] = None
        except MediaError as exc:
            refusals[label] = str(exc)[:80]
    undisclosed = dict(canon, editorial_rules=[r for r in REQUIRED_EDITORIAL_RULES if r != "synthetic_identity_disclosed"])
    refused("canon_without_disclosure_rule", lambda: Engine(root / "bad", key_seed=bytes(32 * [71]), canon=undisclosed, clock=lambda: "t"))
    refused("canon_without_palette", lambda: Engine(root / "bad2", key_seed=bytes(32 * [71]), canon=dict(canon, palette={}), clock=lambda: "t"))
    engine = Engine(root / "engine", key_seed=bytes(32 * [71]), canon=canon, clock=lambda: "2026-10-13T16:00:00Z")
    brief = {"title": "Why receipts beat promises", "lines": ["A claim is a claim.", "A receipt is a hash you can check.", "Pay on the receipt."]}
    image = engine.produce("image", {**brief, "size": (640, 360)})
    audio = engine.produce("audio", {"title": "Sting", "notes": ["C4", "E4", "G4", "C5", "rest", "G4"], "bpm": 120})
    video = engine.produce("video", {**brief, "size": (320, 180), "fps": 12, "seconds": 3})
    page = engine.produce("interactive", brief)
    refused("brief_without_title", lambda: engine.produce("image", {"lines": ["x"]}))
    refused("brief_omitting_disclosure", lambda: engine.produce("image", {**brief, "disclosure": False}))
    refused("unknown_kind", lambda: engine.produce("hologram", brief))
    refused("unknown_note", lambda: engine.produce("audio", {"title": "x", "notes": ["H9"]}))
    refused("odd_video_dimensions", lambda: engine.produce("video", {**brief, "size": (321, 181), "seconds": 1}))
    data = cas.get(root / "engine" / "cas", image["asset"])
    tampered_manifest = json.loads(json.dumps(image["manifest"])); tampered_manifest["assertions"]["synthetic_identity_disclosed"] = False
    return {"image": {k: image["manifest"]["assertions"][k] for k in ("width", "height", "format", "bg_pixel", "mark_pixel")},
            "image_bg_is_canon_bg": image["manifest"]["assertions"]["bg_pixel"] == list(_rgb(palette["bg"])),
            "image_mark_is_canon_accent": image["manifest"]["assertions"]["mark_pixel"] == list(_rgb(palette["accent"])),
            "audio": {k: audio["manifest"]["assertions"][k] for k in ("duration_s", "sample_rate", "channels", "peak")},
            "video": {k: video["manifest"]["assertions"][k] for k in ("width", "height", "frames", "has_audio", "video_codec")},
            "video_first_frame_near_canon_bg": all(abs(a - b) <= 12 for a, b in zip(video["manifest"]["assertions"]["first_frame_centre_pixel"], _rgb(palette["bg"]))),
            "interactive": {k: page["manifest"]["assertions"][k] for k in ("self_contained", "has_disclosure", "interactive_steps")},
            "interactive_sha256": page["asset"],
            "every_manifest_discloses": all(m["manifest"]["assertions"]["synthetic_identity_disclosed"] for m in (image, audio, video, page)),
            "ingredients_trace_to_canon": all(m["manifest"]["ingredients"][0]["hash"] == engine.canon_hash for m in (image, audio, video, page)),
            "verify_image": Engine.verify(data, image["manifest"]),
            "verify_substituted_bytes": Engine.verify(data + b"\x00", image["manifest"]),
            "verify_tampered_manifest": Engine.verify(data, tampered_manifest),
            "assets_indexed": len(engine._index()), "refusals": refusals}
