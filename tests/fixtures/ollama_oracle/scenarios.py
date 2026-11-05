"""Ollama model stores for the frozen differential test of GREG's model-license gate.

Each scenario writes a store at ``<dir>/models`` (a few also write beside it, in ``<dir>``) and returns the request
name, a label, and the digests of any config blob in it that is a relay. The bytes are the same on every run, so
the digests in ``answers.json`` (what Ollama's own code serves for each store, frozen by ``freeze.py``) still name
the files ``tests/unit/test_greg_ollama_oracle.py`` builds; ``fingerprint`` checks that.

The first 54 scenarios are the independent reviewer's differential harness of 52f5703b (diff_harness.py), ported
with the same store bytes and without its LAYOUT switch; the next 22 were added with the fix of its findings F1 to
F4, and the last 9 with the fix of the review of d1724006 (N1 to N3: OLLAMA_MODELS read as envconfig.Var reads it,
only the store it names, and a manifest Go's decoder rejects).
``CLEARS`` are the stores both Ollama versions serve as one Apache-licensed manifest GREG is meant to clear: the
positive controls that keep the test from passing on a reader that holds everything.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

APACHE = (Path(__file__).resolve().parents[1] / "licenses" / "Apache-2.0.txt").read_text()
LLAMA = "LLAMA 3.1 COMMUNITY LICENSE AGREEMENT\nLlama 3.1 Version Release Date: July 23, 2024\n"
D2 = "application/vnd.docker.distribution.manifest.v2+json"
LIST = "application/vnd.ollama.manifest.list.v2+json"
LIC = "application/vnd.ollama.image.license"
MODEL = "application/vnd.ollama.image.model"
CONFIG = "application/vnd.docker.container.image.v1+json"
APACHE_DIGEST = "sha256:" + hashlib.sha256(APACHE.encode()).hexdigest()

SCENARIOS = []
CLEARS = set()
# The OLLAMA_MODELS value a scenario runs under, "{models}" standing for <dir>/models, with HOME=<dir>. A scenario not
# named here runs under OLLAMA_MODELS=<dir>/models exactly; the test passes that store to GREG as ``models_dir``,
# and an ENV scenario's value to GREG through the environment, with no ``models_dir``.
ENV = {}


def scenario(fn=None, *, clears=False, env=None):
    def register(f):
        SCENARIOS.append(f)
        if clears:
            CLEARS.add(f.__name__)
        if env is not None:
            ENV[f.__name__] = env
        return f
    return register(fn) if fn is not None else register


def fingerprint(directory: Path) -> str:
    """A digest of everything under ``directory``: each path, and a file's bytes or a link's target (``directory``
    itself written as <dir>, since a few scenarios link to absolute paths beside the store)."""
    h = hashlib.sha256()

    def walk(path: Path, rel: str):
        for entry in sorted(os.scandir(path), key=lambda e: e.name):
            name = f"{rel}/{entry.name}"
            if entry.is_symlink():
                h.update(f"L {name} -> {os.readlink(entry.path).replace(str(directory), '<dir>')}\n".encode())
            elif entry.is_dir():
                h.update(f"D {name}\n".encode())
                walk(Path(entry.path), name)
            else:
                h.update(f"F {name} {hashlib.sha256(Path(entry.path).read_bytes()).hexdigest()}\n".encode())
    walk(directory, "")
    return h.hexdigest()


def blob(root, data: bytes) -> str:
    (root / "blobs").mkdir(parents=True, exist_ok=True)
    d = "sha256:" + hashlib.sha256(data).hexdigest()
    (root / "blobs" / d.replace(":", "-")).write_bytes(data)
    return d


def lay(root, media, data: bytes):
    return {"mediaType": media, "digest": blob(root, data), "size": len(data)}


def mf(root, licenses=(APACHE,), weights=b"GGUF weights", extra=(), raw_layers=None, **top):
    layers = raw_layers if raw_layers is not None else (
        [lay(root, MODEL, weights)] + [lay(root, LIC, t.encode()) for t in licenses] + list(extra))
    doc = {"schemaVersion": 2, "mediaType": D2, "layers": layers}
    doc.update(top)
    return json.dumps(doc).encode()


def link(root, raw, *where, target_name=None):
    d = blob(root, raw)
    named = root / "manifests-v2" / Path(*(where or ("ollama.com", "library", "qwen3.5", "4b")))
    named.parent.mkdir(parents=True, exist_ok=True)
    named.symlink_to(os.path.relpath(root / "blobs" / (target_name or d.replace(":", "-")), named.parent))
    return d


def legacy(root, raw, *where):
    p = root / "manifests" / Path(*(where or ("registry.ollama.ai", "library", "qwen3.5", "4b")))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(raw)
    return p


def listing(entries, **top):
    doc = {"schemaVersion": 2, "mediaType": LIST, "manifests": entries}
    doc.update(top)
    return json.dumps(doc).encode()


def ref(d, runner, **extra):
    e = {"mediaType": D2, "digest": d, "runner": runner}
    e.update(extra)
    return e


def relay_config(root, keys=("remote_host", "remote_model")) -> str:
    return blob(root, json.dumps(dict(zip(keys, ("https://relay.example", "x")))).encode())


# --- baselines -------------------------------------------------------------------------------------------------
@scenario(clears=True)
def base_v2_apache(root):
    link(root, mf(root))
    return "qwen3.5:4b", "v2 link, Apache"


@scenario(clears=True)
def base_v2_apache_with_anchor(root):
    raw = mf(root)
    link(root, raw)
    doc = json.loads(raw)
    doc["layers"].append({"mediaType": D2, "digest": "sha256:" + hashlib.sha256(raw).hexdigest(), "size": len(raw)})
    legacy(root, json.dumps(doc).encode())
    return "qwen3.5:4b", "v2 link + downgrade anchor, Apache"


@scenario(clears=True)
def r4b_case(root):
    link(root, mf(root))
    return "Qwen3.5:4b", "R4b: request Qwen3.5:4b, store holds qwen3.5 v2 only"


@scenario(clears=True)
def r4b_case_upper_everything(root):
    link(root, mf(root))
    return "REGISTRY.OLLAMA.AI/LIBRARY/QWEN3.5:4B", "R4b': everything upper-cased"


@scenario
def r4b_explicit_ollama_com(root):
    link(root, mf(root), "ollama.com", "library", "Qwen3.5", "4b")
    return "ollama.com/library/qwen3.5:4b", "explicit ollama.com host, stored Qwen3.5"


@scenario
def r4b_stored_upper_host(root):
    link(root, mf(root), "Ollama.com", "library", "qwen3.5", "4b")
    return "qwen3.5:4b", "v2 stored under Ollama.com"


# --- JSON key case (Go encoding/json matches keys ignoring case; last duplicate wins) ---------------------------
@scenario
def json_dup_layers_case(root):
    good = [lay(root, MODEL, b"w-good"), lay(root, LIC, APACHE.encode())]
    evil = [lay(root, MODEL, b"w-evil"), lay(root, LIC, LLAMA.encode())]
    raw = json.dumps({"schemaVersion": 2, "mediaType": D2, "layers": good, "Layers": evil}).encode()
    link(root, raw)
    return "qwen3.5:4b", "manifest with 'layers' (Apache) and 'Layers' (Llama)"


@scenario
def json_hidden_license_layer(root):
    layers = [lay(root, MODEL, b"w"), lay(root, LIC, APACHE.encode()),
              {"MediaType": LIC, "Digest": blob(root, LLAMA.encode()), "Size": len(LLAMA)}]
    link(root, mf(root, raw_layers=layers))
    return "qwen3.5:4b", "a license layer spelled MediaType/Digest (Llama)"


@scenario
def json_layer_digest_case_dup(root):
    layers = [lay(root, MODEL, b"w"),
              {"mediaType": LIC, "digest": blob(root, APACHE.encode()), "Digest": blob(root, LLAMA.encode())}]
    link(root, mf(root, raw_layers=layers))
    return "qwen3.5:4b", "a license layer with digest (Apache) and Digest (Llama)"


@scenario
def json_hidden_adapter(root):
    layers = [lay(root, MODEL, b"w"), lay(root, LIC, APACHE.encode()),
              {"MediaType": "application/vnd.ollama.image.adapter", "digest": blob(root, b"adapter"), "size": 7}]
    link(root, mf(root, raw_layers=layers))
    return "qwen3.5:4b", "an adapter layer spelled MediaType"


@scenario
def json_top_mediatype_list(root):
    child = mf(root, licenses=(), weights=b"child-unlicensed")
    cd = blob(root, child)
    doc = {"schemaVersion": 2, "MediaType": LIST, "manifests": [ref(cd, "llamacpp"), ref(cd, "mlx"), ref(cd, "ggml")],
           "layers": [lay(root, MODEL, b"decoy"), lay(root, LIC, APACHE.encode())]}
    link(root, json.dumps(doc).encode())
    return "qwen3.5:4b", "top-level MediaType=list (Go) beside Apache 'layers' (Python)"


@scenario
def json_top_mediatype_dup(root):
    child = mf(root, licenses=(), weights=b"child-unlicensed")
    cd = blob(root, child)
    doc = {"schemaVersion": 2, "mediaType": D2, "MediaType": LIST,
           "manifests": [ref(cd, "llamacpp"), ref(cd, "mlx"), ref(cd, "ggml")],
           "layers": [lay(root, MODEL, b"decoy"), lay(root, LIC, APACHE.encode())]}
    link(root, json.dumps(doc).encode())
    return "qwen3.5:4b", "mediaType=docker then MediaType=list"


@scenario
def json_list_entry_inline_layers(root):
    good = mf(root, weights=b"good-child")
    gd = blob(root, good)
    evil = [lay(root, MODEL, b"inline-evil"), lay(root, LIC, LLAMA.encode())]
    link(root, listing([ref(gd, r, Layers=evil) for r in ("llamacpp", "mlx", "ggml")]))
    return "qwen3.5:4b", "list entries naming an Apache blob but carrying 'Layers' (Llama)"


@scenario
def json_list_entry_digest_dup(root):
    good, evil = mf(root, weights=b"good-child"), mf(root, licenses=(LLAMA,), weights=b"evil-child")
    gd, ed = blob(root, good), blob(root, evil)
    link(root, listing([ref(gd, r, Digest=ed) for r in ("llamacpp", "mlx", "ggml")]))
    return "qwen3.5:4b", "list entries with digest (Apache child) and Digest (Llama child)"


@scenario
def json_list_entry_manifests_case(root):
    good, evil = mf(root, weights=b"good-child"), mf(root, licenses=(LLAMA,), weights=b"evil-child")
    gd, ed = blob(root, good), blob(root, evil)
    doc = {"schemaVersion": 2, "mediaType": LIST, "manifests": [ref(gd, "llamacpp")],
           "Manifests": [ref(ed, r) for r in ("llamacpp", "mlx", "ggml")]}
    link(root, json.dumps(doc).encode())
    return "qwen3.5:4b", "list with manifests (Apache) and Manifests (Llama)"


@scenario
def json_config_case_relay(root):
    cfg = relay_config(root)
    doc = json.loads(mf(root))
    doc["Config"] = {"mediaType": CONFIG, "digest": cfg, "size": 10}
    link(root, json.dumps(doc).encode())
    return "qwen3.5:4b", "relay config under 'Config'", (cfg,)


@scenario
def json_relay_keys_case(root):
    cfg = relay_config(root, ("Remote_Host", "Remote_Model"))
    doc = json.loads(mf(root))
    doc["config"] = {"mediaType": CONFIG, "digest": cfg, "size": 10}
    link(root, json.dumps(doc).encode())
    return "qwen3.5:4b", "relay config with Remote_Host/Remote_Model keys", (cfg,)


@scenario
def json_long_s_key(root):
    good = [lay(root, MODEL, b"w-good"), lay(root, LIC, APACHE.encode())]
    evil = [lay(root, MODEL, b"w-evil"), lay(root, LIC, LLAMA.encode())]
    raw = ('{"schemaVersion":2,"mediaType":"%s","layers":%s,"layer\u017f":%s}' % (D2, json.dumps(good),
                                                                                    json.dumps(evil))).encode()
    link(root, raw)
    return "qwen3.5:4b", "'layers' (Apache) then 'layer\u017f' (U+017F) (Llama)"


# --- names, hosts, placement -------------------------------------------------------------------------------------
@scenario(clears=True)
def host_port_v2(root):
    link(root, mf(root), "myhost%3A5000", "ns", "m", "t")
    return "myhost:5000/ns/m:t", "host:port, v2 under %3A"


@scenario
def host_port_v2_lower(root):
    link(root, mf(root), "myhost%3a5000", "ns", "m", "t")
    return "myhost:5000/ns/m:t", "host:port, v2 under %3a"


@scenario(clears=True)
def host_port_legacy_literal(root):
    legacy(root, mf(root), "myhost:5000", "ns", "m", "t")
    return "myhost:5000/ns/m:t", "host:port, legacy under literal colon"


@scenario
def host_port_legacy_encoded(root):
    legacy(root, mf(root), "myhost%3A5000", "ns", "m", "t")
    return "myhost:5000/ns/m:t", "host:port, legacy under %3A"


@scenario
def host_port_v2_literal(root):
    link(root, mf(root), "myhost:5000", "ns", "m", "t")
    return "myhost:5000/ns/m:t", "host:port, v2 under a literal colon"


@scenario
def two_v2_spellings(root):
    link(root, mf(root, licenses=(LLAMA,), weights=b"x"), "registry.ollama.ai", "library", "qwen3.5", "4b")
    link(root, mf(root), "ollama.com", "library", "qwen3.5", "4b")
    return "qwen3.5:4b", "v2 under both registry spellings (Llama at registry.ollama.ai)"


@scenario
def dangling_v2_with_legacy(root):
    named = root / "manifests-v2" / "ollama.com" / "library" / "qwen3.5" / "4b"
    named.parent.mkdir(parents=True)
    named.symlink_to("../../../../blobs/sha256-" + "0" * 64)
    legacy(root, mf(root))
    return "qwen3.5:4b", "dangling v2 link + Apache legacy"


@scenario(clears=True)
def legacy_only(root):
    legacy(root, mf(root))
    return "qwen3.5:4b", "legacy only (Ollama 0.35 store)"


@scenario(clears=True)
def legacy_only_ollama_com(root):
    legacy(root, mf(root), "ollama.com", "library", "qwen3.5", "4b")
    return "qwen3.5:4b", "legacy only, under ollama.com"


@scenario
def digest_name_unmatched(root):
    link(root, mf(root), "ollama.com", "library", "deadbeefcafe", "latest")
    return "deadbeefcafe", "a 12-hex name with no matching blob"


@scenario
def upper_hex_link_target(root):
    raw = mf(root)
    d = blob(root, raw)
    upper = "sha256-" + d[7:].upper()
    os.rename(root / "blobs" / d.replace(":", "-"), root / "blobs" / upper)
    link(root, raw, target_name=upper)
    return "qwen3.5:4b", "v2 link to sha256-<UPPER HEX> blob"


@scenario
def symlinked_blob(root):
    raw = mf(root)
    d = blob(root, raw)
    elsewhere = root.parent / "elsewhere"
    elsewhere.mkdir()
    real = elsewhere / "m"
    os.rename(root / "blobs" / d.replace(":", "-"), real)
    (root / "blobs" / d.replace(":", "-")).symlink_to(real)
    link(root, raw)
    return "qwen3.5:4b", "v2 link to a blob that is itself a link out of the store"


@scenario(clears=True)
def hardlinked_v2(root):
    raw = mf(root)
    d = blob(root, raw)
    named = root / "manifests-v2" / "ollama.com" / "library" / "qwen3.5" / "4b"
    named.parent.mkdir(parents=True)
    os.link(root / "blobs" / d.replace(":", "-"), named)
    return "qwen3.5:4b", "v2 entry hard-linked to its blob"


@scenario
def symlinked_tree_dir(root):
    other = root.parent / "other-tree"
    (other / "library" / "qwen3.5").mkdir(parents=True)
    (other / "library" / "qwen3.5" / "4b").write_bytes(mf(root))
    (root / "manifests-v2").mkdir(parents=True)
    (root / "manifests-v2" / "ollama.com").symlink_to(other)
    return "qwen3.5:4b", "manifests-v2/ollama.com is a link to a directory outside the store"


@scenario
def v2_link_to_v2_entry(root):
    link(root, mf(root), "ollama.com", "library", "base", "latest")
    named = root / "manifests-v2" / "ollama.com" / "library" / "qwen3.5" / "4b"
    named.parent.mkdir(parents=True)
    named.symlink_to("../../base/latest")
    return "qwen3.5:4b", "v2 link to another v2 link (chain to a blob)"


# --- lists ---------------------------------------------------------------------------------------------------------
@scenario(clears=True)
def list_all_apache(root):
    ds = [blob(root, mf(root, weights=r.encode())) for r in ("mlx", "llamacpp")]
    link(root, listing([ref(ds[0], "mlx"), ref(ds[1], "llamacpp")]))
    return "qwen3.5:4b", "list, two Apache children"


@scenario(clears=True)
def list_first_runner_absent_second_present(root):
    good = blob(root, mf(root, weights=b"good"))
    evil = mf(root, licenses=(LLAMA,), weights=b"evil")
    ed = "sha256:" + hashlib.sha256(evil).hexdigest()           # not stored
    link(root, listing([ref(ed, "llamacpp"), ref(good, "llamacpp"), ref(good, "mlx")]))
    return "qwen3.5:4b", "first llamacpp child absent, second llamacpp child Apache"


@scenario
def list_runner_alias(root):
    good = blob(root, mf(root, weights=b"good"))
    evil = blob(root, mf(root, licenses=(LLAMA,), weights=b"evil"))
    link(root, listing([ref(good, "llama.cpp"), ref(evil, "llamacpp")]))
    return "qwen3.5:4b", "runner alias llama.cpp (Apache) and llamacpp (Llama)"


@scenario(clears=True)
def list_child_mediatype_empty(root):
    good = blob(root, mf(root, weights=b"good"))
    link(root, listing([{"digest": good, "runner": "llamacpp"}, {"digest": good, "runner": "mlx"}]))
    return "qwen3.5:4b", "list children without mediaType"


@scenario
def list_child_mediatype_other(root):
    good = blob(root, mf(root, weights=b"good"))
    evil = blob(root, mf(root, licenses=(), weights=b"evil"))
    link(root, listing([{"mediaType": "application/vnd.oci.image.manifest.v1+json", "digest": evil,
                         "runner": "llamacpp"}, ref(good, "llamacpp"), ref(good, "mlx"), ref(good, "ggml")]))
    return "qwen3.5:4b", "an OCI-typed child (unlicensed) Ollama skips, then Apache"


@scenario
def list_child_blob_is_list(root):
    inner_child = blob(root, mf(root, licenses=(), weights=b"inner"))
    inner = blob(root, listing([ref(inner_child, "llamacpp")]))
    link(root, listing([ref(inner, "llamacpp"), ref(inner, "mlx"), ref(inner, "ggml")]))
    return "qwen3.5:4b", "a child blob that is itself a list"


@scenario
def list_child_upper_digest(root):
    good = blob(root, mf(root, weights=b"good"))
    evil = blob(root, mf(root, licenses=(), weights=b"evil"))
    link(root, listing([ref("sha256:" + evil[7:].upper(), "llamacpp"), ref(good, "mlx")]))
    return "qwen3.5:4b", "a child digest in upper-case hex (unlicensed) and an Apache child"


@scenario
def list_child_dash_digest(root):
    good = blob(root, mf(root, weights=b"good"))
    evil = blob(root, mf(root, licenses=(), weights=b"evil"))
    link(root, listing([ref("sha256-" + evil[7:], "llamacpp"), ref(good, "mlx")]))
    return "qwen3.5:4b", "a child digest spelled sha256-<hex> (unlicensed) and an Apache child"


@scenario
def list_child_symlinked_blob(root):
    good = blob(root, mf(root, weights=b"good"))
    evil = mf(root, licenses=(), weights=b"evil")
    ed = blob(root, evil)
    out = root.parent / "out"
    out.mkdir()
    os.rename(root / "blobs" / ed.replace(":", "-"), out / "x")
    (root / "blobs" / ed.replace(":", "-")).symlink_to(out / "x")
    link(root, listing([ref(ed, "llamacpp"), ref(good, "mlx")]))
    return "qwen3.5:4b", "an unlicensed child whose blob is a link"


@scenario
def list_with_top_layers(root):
    good = blob(root, mf(root, weights=b"good"))
    link(root, listing([ref(good, "llamacpp")], layers=[lay(root, MODEL, b"top"), lay(root, LIC, LLAMA.encode())]))
    return "qwen3.5:4b", "list with top-level Llama layers"


@scenario(clears=True)
def list_child_tensor_draft(root):
    layers = [lay(root, "application/vnd.ollama.image.tensor", b"t1"), lay(root, "application/vnd.ollama.image.draft",
                                                                              b"d1"), lay(root, LIC, APACHE.encode())]
    good = blob(root, mf(root, raw_layers=layers))
    link(root, listing([ref(good, "mlx")]))
    return "qwen3.5:4b", "an mlx child with tensor and draft layers"


@scenario
def list_empty(root):
    link(root, listing([]))
    return "qwen3.5:4b", "an empty list"


@scenario(clears=True)
def plain_projector_adapter(root):
    extra = [lay(root, "application/vnd.ollama.image.projector", b"proj"),
             lay(root, "application/vnd.ollama.image.adapter", b"adap")]
    link(root, mf(root, extra=extra))
    return "qwen3.5:4b", "plain manifest with projector and adapter"


@scenario
def config_missing(root):
    doc = json.loads(mf(root))
    doc["config"] = {"mediaType": CONFIG, "digest": "sha256:" + "1" * 64}
    link(root, json.dumps(doc).encode())
    return "qwen3.5:4b", "config blob missing"


@scenario
def config_empty_digest_relay_layer(root):
    doc = json.loads(mf(root))
    doc["config"] = {"mediaType": "x", "digest": ""}
    link(root, json.dumps(doc).encode())
    return "qwen3.5:4b", "config with empty digest"


@scenario
def duplicate_config_keys(root):
    cfg_ok = blob(root, json.dumps({"model_format": "gguf"}).encode())
    cfg_relay = relay_config(root)
    raw = mf(root)
    body = raw[:-1] + (',"config":{"digest":"%s"},"config":{"digest":"%s"}}' % (cfg_relay, cfg_ok)).encode()
    link(root, body)
    return "qwen3.5:4b", "two config keys (relay first, plain last)", (cfg_relay,)


# --- request-name forms Ollama's handlers parse before any lookup (server/model_resolver.go, internal/modelref) ----
@scenario
def name_cloud_suffix_upper(root):
    link(root, mf(root), "ollama.com", "library", "qwen3.5", "4b-CLOUD")
    return "qwen3.5:4b-CLOUD", "a local Apache manifest under tag 4b-CLOUD (Ollama: cloud source)"


@scenario
def name_cloud_suffix_lower(root):
    link(root, mf(root), "ollama.com", "library", "qwen3.5", "4b-cloud")
    return "qwen3.5:4b-cloud", "a local Apache manifest under tag 4b-cloud (Ollama: cloud source)"


@scenario
def name_runner_digest(root):
    d = blob(root, mf(root, licenses=(LLAMA,), weights=b"blob-evil"))
    link(root, mf(root), "ollama.com", "library", "llamacpp", d[7:19])
    return "llamacpp:" + d[7:19], "llamacpp:<12 hex>: named manifest Apache, blob sha256-<hex>.. Llama"


@scenario
def name_sha256_colon(root):
    d = blob(root, mf(root, licenses=(LLAMA,), weights=b"blob-evil"))
    link(root, mf(root), "ollama.com", "library", "sha256", d[7:])
    return "sha256:" + d[7:], "sha256:<64 hex>: named manifest Apache, blob Llama"


@scenario
def name_mlx_sha256_dash(root):
    d = blob(root, mf(root, licenses=(LLAMA,), weights=b"blob-evil"))
    link(root, mf(root), "ollama.com", "library", "mlx", "sha256-" + d[7:])
    return "mlx:sha256-" + d[7:], "mlx:sha256-<64 hex>: named manifest Apache, blob Llama"


# === added with the fix of F1-F4 ====================================================================================
# --- F1: more keys Go reads and GREG did not ---------------------------------------------------------------------
@scenario
def json_dup_config_merge(root):
    cfg = relay_config(root)
    raw = mf(root)
    body = raw[:-1] + (',"config":{"mediaType":"%s","digest":"%s"},"config":{"mediaType":"x"}}'
                       % (CONFIG, cfg)).encode()
    link(root, body)
    return "qwen3.5:4b", "a relay 'config', then a second 'config' without a digest (Go merges the two)", (cfg,)


@scenario
def json_long_s_remote_host(root):
    cfg = blob(root, '{"remote_ho\u017ft":"https://relay.example","remote_model":"x"}'.encode())
    doc = json.loads(mf(root))
    doc["config"] = {"mediaType": CONFIG, "digest": cfg, "size": 10}
    link(root, json.dumps(doc).encode())
    return "qwen3.5:4b", "a relay config whose host key is spelled remote_ho\u017ft (U+017F)", (cfg,)


@scenario
def json_long_s_manifests(root):
    good, evil = mf(root, weights=b"good-child"), mf(root, licenses=(LLAMA,), weights=b"evil-child")
    gd, ed = blob(root, good), blob(root, evil)
    raw = ('{"schemaVersion":2,"mediaType":"%s","manifests":%s,"manife\u017fts":%s}' % (
        LIST, json.dumps([ref(gd, r) for r in ("llamacpp", "mlx", "ggml")]),
        json.dumps([ref(ed, r) for r in ("llamacpp", "mlx", "ggml")]))).encode()
    link(root, raw)
    return "qwen3.5:4b", "a list with 'manifests' (Apache) then 'manife\u017fts' (U+017F) (Llama)"


@scenario
def json_dup_layers_exact(root):
    first = [lay(root, MODEL, b"w"), lay(root, LIC, LLAMA.encode())]
    last = [lay(root, MODEL, b"w"), lay(root, LIC, APACHE.encode())]
    raw = mf(root, raw_layers=first)[:-1] + (',"layers":%s}' % json.dumps(last)).encode()
    link(root, raw)
    return "qwen3.5:4b", "'layers' twice, spelled the same (Llama, then Apache)"


# --- F2: digest names, runner aliases, any case ------------------------------------------------------------------
@scenario
def name_alias_llama_dot_cpp(root):
    d = blob(root, mf(root, licenses=(LLAMA,), weights=b"blob-evil"))
    link(root, mf(root), "ollama.com", "library", "llama.cpp", d[7:19])
    return "llama.cpp:" + d[7:19], "llama.cpp:<12 hex>: named manifest Apache, blob Llama"


@scenario
def name_alias_mlxrunner_upper(root):
    d = blob(root, mf(root, licenses=(LLAMA,), weights=b"blob-evil"))
    link(root, mf(root), "ollama.com", "library", "mlxrunner", d[7:])
    return "MLXRUNNER:" + d[7:], "MLXRUNNER:<64 hex>: named manifest Apache, blob Llama"


@scenario
def name_alias_ggml_upper_dash(root):
    d = blob(root, mf(root, licenses=(LLAMA,), weights=b"blob-evil"))
    link(root, mf(root), "ollama.com", "library", "ggml", "SHA256-" + d[7:].upper())
    return "Ggml:SHA256-" + d[7:].upper(), "Ggml:SHA256-<64 HEX>: named manifest Apache, blob Llama"


@scenario
def name_alias_llama_underscore(root):
    d = blob(root, mf(root, licenses=(LLAMA,), weights=b"blob-evil"))
    link(root, mf(root), "ollama.com", "library", "llama_cpp", d[7:])
    return "llama_cpp:" + d[7:], "llama_cpp:<64 hex>: named manifest Apache, blob Llama"


@scenario
def name_sha256_dash_upper(root):
    d = blob(root, mf(root, licenses=(LLAMA,), weights=b"blob-evil"))
    link(root, mf(root), "ollama.com", "library", "sha256-" + d[7:], "latest")
    return "SHA256-" + d[7:].upper(), "SHA256-<64 HEX>: named manifest Apache, blob Llama"


@scenario
def name_runner_prefix_unmatched(root):
    link(root, mf(root), "ollama.com", "library", "llamacpp", "abcdefabcdef")
    return "llamacpp:abcdefabcdef", "llamacpp:<12 hex> that no blob begins with: Ollama reads the named manifest"


@scenario
def name_digest_tag_case(root):
    d = blob(root, mf(root, licenses=(LLAMA,), weights=b"blob-evil"))
    link(root, mf(root), "ollama.com", "library", d[7:], "Latest")
    return d[7:] + ":Latest", "<64 hex>:Latest: named manifest Apache, blob Llama"


@scenario
def name_digest_namespace_case(root):
    d = blob(root, mf(root, licenses=(LLAMA,), weights=b"blob-evil"))
    link(root, mf(root), "ollama.com", "library", d[7:], "latest")
    return "Library/" + d[7:], "Library/<64 hex>: named manifest Apache, blob Llama"


@scenario
def name_digest_qualified_upper(root):
    d = blob(root, mf(root, licenses=(LLAMA,), weights=b"blob-evil"))
    link(root, mf(root), "ollama.com", "library", d[7:], "latest")
    return "REGISTRY.OLLAMA.AI/LIBRARY/" + d[7:] + ":LATEST", "fully qualified, upper-cased digest name"


# --- F3: source suffixes, any case -----------------------------------------------------------------------------------
@scenario
def name_cloud_suffix_mixed(root):
    link(root, mf(root), "ollama.com", "library", "qwen3.5", "4b-Cloud")
    return "qwen3.5:4b-Cloud", "a local Apache manifest under tag 4b-Cloud (Ollama: cloud source)"


@scenario
def name_cloud_tag_upper(root):
    link(root, mf(root), "ollama.com", "library", "qwen3.5", "CLOUD")
    return "qwen3.5:CLOUD", "a local Apache manifest under tag CLOUD (Ollama: cloud source)"


@scenario
def name_local_suffix_upper(root):
    link(root, mf(root), "ollama.com", "library", "qwen3.5", "LOCAL")
    link(root, mf(root, licenses=(LLAMA,), weights=b"latest weights"), "ollama.com", "library", "qwen3.5", "latest")
    return "qwen3.5:LOCAL", "tag LOCAL (Apache) beside latest (Llama): Ollama strips ':LOCAL'"


@scenario
def name_local_suffix_after_tag(root):
    link(root, mf(root, licenses=(LLAMA,), weights=b"4b weights"))
    return "qwen3.5:4b:local", "qwen3.5:4b:local: Ollama serves qwen3.5:4b (Llama)"


@scenario
def name_cloud_without_tag(root):
    link(root, mf(root), "ollama.com", "library", "qwen-cloud", "latest")
    return "qwen-cloud", "qwen-cloud with no tag: Ollama reads a local model of that name"


# --- F4: runner case, untyped children, entries with a config, relays, stored names ------------------------------
@scenario(clears=True)
def list_runner_case(root):
    gguf, mlx = blob(root, mf(root, weights=b"gguf")), blob(root, mf(root, weights=b"mlx"))
    link(root, listing([ref(gguf, "LlamaCPP"), ref(mlx, " MLX ")]))
    return "qwen3.5:4b", "list children whose runners are 'LlamaCPP' and ' MLX '"


@scenario
def list_entry_config_only(root):
    good = blob(root, mf(root, weights=b"good"))
    cfg = blob(root, json.dumps({"model_format": "gguf"}).encode())
    link(root, listing([ref(good, r, config={"mediaType": CONFIG, "digest": cfg}) for r in ("llamacpp", "mlx")]))
    return "qwen3.5:4b", "list entries naming an Apache blob and carrying a config of their own"


@scenario
def relay_host_only(root):
    cfg = blob(root, json.dumps({"remote_host": "https://relay.example"}).encode())
    doc = json.loads(mf(root))
    doc["config"] = {"mediaType": CONFIG, "digest": cfg, "size": 10}
    link(root, json.dumps(doc).encode())
    return "qwen3.5:4b", "a config naming a remote host and no remote model (Ollama runs the local weights)"


@scenario
def stored_name_kelvin(root):
    link(root, mf(root), "ollama.com", "library", "\u212aimi", "4b")
    return "kimi:4b", "the only entry is stored as \u212aimi (U+212A, Kelvin sign)"


# --- N1, N2: OLLAMA_MODELS as envconfig.Var reads it (TrimSpace, then Trim of " and '), and no other store ----------
def two_stores(root):
    """Llama under the store OLLAMA_MODELS names (<dir>/models), Apache under HOME's default store."""
    home = root.parent / ".ollama" / "models"
    link(root, mf(root, licenses=(LLAMA,), weights=b"llama-w"))
    link(home, mf(home, weights=b"apache-w"))
    return "qwen3.5:4b"


