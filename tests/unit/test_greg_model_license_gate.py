"""The license of a model's weights where Ollama 0.40 and later keep it, and the selection gate built on it.

Ollama 0.40 (tag v0.40.0, 2026-10-06; main 4d22e65, 2026-10-29) no longer writes a pulled model's manifest at
``manifests/<host>/<namespace>/<model>/<tag>``, the only place ``licensing.ollama_model`` read on 3358d660. It stores
the manifest as a blob and names it by a relative link at ``manifests-v2/<host>/<namespace>/<model>/<tag>``, the
default registry spelled ``ollama.com`` and a host's ":" written "%3A" (manifest/paths.go; manifest/manifest.go
writeManifestData, linkManifest), and the name may be a manifest list with one child manifest per runner, of which
a pull fetches the one its runner selects (server/images.go PullModel, pullSelectedManifest). A pull also writes a
legacy "downgrade anchor" at the old path, a regular file holding the pulled manifest plus a layer naming it
(server/images.go writePullDowngradeAnchor; manifest.go WriteLegacyAnchor), so 3358d660's reader read the anchor:
the same licenses, bound to the anchor's digest instead of the manifest Ollama serves. A store without an anchor
(after ``ollama cp``, server/images.go CopyModel, or a failed best-effort write) was unassessed, and a legacy
manifest that differs from the v2 one (an older Ollama pulling after a downgrade) was read in place of the one
Ollama 0.40 serves.

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


def anchor(root: Path, raw: bytes, *where: str) -> Path:
    """The legacy manifest a v0.40.0 or main pull writes beside the v2 link: the pulled manifest with one more layer
    naming it (manifest.go WriteLegacyAnchor, at the logical name's registry.ollama.ai path)."""
    document = json.loads(raw)
    document["layers"].append({"mediaType": DOCKER_V2, "digest": "sha256:" + hashlib.sha256(raw).hexdigest(),
                               "size": len(raw)})
    path = root / "manifests" / Path(*(where or ("registry.ollama.ai", "library", "qwen3.5", "4b")))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(document).encode())
    return path


def pull(root: Path, raw: bytes) -> str:
    """What ``ollama pull qwen3.5:4b`` leaves in the store: the v2 link and the downgrade anchor."""
    digest = link(root, raw)
    anchor(root, raw)
    return digest


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
    """The manifest Ollama serves is the v2 one; the anchor beside it carries another digest."""
    root = tmp_path / "models"
    raw = manifest(root, (APACHE,))
    digest = pull(root, raw)
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


def test_a_legacy_manifest_that_differs_from_the_v2_one_is_not_read(tmp_path):
    """A legacy manifest (Apache) beside a different v2 manifest (Llama), as an older Ollama leaves one when it
    pulls after a downgrade: Ollama 0.40 serves v2."""
    root = tmp_path / "models"
    anchor(root, manifest(root, (APACHE,), weights=b"earlier weights"))
    digest = link(root, manifest(root, (LLAMA,), weights=b"later weights"))
    a = licensing.ollama_model("qwen3.5:4b", root)
    assert a is not None and a["held"] and "llama-3.1" in a["reason"], a and a["reason"]
    assert a["subject"]["manifest_sha256"] == digest.split(":")[1]


def test_a_v2_copy_is_read_as_the_manifest(tmp_path):
    """Where it cannot link, Ollama copies the manifest blob to the v2 path (manifest.go linkManifest,
    copyManifestFile) and opens the copy as it is (openManifestFileLocked)."""
    root = tmp_path / "models"
    raw = manifest(root, (APACHE,))
    named = root / "manifests-v2" / "ollama.com" / "library" / "qwen3.5" / "4b"
    named.parent.mkdir(parents=True)
    named.write_bytes(raw)
    a = licensing.ollama_model("qwen3.5:4b", root)
    assert a is not None and a["verdict"] == "CLEARED", a and a["reason"]
    assert a["subject"]["manifest_sha256"] == hashlib.sha256(raw).hexdigest()


def test_the_legacy_tree_is_read_under_either_spelling_of_the_default_registry(tmp_path):
    """manifest/paths.go legacyNameCandidates. A dangling v2 link holds the model: main reads the v2 entry and fails
    to load (manifest.go FindNamedManifestForRunner), v0.40.0 falls back to the legacy manifest (resolveManifestPath),
    and GREG cannot tell which of them is running."""
    root = tmp_path / "a"
    legacy(root, manifest(root, (APACHE,)), "ollama.com", "library", "qwen3.5", "4b")
    assert licensing.ollama_model("qwen3.5:4b", root)["verdict"] == "CLEARED"
    root = tmp_path / "b"
    legacy(root, manifest(root, (APACHE,)))
    assert licensing.ollama_model("registry.ollama.ai/library/qwen3.5:4b", root)["verdict"] == "CLEARED"
    dangling = root / "manifests-v2" / "ollama.com" / "library" / "qwen3.5" / "4b"
    dangling.parent.mkdir(parents=True)
    dangling.symlink_to("../../../../blobs/sha256-" + "1" * 64)
    a = licensing.ollama_model("qwen3.5:4b", root)
    assert a["held"] and "manifests-v2 link" in a["reason"], a["reason"]


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


def test_a_name_is_matched_to_the_stored_one_ignoring_case_as_ollama_does(tmp_path):
    """Ollama maps a requested name to the stored spelling ignoring case, a v2 entry before a legacy one (manifest.go
    FindName, FindNamedManifestForRunner; routes.go getExistingName). On 4f5ce7e5 "Qwen3.5:4b" missed the v2 link
    and read the lower-cased legacy manifest beside it."""
    root = tmp_path / "models"
    link(root, manifest(root, (LLAMA,), weights=b"new weights"))
    anchor(root, manifest(root, (APACHE,), weights=b"old weights"))
    a = licensing.ollama_model("Qwen3.5:4b", root)
    assert a is not None and a["held"] and "llama-3.1" in a["reason"], a and a["reason"]
    root = tmp_path / "v2only"
    digest = link(root, manifest(root, (APACHE,)))
    (root / "manifests-v2" / "ollama.com" / "library" / "QWEN3.5" / "4b").mkdir(parents=True)   # not a manifest
    for name in ("Qwen3.5:4B", "Registry.Ollama.AI/library/qwen3.5:4b", "REGISTRY.OLLAMA.AI/Library/QWEN3.5:4b"):
        a = licensing.ollama_model(name, root)
        assert a is not None and a["verdict"] == "CLEARED", (name, a and a["reason"])
        assert a["subject"]["manifest_sha256"] == digest.split(":")[1]


