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
(after ``ollama cp``, server/images.go CopyModel, or a failed best-effort write) was unassessed, and a model
re-pulled with other terms kept the earlier anchor's verdict until the anchor was rewritten.

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


def test_a_re_pull_with_other_terms_is_read_from_v2_not_from_the_earlier_anchor(tmp_path):
    """An anchor left by an earlier pull (Apache) and the manifest a later pull linked (Llama): Ollama serves v2."""
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
    assert licensing.ollama_model("ollama.com/library/qwen3.5:4b", root)["verdict"] == "CLEARED"
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
    and read the lower-cased legacy anchor of an earlier pull."""
    root = tmp_path / "models"
    link(root, manifest(root, (LLAMA,), weights=b"new weights"))
    anchor(root, manifest(root, (APACHE,), weights=b"old weights"))
    a = licensing.ollama_model("Qwen3.5:4b", root)
    assert a is not None and a["held"] and "llama-3.1" in a["reason"], a and a["reason"]
    root = tmp_path / "v2only"
    digest = link(root, manifest(root, (APACHE,)))
    (root / "manifests-v2" / "ollama.com" / "library" / "QWEN3.5" / "4b").mkdir(parents=True)   # not a manifest
    for name in ("Qwen3.5:4B", "Registry.Ollama.AI/library/qwen3.5:4b", "OLLAMA.COM/Library/QWEN3.5:4b"):
        a = licensing.ollama_model(name, root)
        assert a is not None and a["verdict"] == "CLEARED", (name, a and a["reason"])
        assert a["subject"]["manifest_sha256"] == digest.split(":")[1]


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