@scenario(env='"{models}"')
def env_models_double_quoted(root):
    return two_stores(root), 'OLLAMA_MODELS="<store>" (Llama there), Apache in the home store'


@scenario(env="'{models}'")
def env_models_single_quoted(root):
    return two_stores(root), "OLLAMA_MODELS='<store>' (Llama there), Apache in the home store"


@scenario(env="{models} ")
def env_models_trailing_space(root):
    return two_stores(root), "OLLAMA_MODELS='<store> ' (Llama there), Apache in the home store"


@scenario(env=" {models}")
def env_models_leading_space(root):
    return two_stores(root), "OLLAMA_MODELS=' <store>' (Llama there), Apache in the home store"


@scenario(clears=True, env='\t"\'{models}\'" ')
def env_models_quoted_apache(root):
    home = root.parent / ".ollama" / "models"
    link(root, mf(root, weights=b"apache-w"))
    link(home, mf(home, licenses=(LLAMA,), weights=b"llama-w"))
    return "qwen3.5:4b", "OLLAMA_MODELS padded and quoted twice, naming an Apache store; Llama in the home store"


@scenario(clears=True, env=' "" ')
def env_models_empty_after_trim(root):
    home = root.parent / ".ollama" / "models"
    link(home, mf(home))
    return "qwen3.5:4b", 'OLLAMA_MODELS=\' "" \' (empty once trimmed: the home store), Apache there'


@scenario(env="{models}")
def env_models_home_only(root):
    home = root.parent / ".ollama" / "models"
    root.joinpath("blobs").mkdir()
    link(home, mf(home))
    return "qwen3.5:4b", "OLLAMA_MODELS names a store without the model; Apache only in the home store"


# --- N3: a manifest Go's encoding/json cannot decode ------------------------------------------------------------
@scenario
def manifest_utf8_bom(root):
    link(root, b"\xef\xbb\xbf" + mf(root))
    return "qwen3.5:4b", "an Apache manifest written with a UTF-8 BOM"


@scenario
def manifest_utf16(root):
    link(root, mf(root).decode().encode("utf-16"))
    return "qwen3.5:4b", "an Apache manifest written as UTF-16 (with its BOM)"