def test_a_name_under_the_host_ollama_com_is_held(tmp_path):
    """Ollama main (e9fde36d) names local models registry.ollama.ai and finds none asked for under ollama.com, in any
    case, so it would pull the name from the registry (the frozen oracle: r4b_explicit_ollama_com). v0.40.0 serves the
    local one when the spelling matches; GREG holds both, and the same store clears without a host. On d1724006 every
    one of these cleared."""
    root = tmp_path / "models"
    legacy(root, manifest(root, (APACHE,)))
    link(root, manifest(root, (APACHE,)))
    assert licensing.ollama_model("qwen3.5:4b", root)["verdict"] == "CLEARED"
    for name in ("ollama.com/library/qwen3.5:4b", "OLLAMA.COM/Library/QWEN3.5:4b", "Ollama.Com/library/qwen3.5",
                 "ollama.com/library/absent:1b"):
        a = licensing.ollama_model(name, root)
        assert a["held"] and "under the host ollama.com" in a["reason"], (name, a["reason"])
        assert a["subject"]["manifest_sha256"] is None and a["subject"]["weights"] == [], a["subject"]


def test_two_stored_names_that_differ_only_in_case_hold_the_model(tmp_path):
    """Ollama serves whichever its name index, a Go map, yields first."""
    root = tmp_path / "models"
    legacy(root, manifest(root, (APACHE,)))
    legacy(root, manifest(root, (LLAMA,), weights=b"other"), "registry.ollama.ai", "library", "Qwen3.5", "4b")
    a = licensing.ollama_model("qwen3.5:4b", root)
    assert a is not None and a["held"] and "ignoring case" in a["reason"], a and a["reason"]


def test_a_legacy_link_is_opened_as_ollama_opens_it_and_two_legacy_spellings_hold(tmp_path):
    """Ollama opens a legacy entry that is a link as it opens a v2 one (manifest.go openManifestFileLocked). With both
    spellings of the default registry in the legacy tree, main serves the first of its sorted index (ollama.com) and
    v0.40.0 the registry.ollama.ai one (paths.go resolveManifestPath), so neither is read."""
    root = tmp_path / "models"
    digest = blob(root, manifest(root, (LLAMA,), weights=b"restricted"))
    first = root / "manifests" / "registry.ollama.ai" / "library" / "qwen3.5" / "4b"
    first.parent.mkdir(parents=True)
    first.symlink_to(os.path.relpath(root / "blobs" / digest.replace(":", "-"), first.parent))
    a = licensing.ollama_model("qwen3.5:4b", root)
    assert a is not None and a["held"] and "llama-3.1" in a["reason"], a and a["reason"]
    assert a["subject"]["manifest_sha256"] == digest.split(":")[1]
    legacy(root, manifest(root, (APACHE,), weights=b"open"), "ollama.com", "library", "qwen3.5", "4b")
    a = licensing.ollama_model("qwen3.5:4b", root)
    assert a["held"] and "2 manifests entries" in a["reason"], a["reason"]
    root = tmp_path / "outside"
    (tmp_path / "elsewhere").write_bytes(manifest(root, (APACHE,)))
    first = root / "manifests" / "registry.ollama.ai" / "library" / "qwen3.5" / "4b"
    first.parent.mkdir(parents=True)
    first.symlink_to(tmp_path / "elsewhere")
    a = licensing.ollama_model("qwen3.5:4b", root)
    assert a["held"] and "manifests link" in a["reason"], a["reason"]
    root = tmp_path / "through"                     # a regular file reached out of the tree (pathWithin)
    legacy(tmp_path / "outside-tree", manifest(root, (APACHE,)), "library", "qwen3.5", "4b")
    (root / "manifests" / "registry.ollama.ai").mkdir(parents=True)
    (root / "manifests" / "registry.ollama.ai" / "library").symlink_to(tmp_path / "outside-tree/manifests/library")
    a = licensing.ollama_model("qwen3.5:4b", root)
    assert a["held"] and "lies outside that tree" in a["reason"], a["reason"]


def test_a_v2_entry_where_ollama_0_40_does_not_look_holds_the_model(tmp_path):
    """v0.40.0 looks for a default-registry model under manifests-v2/ollama.com only (canonicalV2Name); main serves
    any entry its index holds. An entry elsewhere, or one under each spelling, could run on one and not the other."""
    root = tmp_path / "models"
    link(root, manifest(root, (APACHE,)), "registry.ollama.ai", "library", "qwen3.5", "4b")
    a = licensing.ollama_model("qwen3.5:4b", root)
    assert a is not None and a["held"] and "not where Ollama 0.40 looks" in a["reason"], a and a["reason"]
    link(root, manifest(root, (APACHE,)))
    a = licensing.ollama_model("qwen3.5:4b", root)
    assert a["held"] and "2 manifests-v2 entries" in a["reason"], a["reason"]
    root = tmp_path / "legacy"
    legacy(root, manifest(root, (APACHE,)), "Registry.Ollama.AI", "library", "qwen3.5", "4b")
    a = licensing.ollama_model("qwen3.5:4b", root)
    assert a["held"] and "manifests entry is not where Ollama 0.40 looks" in a["reason"], a["reason"]
    root = tmp_path / "port"
    link(root, manifest(root, (APACHE,)), "localhost%3a5000", "team", "coder", "7b")
    a = licensing.ollama_model("localhost:5000/team/coder:7b", root)
    assert a["held"] and "not where Ollama 0.40 looks" in a["reason"], a["reason"]


