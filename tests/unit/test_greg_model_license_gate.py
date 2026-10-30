"""The license of a model's weights where Ollama 0.40 and later keep it, and the selection gate built on it.

Ollama 0.40 (tag v0.40.0, 2026-10-06; main 4d22e65, 2026-10-29) no longer writes a pulled model's manifest at
``manifests/<host>/<namespace>/<model>/<tag>``, the only place ``licensing.ollama_model`` read on 3358d660. It stores
the manifest as a blob and names it by a relative link at ``manifests-v2/<host>/<namespace>/<model>/<tag>``, the
default registry spelled ``ollama.com`` and a host's ":" written "%3A" (manifest/paths.go; manifest/manifest.go
writeManifestData, linkManifest), and the name may be a manifest list with one child manifest per runner, of which
a pull fetches the one its runner selects (server/images.go PullModel, pullSelectedManifest). On 3358d660 every
model pulled that way was unassessed, so a gate that holds unassessed models would hold all of them.

``licensing.admit_model_selection`` is the selection gate the body and the console can call before a route is built:
a held, missing or unreadable model leaves the founder's order with the reason; a cleared one carries its evidence.

The layouts below are written from Ollama's source, not read from a live Ollama store: none exists on this body.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from greg import licensing

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "licenses"
APACHE = (FIXTURES / "Apache-2.0.txt").read_text()
LLAMA = "LLAMA 3.1 COMMUNITY LICENSE AGREEMENT\nLlama 3.1 Version Release Date: July 23, 2024\n"
DOCKER_V2 = "application/vnd.docker.distribution.manifest.v2+json"
MANIFEST_LIST = "application/vnd.ollama.manifest.list.v2+json"      # manifest/manifest.go MediaTypeManifestList


def blob(root: Path, data: bytes) -> str:
    (root / "blobs").mkdir(parents=True, exist_ok=True)
    digest = "sha256:" + hashlib.sha256(data).hexdigest()
    (root / "blobs" / digest.replace(":", "-")).write_bytes(data)
    return digest


def manifest(root: Path, licenses, weights: bytes = b"GGUF weights") -> bytes:
    """A model manifest whose weight and license layers are blobs of ``root``."""
    layers = [{"mediaType": "application/vnd.ollama.image.model", "digest": blob(root, weights), "size": len(weights)}]
    layers += [{"mediaType": licensing.OLLAMA_LICENSE, "digest": blob(root, t.encode()), "size": len(t)}
               for t in licenses]
    return json.dumps({"schemaVersion": 2, "mediaType": DOCKER_V2, "layers": layers}).encode()


def link(root: Path, raw: bytes, *where: str) -> str:
    """Store ``raw`` as Ollama 0.40 does: a blob, named by a relative link at manifests-v2/<where>."""
    digest = blob(root, raw)
    named = root / "manifests-v2" / Path(*(where or ("ollama.com", "library", "qwen3.5", "4b")))
    named.parent.mkdir(parents=True, exist_ok=True)
    named.symlink_to(os.path.relpath(root / "blobs" / digest.replace(":", "-"), named.parent))
    return digest


def legacy(root: Path, raw: bytes, *where: str) -> None:
    """Store ``raw`` as Ollama 0.35 does, at manifests/<where>."""
    path = root / "manifests" / Path(*(where or ("registry.ollama.ai", "library", "qwen3.5", "4b")))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


def listing(root: Path, *children: str) -> bytes:
    return json.dumps({"schemaVersion": 2, "mediaType": MANIFEST_LIST,
                       "manifests": [{"mediaType": DOCKER_V2, "digest": d, "runner": r}
                                     for d, r in zip(children, ("llamacpp", "mlx", "ggml"))]}).encode()


def weights_of(raw: bytes) -> list:
    return [layer["digest"] for layer in json.loads(raw)["layers"]
            if layer["mediaType"] == "application/vnd.ollama.image.model"]


# -- the store Ollama 0.40 writes -------------------------------------------------------------------------------

def test_g9_a_model_pulled_by_ollama_0_40_is_read_where_ollama_writes_it(tmp_path):
    root = tmp_path / "models"
    raw = manifest(root, (LLAMA,))
    digest = link(root, raw, "ollama.com", "library", "llama3.1", "8b")
    a = licensing.ollama_model("llama3.1:8b", root)
    assert a is not None, "a model linked in manifests-v2 is unassessed"
    assert a["verdict"] == "FOUNDER_REVIEW" and a["held"] and "llama-3.1" in a["reason"], a["reason"]
    assert a["subject"]["manifest_sha256"] == digest.split(":")[1]


def test_an_apache_licensed_model_in_the_v2_layout_is_cleared_and_bound_to_its_manifest_digest(tmp_path):
    root = tmp_path / "models"
    raw = manifest(root, (APACHE,))
    digest = link(root, raw)
    assert not (root / "manifests").exists()          # Ollama removes the legacy name after writing the v2 one
    a = licensing.ollama_model("qwen3.5:4b", root)
    assert a is not None and a["verdict"] == "CLEARED" and not a["held"], a and a["reason"]
    assert a["subject"] == {"model": "registry.ollama.ai/library/qwen3.5:4b",
                            "manifest_sha256": digest.split(":")[1], "weights": weights_of(raw)}


def test_a_registry_host_with_a_port_is_filed_as_ollama_escapes_it(tmp_path):
    """manifest/paths.go encodeV2ManifestHost: strings.ReplaceAll(host, ":", "%3A"), in v0.40.0 and main."""
    assert licensing._ollama_parts("localhost:5000/team/coder:7b") == ("localhost:5000", "team", "coder", "7b")
    for bad in ("localhost:5000/coder", "a:b/team/coder", "localhost:/team/coder"):
        assert licensing._ollama_parts(bad) is None, bad
    root = tmp_path / "models"
    link(root, manifest(root, (APACHE,)), "localhost%3A5000", "team", "coder", "7b")
    a = licensing.ollama_model("localhost:5000/team/coder:7b", root)
    assert a is not None and a["verdict"] == "CLEARED", a


def test_the_legacy_tree_is_read_under_either_spelling_of_the_default_registry(tmp_path):
    """manifest/paths.go legacyNameCandidates; a dangling v2 link falls back to it, as resolveManifestPath does."""
    root = tmp_path / "a"
    legacy(root, manifest(root, (APACHE,)), "ollama.com", "library", "qwen3.5", "4b")
    assert licensing.ollama_model("qwen3.5:4b", root)["verdict"] == "CLEARED"
    root = tmp_path / "b"
    legacy(root, manifest(root, (APACHE,)))
    assert licensing.ollama_model("ollama.com/library/qwen3.5:4b", root)["verdict"] == "CLEARED"
    dangling = root / "manifests-v2" / "ollama.com" / "library" / "qwen3.5" / "4b"
    dangling.parent.mkdir(parents=True)
    dangling.symlink_to("../../../../blobs/sha256-" + "1" * 64)
    assert licensing.ollama_model("qwen3.5:4b", root)["verdict"] == "CLEARED"


def test_g10_a_v2_link_out_of_the_store_or_to_a_blob_of_another_name_is_not_read(tmp_path):
    """Ollama serves a manifests-v2 link only when it resolves to the blob of this store its file name names, with
    bytes that hash to that name (manifest.go openManifestFileLocked). A link that does not is not read, and the
    legacy manifest a downgrade anchor may leave beside it is not read in its place: Ollama would not serve it."""
    root = tmp_path / "models"
    raw = manifest(root, (APACHE,))
    legacy(root, raw)
    named = root / "manifests-v2" / "ollama.com" / "library" / "qwen3.5" / "4b"
    real = root / "blobs" / blob(root, raw).replace(":", "-")
    outside = tmp_path / "elsewhere" / real.name
    outside.parent.mkdir()
    outside.write_bytes(raw)
    named.parent.mkdir(parents=True)
    named.symlink_to(outside)
    a = licensing.ollama_model("qwen3.5:4b", root)
    assert a is not None and a["held"] and "manifests-v2 link" in a["reason"], a and a["reason"]
    wrong = root / "blobs" / ("sha256-" + "0" * 64)
    wrong.write_bytes(raw)
    named.unlink()
    named.symlink_to(os.path.relpath(wrong, named.parent))
    a = licensing.ollama_model("qwen3.5:4b", root)
    assert a is not None and a["held"] and "manifests-v2 link" in a["reason"], a and a["reason"]


# -- manifest lists ---------------------------------------------------------------------------------------------

def test_g11_every_manifest_of_a_manifest_list_is_read_and_one_held_runner_holds_the_model(tmp_path):
    root = tmp_path / "models"
    clean, held = manifest(root, (APACHE,)), manifest(root, (LLAMA,), weights=b"MLX weights")
    digest = link(root, listing(root, blob(root, clean), blob(root, held)))
    a = licensing.ollama_model("qwen3.5:4b", root)
    assert a is not None and a["held"] and "llama-3.1" in a["reason"], a and a["reason"]
    assert a["subject"]["manifest_sha256"] == digest.split(":")[1]
    assert a["subject"]["weights"] == sorted(weights_of(clean) + weights_of(held))


def test_a_runner_manifest_ollama_never_pulled_here_is_named_not_read(tmp_path):
    """A pull fetches the child its runner selects; another child's blob is not in the store, Ollama never selects
    it (manifest.go selectManifestWithPreferences), and none of its weights can run here."""
    root = tmp_path / "models"
    clean = manifest(root, (APACHE,))
    elsewhere = "sha256:" + "2" * 64
    digest = link(root, listing(root, blob(root, clean), elsewhere))
    a = licensing.ollama_model("qwen3.5:4b", root)
    assert a is not None and a["verdict"] == "CLEARED", a and a["reason"]
    assert a["subject"]["manifest_sha256"] == digest.split(":")[1] and a["subject"]["weights"] == weights_of(clean)
    assert any(elsewhere in u for u in a["uncertainty"]), a["uncertainty"]
    root = tmp_path / "none"
    link(root, listing(root, elsewhere))
    a = licensing.ollama_model("qwen3.5:4b", root)
    assert a["held"] and "nothing of it can run here" in a["reason"], a["reason"]


def test_a_runner_manifest_in_the_store_that_does_not_match_its_digest_holds_the_model(tmp_path):
    root = tmp_path / "models"
    clean, held = manifest(root, (APACHE,)), manifest(root, (LLAMA,), weights=b"MLX weights")
    tampered = blob(root, held)
    (root / "blobs" / tampered.replace(":", "-")).write_bytes(clean)
    link(root, listing(root, blob(root, clean), tampered))
    a = licensing.ollama_model("qwen3.5:4b", root)
    assert a is not None and a["held"] and "not a readable Ollama manifest" in a["reason"], a and a["reason"]


def test_a_list_entry_that_carries_its_own_manifest_is_not_read_as_a_reference(tmp_path):
    """Ollama runs an entry with layers of its own as written, not the blob its digest names (manifest.go
    isReference); no Ollama writer produces one, so it holds the model."""
    root = tmp_path / "models"
    clean, held = manifest(root, (APACHE,)), manifest(root, (LLAMA,), weights=b"MLX weights")
    entry = {"mediaType": DOCKER_V2, "digest": blob(root, clean), "runner": "llamacpp",
             "layers": json.loads(held)["layers"]}
    link(root, json.dumps({"schemaVersion": 2, "mediaType": MANIFEST_LIST,
                           "manifests": [entry]}).encode())
    a = licensing.ollama_model("qwen3.5:4b", root)
    assert a is not None and a["held"] and "not a readable Ollama manifest" in a["reason"], a and a["reason"]


def test_a_deeply_nested_manifest_is_held_not_raised(tmp_path):
    """On 3358d660 json.loads raised RecursionError out of ollama_model for a manifest nested 100,000 deep."""
    root = tmp_path / "models"
    legacy(root, b'{"layers": ' + b"[" * 100_000 + b"]" * 100_000 + b"}")
    a = licensing.ollama_model("qwen3.5:4b", root)
    assert a["held"] and "not a readable Ollama manifest" in a["reason"], a["reason"]


# -- the selection gate -----------------------------------------------------------------------------------------

def two_models(root: Path) -> Path:
    legacy(root, manifest(root, (LLAMA,), weights=b"llama weights"), "registry.ollama.ai", "library", "llama3.1", "8b")
    link(root, manifest(root, (APACHE,)))
    return root


def test_g13_a_held_selection_keeps_the_founders_other_routes_and_says_why(tmp_path):
    root = two_models(tmp_path / "models")
    held = licensing.admit_model_selection({"order": ["ollama", "anthropic"], "ollama_model": "llama3.1:8b"}, root)
    a = licensing.ollama_model("llama3.1:8b", root)
    q = licensing.qualify_use([a], licensing.GREG_USE, a["subject"])
    assert held == {"order": ["anthropic"], "model_license_hold": {
        "model": "llama3.1:8b", "verdict": "FOUNDER_REVIEW", "reason": a["reason"],
        "manifest_sha256": a["subject"]["manifest_sha256"], "assessment_digest": q["assessment_digest"]}}, held
    assert "llama-3.1" in held["model_license_hold"]["reason"]
    assert licensing.admit_model_selection({"order": ["anthropic"]}, root) == {"order": ["anthropic"]}
    assert licensing.admit_model_selection(None, root) is None


def test_a_cleared_selection_carries_its_license_evidence(tmp_path):
    root = two_models(tmp_path / "models")
    cleared = licensing.admit_model_selection({"order": ["ollama"], "ollama_model": "qwen3.5:4b"}, root)
    a = licensing.ollama_model("qwen3.5:4b", root)
    q = licensing.qualify_use([a], licensing.GREG_USE, a["subject"])
    assert cleared == {"order": ["ollama"], "ollama_model": "qwen3.5:4b", "license_evidence": {
        "model": "registry.ollama.ai/library/qwen3.5:4b", "manifest_sha256": a["subject"]["manifest_sha256"],
        "weights": a["subject"]["weights"], "verdict": "CLEARED", "assessment_digest": q["assessment_digest"],
        "use_digest": q["use_digest"]}}, cleared


def test_a_model_in_no_readable_store_is_held_and_the_store_never_takes_the_selection_down(tmp_path, monkeypatch):
    root = two_models(tmp_path / "models")
    for selection in ({"order": ["ollama", "openai"], "ollama_model": "absent:1b"}, {"order": ["ollama", "openai"]}):
        held = licensing.admit_model_selection(selection, root)
        assert held["order"] == ["openai"] and "ollama_model" not in held, held
        assert held["model_license_hold"]["verdict"] == "UNASSESSED" and "in no Ollama store" in \
            held["model_license_hold"]["reason"], held

    def unreadable(model, models_dir=None):
        raise PermissionError(13, "Permission denied", "/usr/share/ollama/.ollama/models")
    monkeypatch.setattr(licensing, "ollama_model", unreadable)
    held = licensing.admit_model_selection({"order": ["ollama"], "ollama_model": "qwen3.5:4b"}, root)
    assert held == {"order": [], "model_license_hold": {
        "model": "qwen3.5:4b", "verdict": "UNASSESSED",
        "reason": "the Ollama store could not be read (PermissionError)", "manifest_sha256": None,
        "assessment_digest": None}}, held


def test_evidence_from_an_earlier_admission_never_rides_on_a_hold(tmp_path):
    """Re-pulled under the same name with Llama terms: a selection admitted before carries no evidence after."""
    root = two_models(tmp_path / "models")
    cleared = licensing.admit_model_selection({"order": ["ollama"], "ollama_model": "qwen3.5:4b"}, root)
    assert "license_evidence" in cleared
    named = root / "manifests-v2" / "ollama.com" / "library" / "qwen3.5" / "4b"
    named.unlink()
    link(root, manifest(root, (LLAMA,), weights=b"re-pulled weights"))
    held = licensing.admit_model_selection(cleared, root)
    assert set(held) == {"order", "model_license_hold"} and held["order"] == [], held