def test_a_name_ollama_reads_as_a_blob_digest_is_held(tmp_path):
    """A name of 12 to 64 hex digits, or sha256-<hex>, is the local manifest blob it names before any model of that
    name (manifest/paths.go resolveManifestPath, ResolveDigestReferenceName), which GREG does not read."""
    root = tmp_path / "models"
    digest = blob(root, manifest(root, (LLAMA,), weights=b"blob weights"))
    prefix = digest[7:19]
    link(root, manifest(root, (APACHE,)), "ollama.com", "library", prefix, "latest")
    for name in (prefix, prefix.upper(), f"{prefix}:latest", "sha256-" + digest[7:], "library/" + prefix):
        a = licensing.ollama_model(name, root)
        assert a is not None and a["held"] and "digest of a local manifest blob" in a["reason"], (name, a)
    link(root, manifest(root, (APACHE,)), "ollama.com", "library", prefix, "4b")
    assert licensing.ollama_model(f"{prefix}:4b", root)["verdict"] == "CLEARED"    # a tag: a model name
    assert not licensing._digest_reference(licensing._ollama_parts(prefix[:11]))
    assert not licensing._digest_reference(licensing._ollama_parts("team/" + prefix))


def test_tensor_and_draft_layers_are_weights_and_a_manifest_without_weights_is_held(tmp_path):
    """manifest/layer.go: a safetensors model is tensor layers, a draft model a draft layer. A manifest with no
    weight layer runs nothing GREG read; on 4f5ce7e5 it was CLEARED with weights=[]."""
    root = tmp_path / "models"
    layers = [{"mediaType": media, "digest": blob(root, data), "size": len(data)} for media, data in (
        ("application/vnd.ollama.image.tensor", b"tensor 1"), ("application/vnd.ollama.image.tensor", b"tensor 2"),
        ("application/vnd.ollama.image.draft", b"draft"),
        (licensing.OLLAMA_LICENSE, APACHE.encode()))]
    link(root, json.dumps({"schemaVersion": 2, "mediaType": DOCKER_V2, "layers": layers}).encode())
    a = licensing.ollama_model("qwen3.5:4b", root)
    assert a["verdict"] == "CLEARED" and a["subject"]["weights"] == sorted(l["digest"] for l in layers[:3]), a
    root = tmp_path / "bare"
    link(root, json.dumps({"schemaVersion": 2, "mediaType": DOCKER_V2, "layers": layers[3:]}).encode())
    a = licensing.ollama_model("qwen3.5:4b", root)
    assert a["held"] and "no weights layer" in a["reason"] and a["subject"]["weights"] == [], a["reason"]


def test_a_relay_to_a_remote_host_is_held(tmp_path):
    """A model whose config names a remote host and model runs there, not here (server/routes.go
    Config.RemoteHost, RemoteModel); its weights and their license are not in this store."""
    root = tmp_path / "models"
    config = json.dumps({"remote_host": "https://ollama.com:443", "remote_model": "gpt-oss:120b"}).encode()
    raw = json.loads(manifest(root, (APACHE,)))
    raw["config"] = {"mediaType": "application/vnd.docker.container.image.v1+json", "digest": blob(root, config),
                     "size": len(config)}
    link(root, json.dumps(raw).encode())
    a = licensing.ollama_model("qwen3.5:4b", root)
    assert a["held"] and "a relay Ollama forwards to https://ollama.com:443" in a["reason"], a["reason"]
    root = tmp_path / "missing"
    raw["layers"] = json.loads(manifest(root, (APACHE,)))["layers"]
    link(root, json.dumps(raw).encode())
    a = licensing.ollama_model("qwen3.5:4b", root)
    assert a["held"] and "config blob is not in this store" in a["reason"], a["reason"]
    local = json.dumps({"model_format": "gguf"}).encode()
    root = tmp_path / "local"
    raw["layers"] = json.loads(manifest(root, (APACHE,)))["layers"]
    raw["config"]["digest"] = blob(root, local)
    link(root, json.dumps(raw).encode())
    assert licensing.ollama_model("qwen3.5:4b", root)["verdict"] == "CLEARED"


# -- manifest lists ---------------------------------------------------------------------------------------------

def test_g11_every_manifest_of_a_manifest_list_is_read_and_one_held_runner_holds_the_model(tmp_path):
    root = tmp_path / "models"
    clean, held = manifest(root, (APACHE,)), manifest(root, (LLAMA,), weights=b"MLX weights")
    digest = link(root, listing(root, blob(root, clean), blob(root, held)))
    a = licensing.ollama_model("qwen3.5:4b", root)
    assert a is not None and a["held"] and "llama-3.1" in a["reason"], a and a["reason"]
    assert a["subject"]["manifest_sha256"] == digest.split(":")[1]
    assert a["subject"]["weights"] == sorted(weights_of(clean) + weights_of(held))


def test_b1_an_unlicensed_child_is_not_hidden_by_a_licensed_sibling(tmp_path):
    """The review of 4f5ce7e5 (blocking): the layers of every child were pooled and assessed once, so the Apache
    license of the mlx child cleared the unlicensed llamacpp child Ollama runs first on Linux (manifest.go
    runnerPreferences). Each child is assessed on its own and any held child holds the model."""
    root = tmp_path / "models"
    licensed, bare = manifest(root, (APACHE,), weights=b"mlx weights"), manifest(root, (), weights=b"llamacpp weights")
    link(root, json.dumps({"schemaVersion": 2, "mediaType": MANIFEST_LIST, "manifests": [
        {"mediaType": DOCKER_V2, "digest": blob(root, bare), "runner": "llamacpp"},
        {"mediaType": DOCKER_V2, "digest": blob(root, licensed), "runner": "mlx"}]}).encode())
    a = licensing.ollama_model("qwen3.5:4b", root)
    assert a is not None and a["held"] and "declares no license" in a["reason"], a and a["reason"]
    assert [(c["manifest_sha256"], c["runners"], c["verdict"]) for c in a["subject"]["children"]] == [
        (hashlib.sha256(bare).hexdigest(), ["llamacpp"], "FOUNDER_REVIEW"),
        (hashlib.sha256(licensed).hexdigest(), ["mlx"], "CLEARED")]
    held = licensing.admit_model_selection({"order": ["ollama"], "ollama_model": "qwen3.5:4b"}, root)
    assert held["order"] == [] and "declares no license" in held["model_license_hold"]["reason"], held


def test_s1_a_cleared_list_carries_each_childs_digest_and_the_one_api_tags_reports(tmp_path):
    """For a manifest list /api/tags reports the digest of the child Ollama selects, not the list's (server/
    model_list.go describeModelRows), and that is the digest greg.models.OllamaRoute reads."""
    root = tmp_path / "models"
    gguf, mlx = manifest(root, (APACHE,), weights=b"gguf"), manifest(root, (APACHE,), weights=b"mlx")
    gguf_d, mlx_d = blob(root, gguf), blob(root, mlx)
    list_digest = link(root, listing(root, gguf_d, mlx_d))
    cleared = licensing.admit_model_selection({"order": ["ollama"], "ollama_model": "qwen3.5:4b"}, root)
    evidence = cleared["license_evidence"]
    assert evidence["manifest_sha256"] == list_digest[7:] and evidence["verdict"] == "CLEARED", evidence
    assert [(c["manifest_sha256"], c["runners"], c["verdict"], c["weights"]) for c in evidence["children"]] == [
        (gguf_d[7:], ["llamacpp"], "CLEARED", weights_of(gguf)), (mlx_d[7:], ["mlx"], "CLEARED", weights_of(mlx))]
    assert evidence["api_tags_digest"] == {"llamacpp>ggml>mlx": gguf_d[7:], "mlx>llamacpp>ggml": mlx_d[7:]}
    root = tmp_path / "mlx-only"                     # the llamacpp child was never pulled: every order runs mlx
    mlx_d = blob(root, manifest(root, (APACHE,), weights=b"mlx"))
    link(root, listing(root, "sha256:" + "3" * 64, mlx_d))
    a = licensing.ollama_model("qwen3.5:4b", root)
    assert a["subject"]["api_tags_digest"] == {"llamacpp>ggml>mlx": mlx_d[7:], "mlx>llamacpp>ggml": mlx_d[7:]}


def test_s5_a_hostile_list_is_read_once_per_manifest_and_bounded(tmp_path):
    """The review of 4f5ce7e5: 5,923 entries naming one 1 MiB child were each re-read (93 s), and 5,000 absent
    children made 365,000 characters of uncertainty. Entries are read once per digest; a list of more than
    MAX_LIST_MANIFESTS manifests is held; at most MAX_NAMED_ABSENT absent digests are named."""
    root = tmp_path / "models"
    child = blob(root, manifest(root, (APACHE,)))
    entries = [{"mediaType": DOCKER_V2, "digest": child, "runner": "llamacpp"}] * 2000
    link(root, json.dumps({"schemaVersion": 2, "mediaType": MANIFEST_LIST, "manifests": entries}).encode())
    a = licensing.ollama_model("qwen3.5:4b", root)
    assert a["verdict"] == "CLEARED" and len(a["subject"]["children"]) == 1 and len(a["subject"]["weights"]) == 1
    root = tmp_path / "absent"
    child = blob(root, manifest(root, (APACHE,)))
    absent = ["sha256:" + f"{i:064x}" for i in range(licensing.MAX_LIST_MANIFESTS - 1)]
    link(root, listing(root, child) [:-2] + b"," + b",".join(json.dumps(
        {"mediaType": DOCKER_V2, "digest": d, "runner": "mlx"}).encode() for d in absent) + b"]}")
    a = licensing.ollama_model("qwen3.5:4b", root)
    assert a["verdict"] == "CLEARED", a["reason"]
    note = next(u for u in a["uncertainty"] if "does not hold" in u)
    assert note.count("sha256:") == licensing.MAX_NAMED_ABSENT and note.endswith(
        f"and {len(absent) - licensing.MAX_NAMED_ABSENT} more"), note
    root = tmp_path / "long"
    child = blob(root, manifest(root, (APACHE,)))
    link(root, listing(root, child)[:-2] + b"," + b",".join(json.dumps(
        {"mediaType": DOCKER_V2, "digest": "sha256:" + f"{i:064x}", "runner": "mlx"}).encode()
        for i in range(licensing.MAX_LIST_MANIFESTS)) + b"]}")
    a = licensing.ollama_model("qwen3.5:4b", root)
    assert a["held"] and f"reads at most {licensing.MAX_LIST_MANIFESTS}" in a["reason"], a["reason"]


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


# -- what Ollama's request parser and JSON decoder read (the review of 52f5703b, F1 to F4) -------------------------
# tests/unit/test_greg_ollama_oracle.py checks the same against Ollama's own code, frozen; these name each guard.

def with_config(root: Path, raw: bytes, settings: bytes, **keys) -> bytes:
    document = json.loads(raw)
    document["config"] = {"mediaType": "application/vnd.docker.container.image.v1+json",
                          "digest": blob(root, settings), "size": len(settings), **keys}
    return json.dumps(document).encode()


def test_f1_a_json_key_ollamas_decoder_reads_otherwise_holds_the_model_and_is_named(tmp_path):
    """Go's encoding/json matches a key to a field ignoring case, folds U+017F to s and U+212A to k, and a repeated
    key overwrites or merges into the first; GREG reads exact keys. On 52f5703b each of these was CLEARED while both
    Ollama versions serve the other reading (tests/fixtures/ollama_oracle/answers.json)."""
    relay = json.dumps({"remote_host": "https://relay.example", "remote_model": "x"}).encode()
    cases = []

    def case(label, build, key):
        root = tmp_path / label
        name = build(root)
        cases.append((label, licensing.ollama_model(name or "qwen3.5:4b", root), key))

    def layers(root, *pairs):
        return [{"mediaType": media, "digest": blob(root, data), "size": len(data)} for media, data in pairs]

    case("manifest", lambda r: link(r, json.dumps({
        "schemaVersion": 2, "mediaType": DOCKER_V2, "layers": json.loads(manifest(r, (APACHE,)))["layers"],
        "Layers": json.loads(manifest(r, (LLAMA,), weights=b"other"))["layers"]}).encode()) and None, "'Layers'")
    case("repeated", lambda r: link(r, with_config(r, manifest(r, (APACHE,)), relay)[:-1]
                                    + b',"config":{"mediaType":"x"}}') and None, "'config' and 'config'")
    case("not-ascii", lambda r: link(r, manifest(r, (APACHE,))[:-1] + ',"layer\u017f":[]}'.encode()) and None,
         "'layer\u017f'")
    case("layer", lambda r: link(r, json.dumps({"schemaVersion": 2, "mediaType": DOCKER_V2, "layers": layers(
        r, ("application/vnd.ollama.image.model", b"w"), (licensing.OLLAMA_LICENSE, APACHE.encode())) + [
        {"MediaType": "application/vnd.ollama.image.adapter", "digest": blob(r, b"adapter")}]}).encode()) and None,
        "'MediaType'")
    case("config", lambda r: link(r, with_config(r, manifest(r, (APACHE,)), b'{"model_format":"gguf"}',
                                                 Digest=blob(r, relay))) and None, "'Digest'")
    case("config-blob", lambda r: link(r, with_config(r, manifest(r, (APACHE,)), json.dumps(
        {"Remote_Host": "https://relay.example", "Remote_Model": "x"}).encode())) and None, "'Remote_Host'")
    case("config-blob-long-s", lambda r: link(r, with_config(r, manifest(r, (APACHE,)), json.dumps(
        {"remote_ho\u017ft": "https://relay.example", "remote_model": "x"}, ensure_ascii=False).encode())) and None,
        "'remote_ho\u017ft'")
    case("list-entry", lambda r: link(r, json.dumps({"schemaVersion": 2, "mediaType": MANIFEST_LIST, "manifests": [
        {"mediaType": DOCKER_V2, "digest": blob(r, manifest(r, (APACHE,))), "runner": "llamacpp",
         "Digest": blob(r, manifest(r, (LLAMA,), weights=b"other"))}]}).encode()) and None, "'Digest'")
    case("list-child", lambda r: link(r, listing(r, blob(r, manifest(r, (APACHE,))[:-1] + b',"Layers":' + json.dumps(
        json.loads(manifest(r, (LLAMA,), weights=b"other"))["layers"]).encode() + b"}"))) and None, "'Layers'")
    for label, a, key in cases:
        assert a is not None and a["held"] and a["verdict"] == "FOUNDER_REVIEW", (label, a and a["reason"])
        assert key in a["reason"] and "Ollama's JSON decoder" in a["reason"], (label, a["reason"])
    root = tmp_path / "unknown-keys"                 # a key Ollama has no field for, in any case, is not a hold
    link(root, manifest(root, (APACHE,))[:-1] + b',"annotations":{"Org":"x","org":"y"},"Extra":1}')
    assert licensing.ollama_model("qwen3.5:4b", root)["verdict"] == "CLEARED"


def test_f2_a_runner_and_digest_request_name_is_held_whatever_the_alias_or_case(tmp_path):
    """server/model_resolver.go digestModelName: "<runner>:<digest>" (mlx, mlxrunner, ggml, llamacpp, llama.cpp,
    llama-cpp, llama_cpp, any case) and a bare "sha256:<hex>" name a local manifest blob before any model. On
    52f5703b GREG read the model "llamacpp" (or "sha256") tagged with the digest, and cleared it."""
    root = tmp_path / "models"
    digest = blob(root, manifest(root, (LLAMA,), weights=b"blob weights"))[7:]
    names = [f"llamacpp:{digest[:12]}", f"LLAMA.CPP:{digest}", f"Llama-Cpp:sha256:{digest}", f"llama_cpp:{digest}",
             f"mlxrunner:{digest}", f"MLX:sha256-{digest}", f"ggml:{digest[:20].upper()}", f"sha256:{digest}",
             f"SHA256:{digest.upper()}"]
    for name in names:
        runner, tag = name.split(":", 1)
        if licensing._ollama_parts(name):
            link(root, manifest(root, (APACHE,)), "ollama.com", "library", runner.lower(), tag)
        a = licensing.ollama_model(name, root)
        assert a is not None and a["held"] and "digest of a local manifest blob" in a["reason"], (name, a)
    for name in ("llamacpp:4b", f"notarunner:{digest[:12]}", f"{digest[:12]}:4b"):
        link(root, manifest(root, (APACHE,)), "ollama.com", "library", *name.split(":"))
        assert licensing.ollama_model(name, root)["verdict"] == "CLEARED", name


def test_f4_a_digest_name_is_read_as_ollama_reads_it_in_any_case_of_namespace_and_tag(tmp_path):
    """manifest/paths.go ResolveDigestReferenceName compares the namespace and tag with strings.EqualFold."""
    root = tmp_path / "models"
    digest = blob(root, manifest(root, (LLAMA,), weights=b"blob weights"))[7:]
    for namespace, tag in (("library", "Latest"), ("Library", "latest"), ("LIBRARY", "LATEST")):
        link(root, manifest(root, (APACHE,)), "ollama.com", namespace, digest, tag)
        a = licensing.ollama_model(f"registry.ollama.ai/{namespace}/{digest}:{tag}", root)
        assert a["held"] and "digest of a local manifest blob" in a["reason"], (namespace, tag, a["reason"])
        for entry in (root / "manifests-v2").rglob(tag):
            entry.unlink()


def test_f3_a_cloud_or_local_source_suffix_is_held_in_any_case(tmp_path):
    """internal/modelref ParseRef: a last ":" part "cloud" or "local", or one ending in "-cloud", ignoring case, is a
    source suffix: a cloud name is proxied to ollama.com, and ":local" names the model before it. On 52f5703b GREG
    cleared a local manifest stored under those tags (greg.models.OllamaRoute refuses only ':cloud' and '-cloud')."""
    root = tmp_path / "models"
    for tag in ("4b-CLOUD", "4b-Cloud", "4b-cloud", "CLOUD", "cloud", "LOCAL", "Local"):
        link(root, manifest(root, (APACHE,)), "ollama.com", "library", "qwen3.5", tag)
        a = licensing.ollama_model(f"qwen3.5:{tag}", root)
        assert a["held"] and "source suffix" in a["reason"] and a["subject"]["manifest_sha256"] is None, (tag, a)
    held = licensing.admit_model_selection({"order": ["ollama", "anthropic"], "ollama_model": "qwen3.5:4b-Cloud"},
                                           root)
    assert held["order"] == ["anthropic"] and held["model_license_hold"]["verdict"] == "FOUNDER_REVIEW", held
    for name in ("qwen-cloud", "qwen3.5:4b-cloudy"):       # Ollama reads both as local models
        model, tag = (name.split(":") + ["latest"])[:2]
        link(root, manifest(root, (APACHE,)), "ollama.com", "library", model, tag)
        assert licensing.ollama_model(name, root)["verdict"] == "CLEARED", name


def test_f4_a_stored_name_that_is_not_ascii_is_never_matched(tmp_path):
    """Ollama's name index skips a stored name that is not a valid name (types/model/name.go isValidPart takes
    ASCII only), so a "kimi" spelled with U+212A (Kelvin sign), which Python lower-cases to "k", is not "kimi"."""
    root = tmp_path / "models"
    link(root, manifest(root, (APACHE,)), "ollama.com", "library", "\u212aimi", "4b")
    assert licensing.ollama_model("kimi:4b", root) is None


def test_f4_api_tags_reads_runners_as_ollama_trims_and_folds_them_and_takes_untyped_children(tmp_path):
    """manifest.go selectManifestReferenceWithPreferences: an entry's runner is compared trimmed and lower-cased,
    and an entry without a mediaType is a manifest."""
    root = tmp_path / "models"
    gguf, mlx = blob(root, manifest(root, (APACHE,), weights=b"gguf")), blob(root, manifest(root, (APACHE,), b"mlx"))
    link(root, json.dumps({"schemaVersion": 2, "mediaType": MANIFEST_LIST, "manifests": [
        {"digest": gguf, "runner": "LlamaCPP"}, {"mediaType": DOCKER_V2, "digest": mlx, "runner": " MLX\t"}]}).encode())
    a = licensing.ollama_model("qwen3.5:4b", root)
    assert a["verdict"] == "CLEARED" and a["subject"]["api_tags_digest"] == {
        "llamacpp>ggml>mlx": gguf[7:], "mlx>llamacpp>ggml": mlx[7:]}, a["subject"]
    assert [c["runners"] for c in a["subject"]["children"]] == [["llamacpp"], ["mlx"]]


def test_f4_a_list_entry_with_a_config_of_its_own_is_not_read_as_a_reference(tmp_path):
    """manifest.go isReference: an entry whose config names a digest is run as written, with no layers here."""
    root = tmp_path / "models"
    config = {"mediaType": "application/vnd.docker.container.image.v1+json", "digest": blob(root, b"{}")}
    link(root, json.dumps({"schemaVersion": 2, "mediaType": MANIFEST_LIST, "manifests": [
        {"mediaType": DOCKER_V2, "digest": blob(root, manifest(root, (APACHE,))), "runner": "llamacpp",
         "config": config}]}).encode())
    a = licensing.ollama_model("qwen3.5:4b", root)
    assert a["held"] and "carries a manifest of its own" in a["reason"], a["reason"]


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


def test_stale_evidence_and_holds_never_ride_on_any_result_and_an_order_must_be_a_list(tmp_path):
    root = two_models(tmp_path / "models")
    stale = {"license_evidence": {"model": "x", "verdict": "CLEARED"}, "model_license_hold": {"model": "y"}}
    cleared = licensing.admit_model_selection({"order": ["ollama"], "ollama_model": "qwen3.5:4b", **stale}, root)
    assert "model_license_hold" not in cleared and cleared["license_evidence"]["model"] != "x", cleared
    assert licensing.admit_model_selection({"order": ["anthropic"], **stale}, root) == {"order": ["anthropic"]}
    assert licensing.admit_model_selection({"ollama_model": "qwen3.5:4b", **stale}, root) == {
        "ollama_model": "qwen3.5:4b"}
    for order in ({"ollama": 1}, "ollama", 7):
        held = licensing.admit_model_selection({"order": order, "ollama_model": "qwen3.5:4b", **stale}, root)
        assert held == {"order": [], "model_license_hold": {
            "model": "qwen3.5:4b", "verdict": "UNASSESSED",
            "reason": "the selection's order is not a list of routes, so no route is admitted",
            "manifest_sha256": None, "assessment_digest": None}}, held
    assert licensing.admit_model_selection(["ollama"], root) == ["ollama"]


def two_stores(tmp_path: Path) -> tuple[Path, Path]:
    """Llama under <tmp>/srv, Apache under HOME's default store <tmp>/home/.ollama/models."""
    srv, home = tmp_path / "srv", tmp_path / "home" / ".ollama" / "models"
    link(srv, manifest(srv, (LLAMA,), weights=b"llama weights"))
    link(home, manifest(home, (APACHE,), weights=b"apache weights"))
    return srv, home


def test_ollama_models_is_read_as_envconfig_var_reads_it(tmp_path, monkeypatch):
    """N1 (review of d1724006). Ollama reads OLLAMA_MODELS through envconfig.Var: strings.TrimSpace, then
    strings.Trim of every leading and trailing " and ' (v0.40.0 and main). A Docker --env-file line
    OLLAMA_MODELS="/srv" keeps its quotes; on d1724006 GREG took the quoted path, found nothing there and cleared the
    home store's Apache copy while Ollama served the Llama manifest in /srv."""
    srv, home = two_stores(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    for value in (f'"{srv}"', f"'{srv}'", f"{srv} ", f" {srv}", f"\t\"'{srv}'\"\n", f"　{srv}\x85",
                  f" {srv} "):
        monkeypatch.setenv("OLLAMA_MODELS", value)
        a = licensing.ollama_model("qwen3.5:4b")
        assert a is not None and a["held"] and "llama-3.1" in a["reason"], (value, a and a["reason"])
    monkeypatch.setenv("OLLAMA_MODELS", f'" {srv}"')     # Trim is last: the space inside the quotes stays
    assert licensing.ollama_model("qwen3.5:4b") is None
    for empty in ("", " ", '""', " '' ", "\"'\""):      # empty once trimmed: Ollama's default, HOME's store
        monkeypatch.setenv("OLLAMA_MODELS", empty)
        a = licensing.ollama_model("qwen3.5:4b")
        assert a is not None and a["verdict"] == "CLEARED", (empty, a and a["reason"])


def test_while_ollama_models_is_set_no_other_store_is_read(tmp_path, monkeypatch):
    """N2 (review of d1724006). envconfig.Models returns OLLAMA_MODELS when it is set, with no fallback; Ollama
    answers "not found" and a run would pull bytes GREG never read. On d1724006 GREG fell through to the home store."""
    srv, home = two_stores(tmp_path)
    (tmp_path / "empty" / "blobs").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("OLLAMA_MODELS", str(tmp_path / "empty"))
    assert licensing.ollama_model("qwen3.5:4b") is None
    held = licensing.admit_model_selection({"order": ["ollama", "openai"], "ollama_model": "qwen3.5:4b"})
    assert held["order"] == ["openai"] and "in no Ollama store" in held["model_license_hold"]["reason"], held
    monkeypatch.delenv("OLLAMA_MODELS")
    assert licensing.ollama_model("qwen3.5:4b")["verdict"] == "CLEARED"


def test_a_manifest_go_cannot_decode_is_held(tmp_path):
    """N3 (review of d1724006). Python's json.loads(bytes) takes a UTF-8 BOM, UTF-16 or UTF-32; Go's encoding/json
    rejects them ("invalid character"), so Ollama runs nothing. On d1724006 each of these cleared."""
    for i, encode in enumerate((lambda raw: b"\xef\xbb\xbf" + raw, lambda raw: raw.decode().encode("utf-16"),
                                lambda raw: raw.decode().encode("utf-32"), lambda raw: raw.decode().encode("utf-16-le"))):
        root = tmp_path / str(i)
        link(root, encode(manifest(root, (APACHE,))))
        a = licensing.ollama_model("qwen3.5:4b", root)
        assert a["held"] and "not a readable Ollama manifest" in a["reason"], (i, a["reason"])
    root = tmp_path / "config"
    document = json.loads(manifest(root, (APACHE,)))
    config = blob(root, b"\xef\xbb\xbf" + json.dumps({"model_format": "gguf"}).encode())
    document["config"] = {"mediaType": "application/vnd.docker.container.image.v1+json", "digest": config, "size": 1}
    link(root, json.dumps(document).encode())
    assert licensing.ollama_model("qwen3.5:4b", root)["held"]
    child = tmp_path / "child"
    digest = blob(child, b"\xef\xbb\xbf" + manifest(child, (APACHE,)))
    link(child, json.dumps({"schemaVersion": 2, "mediaType": MANIFEST_LIST,
                            "manifests": [{"mediaType": DOCKER_V2, "digest": digest, "runner": "llamacpp"}]}).encode())
    assert licensing.ollama_model("qwen3.5:4b", child)["held"]


# -- the review of 49aaa812 ---------------------------------------------------------------------------------------

def test_with_ollama_models_unset_only_homes_store_is_read(tmp_path, monkeypatch):
    """F1 (review of 49aaa812). envconfig.Models (v0.40.0 and main) returns $HOME/.ollama/models when OLLAMA_MODELS
    is unset or empty once trimmed, and nothing else. On 49aaa812 GREG also read /usr/share/ollama/.ollama/models, the
    Linux service's store: with HOME's store empty and an Apache copy there, GREG cleared a model this process's
    Ollama does not have, and a run would pull bytes GREG never read. The system store is read only when a caller
    names it as models_dir."""
    (tmp_path / "home" / ".ollama" / "models" / "blobs").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("OLLAMA_MODELS", raising=False)
    listed, scandir = [], os.scandir

    def tracing(path=".", *args):
        listed.append(str(path))
        return scandir(path, *args)
    monkeypatch.setattr(os, "scandir", tracing)
    assert licensing.ollama_model("qwen3.5:4b") is None
    assert listed and all(p.startswith(str(tmp_path / "home" / ".ollama" / "models")) for p in listed), listed
    held = licensing.admit_model_selection({"order": ["ollama", "openai"], "ollama_model": "qwen3.5:4b"})
    assert held["order"] == ["openai"] and "in no Ollama store" in held["model_license_hold"]["reason"], held
    system = tmp_path / "usr-share-ollama" / ".ollama" / "models"      # what a caller passes for the service's store
    link(system, manifest(system, (APACHE,)))
    assert licensing.ollama_model("qwen3.5:4b", system)["verdict"] == "CLEARED"
    assert licensing.ollama_model("qwen3.5:4b") is None
    home = tmp_path / "home" / ".ollama" / "models"
    link(home, manifest(home, (APACHE,), weights=b"home weights"))
    assert licensing.ollama_model("qwen3.5:4b")["verdict"] == "CLEARED"


def test_with_ollama_models_and_home_unset_or_empty_the_model_is_held(tmp_path, monkeypatch):
    """F1. With OLLAMA_MODELS and HOME unset or empty, os.UserHomeDir fails and envconfig.Models panics: Ollama runs
    nothing. Python's Path.home() would read the password database's home for an unset HOME and "/" for an empty
    one; GREG reads neither and holds, naming models_dir as the way to point the gate at a store."""
    monkeypatch.delenv("OLLAMA_MODELS", raising=False)
    for home in (None, ""):
        if home is None:
            monkeypatch.delenv("HOME", raising=False)
        else:
            monkeypatch.setenv("HOME", home)
        a = licensing.ollama_model("qwen3.5:4b")
        assert a is not None and a["held"] and a["subject"]["manifest_sha256"] is None, (home, a)
        assert "HOME" in a["reason"] and "models_dir" in a["reason"], a["reason"]
        held = licensing.admit_model_selection({"order": ["ollama", "openai"], "ollama_model": "qwen3.5:4b"})
        assert held["order"] == ["openai"] and "HOME" in held["model_license_hold"]["reason"], held
    root = tmp_path / "models"
    link(root, manifest(root, (APACHE,)))
    assert licensing.ollama_model("qwen3.5:4b", root)["verdict"] == "CLEARED"
    monkeypatch.setenv("OLLAMA_MODELS", str(root))
    assert licensing.ollama_model("qwen3.5:4b")["verdict"] == "CLEARED"


def literal_manifest(root: Path, size: str, schema: str = "2") -> bytes:
    """An Apache manifest written by hand, its weight layer's size the JSON text ``size``."""
    weights, license_ = blob(root, b"GGUF weights"), blob(root, APACHE.encode())
    return ('{"schemaVersion":%s,"mediaType":"%s","layers":[{"mediaType":"application/vnd.ollama.image.model",'
            '"digest":"%s","size":%s},{"mediaType":"%s","digest":"%s","size":1}]}'
            % (schema, DOCKER_V2, weights, size, licensing.OLLAMA_LICENSE, license_)).encode()


def test_a_manifest_value_go_cannot_store_in_its_field_is_held(tmp_path):
    """F2 (review of 49aaa812). Python's json.loads takes NaN, Infinity and -Infinity, which Go's encoding/json
    rejects as invalid characters, and GREG never looked at a field's type; Go fails the whole decode on a value its
    field cannot hold: a layer's int64 size of 1e999, 1e2, 1.5, 2**63, "1" or true. Ollama loads none of these, and
    each cleared on 49aaa812. null, -1, the int64 bounds and a lone surrogate escape (Go reads U+FFFD) decode in Go,
    and clear."""
    held = {"NaN": "NaN", "Infinity": "Infinity", "-Infinity": "-Infinity", "1e999": "1e999", "1e2": "1e2",
            "1.5": "1.5", "1.0": "1.0", "2**63": "9223372036854775808", "-2**63-1": "-9223372036854775809",
            '"1"': '"1"', "true": "true", "[]": "[]", "{}": "{}"}
    for label, size in held.items():
        root = tmp_path / f"held-{len(list(tmp_path.iterdir()))}"
        link(root, literal_manifest(root, size))
        a = licensing.ollama_model("qwen3.5:4b", root)
        assert a["held"] and a["verdict"] == "FOUNDER_REVIEW", (label, a["reason"])
        assert "Go" in a["reason"], (label, a["reason"])
    for label, (size, schema) in {"schemaVersion 2.0": ("1", "2.0"), "schemaVersion \"2\"": ("1", '"2"'),
                                  "NaN under an unknown key": ('1,"x":NaN', "2")}.items():
        root = tmp_path / f"held-{len(list(tmp_path.iterdir()))}"
        link(root, literal_manifest(root, size, schema))
        assert licensing.ollama_model("qwen3.5:4b", root)["held"], label
    for label, size in {"null": "null", "-1": "-1", "2**63-1": "9223372036854775807",
                        "-2**63": "-9223372036854775808", "a lone surrogate": '1,"x":"\\ud800"',
                        "1e999 under an unknown key": '1,"x":1e999', "1.5 under an unknown key": '1,"x":[1.5]'}.items():
        root = tmp_path / f"clear-{len(list(tmp_path.iterdir()))}"
        link(root, literal_manifest(root, size))
        a = licensing.ollama_model("qwen3.5:4b", root)
        assert a["verdict"] == "CLEARED", (label, a["reason"])


def test_a_wrong_json_type_in_any_typed_field_is_held(tmp_path):
    """F2. Every field the gate decodes has a Go type: a string field takes no number, a struct no string, a slice no
    object, an int no fraction, and the config blob's generation_defaults (map[string]any) no number beyond float64."""
    def store(name, mutate, config=None):
        root = tmp_path / name
        document = json.loads(manifest(root, (APACHE,)))
        if config is not None:
            document["config"] = {"mediaType": "application/vnd.docker.container.image.v1+json",
                                  "digest": blob(root, config.encode()), "size": 1}
        mutate(document)
        link(root, json.dumps(document).encode())
        return licensing.ollama_model("qwen3.5:4b", root)

    def layer(key, value):
        return lambda d: d["layers"][1].__setitem__(key, value)
    held = {"mediaType 1": layer("mediaType", 1), "digest true": layer("digest", True),
            "from {}": layer("from", {}), "name []": layer("name", []),
            "mediaType of the manifest 2": lambda d: d.__setitem__("mediaType", 2),
            "runner 1": lambda d: d.__setitem__("runner", 1), "format false": lambda d: d.__setitem__("format", False),
            "config a string": lambda d: d.__setitem__("config", "x"),
            "config a list": lambda d: d.__setitem__("config", []),
            "layers an object": lambda d: d.__setitem__("layers", {"a": d["layers"]}),
            "a layer a string": lambda d: d["layers"].append("x"),
            "manifests a string": lambda d: d.__setitem__("manifests", "x"),
            "a nested manifest with a fractional size": lambda d: d.__setitem__(
                "manifests", [{"layers": [{"size": 1.5}]}])}
    for label, mutate in held.items():
        a = store(f"m{len(list(tmp_path.iterdir()))}", mutate)
        assert a["held"] and "Go" in a["reason"], (label, a["reason"])
    configs = {"context_length 1.5": '{"context_length":1.5}', "embedding_length \"8\"": '{"embedding_length":"8"}',
               "capabilities [1]": '{"capabilities":[1]}', "model_families \"x\"": '{"model_families":"x"}',
               "draft \"x\"": '{"draft":"x"}', "draft.config 1": '{"draft":{"config":1}}',
               "remote_host 1": '{"remote_host":1}', "generation_defaults 1e999":
               '{"generation_defaults":{"temperature":1e999}}', "generation_defaults a list":
               '{"generation_defaults":[0.7]}', "generation_defaults nested -1e999":
               '{"generation_defaults":{"x":[{"y":-1e999}]}}', "voices {}": '{"voices":{}}',
               "NaN": '{"model_format":"gguf","context_length":NaN}'}
    for label, config in configs.items():
        a = store(f"c{len(list(tmp_path.iterdir()))}", lambda d: None, config)
        assert a["held"], (label, a["reason"])
    for label, config in {"generation_defaults of floats and ints":
                          '{"generation_defaults":{"temperature":0.7,"top_k":40,"stop":["x",null]},'
                          '"context_length":4096,"capabilities":["completion",null],"draft":null}',
                          "an unknown key with 1e999": '{"model_format":"gguf","extra":1e999}'}.items():
        a = store(f"c{len(list(tmp_path.iterdir()))}", lambda d: None, config)
        assert a["verdict"] == "CLEARED", (label, a["reason"])
