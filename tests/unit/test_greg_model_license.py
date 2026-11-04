"""Model-weight licenses: the license an installed Ollama model carries, read and held before use (directive of
2026-10-22, section VII: "Model-weight licenses are not yet covered by the acquisition gate").

GREG's local models run through Ollama, which is MIT whatever the weights are. Each pulled model stores its license
as full-text layers in the local store. These tests fix the gate: Apache-2.0 and MIT are cleared only when their
terms are the standard text word for word; model community and responsible-AI licenses (Llama, Gemma, OpenRAIL,
the Qwen research and Tongyi Qianwen agreements, DeepSeek, DeepFloyd, Mistral's non-production and research
licenses, research-only terms) are held by family name in any declaration; anything else, an unreadable or
tampered layer, or no license at all, is held. The verdict is bound to the manifest and weight digests.

Fixtures are byte copies of Debian's /usr/share/common-licenses/Apache-2.0 and GPL-2 and of six 1.17.0's MIT
LICENSE. Real Llama, Gemma and Qwen texts are not fetched (the network policy refuses huggingface.co and
registry.ollama.ai); their title lines stand in for them.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from greg import licensing

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "licenses"
APACHE = (FIXTURES / "Apache-2.0.txt").read_text()
MIT = (FIXTURES / "MIT-six.txt").read_text()
GPL2 = (FIXTURES / "GPL-2.0.txt").read_text()
MODEL_FAMILIES = [
    ("llama2", "LLAMA 2 COMMUNITY LICENSE AGREEMENT"), ("llama3.1", "LLAMA 3.1 COMMUNITY LICENSE AGREEMENT"),
    ("llama4", "Llama 4 Community License Agreement"), ("gemma", "Gemma Terms of Use"),
    ("openrail", "Open RAIL License"), ("openrail++", "CreativeML Open RAIL++-M License"),
    ("creativeml-openrail-m", "CreativeML Open RAIL-M"), ("bigscience-openrail-m", "BigScience Open RAIL-M License"),
    ("bigscience-bloom-rail-1.0", "BigScience RAIL License v1.0"), ("bigcode-openrail-m", "BigCode Open RAIL-M v1"),
    ("tongyi-qianwen", "Tongyi Qianwen LICENSE AGREEMENT"), ("qwen-research", "Qwen RESEARCH LICENSE AGREEMENT"),
    ("deepseek-license", "DEEPSEEK LICENSE AGREEMENT"), ("deepfloyd-if-license", "DEEPFLOYD IF LICENSE AGREEMENT"),
    ("mistral-ai-research-license", "Mistral AI Research License"),
    ("fair-noncommercial-research-license", "Mistral AI Non-Production License"),
    ("cc-by-nc-4.0", "Attribution-NonCommercial 4.0 International"), ("research-only", "For research use only"),
]


def verdict(text):
    return licensing.model_assessment("m", [text], {"model": "m"})


def store(tmp_path, name="registry.ollama.ai/library/qwen3.5/4b", licenses=(APACHE,), weights=b"GGUF weights",
          tamper=False, manifest=None):
    """A local Ollama store holding one model: a manifest, its weights blob and one blob per license."""
    root = tmp_path / "models"
    (root / "blobs").mkdir(parents=True, exist_ok=True)

    def blob(data: bytes) -> str:
        digest = "sha256:" + hashlib.sha256(data).hexdigest()
        (root / "blobs" / digest.replace(":", "-")).write_bytes(b"tampered" if tamper and data != weights else data)
        return digest
    layers = [{"mediaType": "application/vnd.ollama.image.model", "digest": blob(weights), "size": len(weights)}]
    layers += [{"mediaType": licensing.OLLAMA_LICENSE, "digest": blob(t.encode()), "size": len(t)} for t in licenses]
    layers.append({"mediaType": "application/vnd.ollama.image.params", "digest": blob(b"{}"), "size": 2})
    path = root / "manifests" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(manifest if manifest is not None else json.dumps(
        {"schemaVersion": 2, "mediaType": "application/vnd.docker.distribution.manifest.v2+json", "layers": layers}))
    return root


# -- full license texts -----------------------------------------------------------------------------------------

def test_the_standard_apache_and_mit_texts_are_cleared():
    for text, spdx in ((APACHE, "Apache-2.0"), (MIT, "MIT")):
        a = verdict(text)
        assert a["verdict"] == "CLEARED" and not a["held"], a["reason"]
        assert [t["id"] for t in a["parts"][0]["terms"]] == [spdx]


def test_an_apache_text_with_its_appendix_filled_in_or_removed_is_still_cleared():
    filled = APACHE.replace("Copyright [yyyy] [name of copyright owner]", "Copyright 2024 Alibaba Cloud")
    terms_only = APACHE[:APACHE.index("APPENDIX")]
    no_header = APACHE[APACHE.index("TERMS AND CONDITIONS"):]
    for text in (filled, terms_only, no_header):
        assert verdict(text)["verdict"] == "CLEARED"


def test_one_changed_word_in_the_terms_is_not_apache_or_mit():
    """Recognition is by the terms, not the title: an edited Apache or MIT text is unclassified and held."""
    edited = APACHE.replace("non-exclusive", "exclusive", 1)
    narrowed = MIT.replace("sublicense, ", "", 1)
    assert edited != APACHE and narrowed != MIT
    for text in (edited, narrowed):
        a = verdict(text)
        assert a["verdict"] == "FOUNDER_REVIEW" and a["class"] == licensing.UNKNOWN, a["reason"]


def test_terms_added_beside_a_standard_text_are_held():
    commons = '"Commons Clause" License Condition v1.0\n\nThe Software is provided subject to this condition.\n\n'
    trailing = MIT + "\n\nThe weights may not be used to train another model.\n"
    a = verdict(commons + APACHE)
    assert a["held"] and any("commons-clause" in r for r in a["restrictive"]), a["reason"]
    b = verdict(trailing)
    assert b["held"] and "may not be used to train" in b["reason"]


MIT_TERMS_AT = MIT.index("Permission is hereby granted")
SMUGGLED = {
    "mit header": MIT[:MIT_TERMS_AT] + "Copyright 2024 Acme. Licensee shall not use the model to train other models; "
                  "usage is limited to 700 million monthly active users.\n\n" + MIT[MIT_TERMS_AT:],
    "mit header, no full stop": MIT[:MIT_TERMS_AT] + "Copyright 2024 Acme, for research use only\n\n" + MIT[MIT_TERMS_AT:],
    "mit header, no listed word": MIT[:MIT_TERMS_AT] + "Copyright 2024 Acme. Weights are for evaluation and audit "
                                  "purposes.\n\n" + MIT[MIT_TERMS_AT:],
    "apache notice": APACHE.replace("[yyyy] [name of copyright owner]", "2024 Acme. These weights may be used only for "
                                    "research and evaluation, never in production or by any company with over 700 "
                                    "million monthly active users."),
}


@pytest.mark.parametrize("where", SMUGGLED)
def test_terms_written_into_a_copyright_notice_are_held(tmp_path, where):
    """The review of #230 (blocking): a line starting "Copyright" was dropped whatever followed it, and the Apache
    notice's copyright field took 300 characters of anything, so Llama-style terms there CLEARED the weights."""
    root = store(tmp_path, "registry.ollama.ai/library/acme/1b", licenses=(SMUGGLED[where],))
    a = licensing.ollama_model("acme:1b", root)
    assert a["verdict"] == "FOUNDER_REVIEW" and a["held"] and not a["auto_attach"], a["reason"]
    assert "with other terms beside it" in a["reason"]


@pytest.mark.parametrize("line", [
    "Copyright (c) 2016 Nathaniel J. Smith <njs@pobox.com> and other contributors",   # h11
    "Copyright (c) Meta Platforms, Inc. and affiliates.",
    "Copyright (c) Sindre Sorhus <sindresorhus@gmail.com> (https://sindresorhus.com)",
    "Copyright (c) 2015-present, Facebook, Inc.",
    "Copyright 2024 Acme. All rights reserved.",
    "© 2023 The Contributors",
])
def test_a_plain_copyright_notice_beside_the_terms_is_still_cleared(line):
    assert verdict(MIT[:MIT_TERMS_AT] + line + "\n\n" + MIT[MIT_TERMS_AT:])["verdict"] == "CLEARED", line
    holder = line.split(" ", 2)[-1] if line.startswith("Copyright (c)") else line.split(" ", 1)[-1]
    assert verdict(APACHE.replace("[yyyy] [name of copyright owner]", holder))["verdict"] == "CLEARED", holder


@pytest.mark.parametrize("short_id,title", MODEL_FAMILIES)
def test_model_community_and_responsible_ai_licenses_are_held_in_any_declaration(short_id, title):
    """By text title, by Hugging Face short id, and in a DEP-5 file: the same family is not open source."""
    a = verdict(title + "\n\n1. Definitions.\n...")
    assert a["held"] and a["class"] == licensing.NOT_OPEN, (title, a["reason"])
    assert a["categories"] == [licensing.RESTRICTED_USE]
    assert licensing._lookup(short_id, "spdx") == licensing.NOT_OPEN, short_id


def test_a_dep5_file_naming_a_model_license_holds_the_binary_it_once_let_through():
    """Fail-before: on 083c91ea a Debian package declaring Llama-2 terms was unclassified, so under P0 its binary
    kept the behaviour it had before licenses were read (attach)."""
    dep5 = ("Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/\n\n"
            "Files: *\nCopyright: 2023 Example\nLicense: Llama-2-Community\n")
    a = licensing.binary_assessment("llama-weights", dep5)
    assert a["verdict"] == "FOUNDER_REVIEW" and a["held"] and not a["auto_attach"], a


def test_the_gpl2_noncommercial_distribution_clause_is_not_a_use_restriction():
    a = verdict(GPL2)
    assert a["held"] and a["class"] == licensing.UNKNOWN
    assert a["restrictive"] == [], a["restrictive"]


def test_ordinary_words_are_not_model_license_names():
    for text in ("The guardrail and the trail", "rails", "llama.cpp is MIT", "a gemmary of ideas", "commercial use",
                 "copies conveyed occasionally and noncommercially"):
        assert licensing._text_riders(text) == [], text


# -- the local Ollama store -------------------------------------------------------------------------------------

def test_an_installed_model_is_read_from_its_own_store_and_bound_to_its_weights(tmp_path):
    root = store(tmp_path)
    a = licensing.ollama_model("qwen3.5:4b", root)
    assert a["verdict"] == "CLEARED"
    weights = "sha256:" + hashlib.sha256(b"GGUF weights").hexdigest()
    assert a["subject"]["weights"] == [weights] and a["subject"]["model"] == "registry.ollama.ai/library/qwen3.5:4b"
    manifest = (root / "manifests/registry.ollama.ai/library/qwen3.5/4b").read_bytes()
    assert a["subject"]["manifest_sha256"] == hashlib.sha256(manifest).hexdigest()


def test_a_llama_model_is_held_and_the_founder_is_told_why(tmp_path):
    root = store(tmp_path, "registry.ollama.ai/library/llama3.1/8b",
                 licenses=("LLAMA 3.1 COMMUNITY LICENSE AGREEMENT\nLlama 3.1 Version Release Date: July 23, 2024\n",))
    a = licensing.ollama_model("llama3.1:8b", root)
    assert a["verdict"] == "FOUNDER_REVIEW" and a["held"] and not a["auto_attach"]
    assert "llama-3.1" in a["reason"] and "not open source" in a["reason"]


def test_every_license_layer_applies(tmp_path):
    root = store(tmp_path, licenses=(APACHE, "Gemma Terms of Use\n"))
    a = licensing.ollama_model("qwen3.5:4b", root)
    assert a["held"] and len(a["parts"]) == 2 and a["class"] == licensing.NOT_OPEN


def test_a_model_without_a_license_is_held(tmp_path):
    a = licensing.ollama_model("qwen3.5:4b", store(tmp_path, licenses=()))
    assert a["held"] and "declares no license" in a["reason"]


def test_a_license_blob_that_does_not_match_its_digest_is_held(tmp_path):
    a = licensing.ollama_model("qwen3.5:4b", store(tmp_path, tamper=True))
    assert a["held"] and "do not match its digest" in a["reason"]


def test_an_unreadable_manifest_is_held_and_a_missing_model_is_unassessed(tmp_path):
    a = licensing.ollama_model("qwen3.5:4b", store(tmp_path, manifest="{not json"))
    assert a["held"] and "not a readable Ollama manifest" in a["reason"]
    assert licensing.ollama_model("absent:1b", tmp_path / "models") is None


def test_model_names_complete_as_ollama_completes_them_and_never_escape_the_store(tmp_path):
    assert licensing._ollama_parts("qwen3.5") == ("registry.ollama.ai", "library", "qwen3.5", "latest")
    assert licensing._ollama_parts("me/model:q4") == ("registry.ollama.ai", "me", "model", "q4")
    assert licensing._ollama_parts("hf.co/u/r:Q4_K_M") == ("hf.co", "u", "r", "Q4_K_M")
    for bad in ("../x", "a/../b:1", "a/b/c/d", "a:../b", "", "a/./b"):
        assert licensing._ollama_parts(bad) is None, bad
    root = store(tmp_path, "registry.ollama.ai/library/qwen3.5/latest")
    assert licensing.ollama_model("qwen3.5", root)["verdict"] == "CLEARED"


def test_the_store_named_by_ollama_models_is_read(tmp_path, monkeypatch):
    root = store(tmp_path)
    monkeypatch.setenv("OLLAMA_MODELS", str(root))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    assert licensing.ollama_model("qwen3.5:4b")["verdict"] == "CLEARED"


def test_a_fifo_or_link_in_place_of_a_license_blob_is_not_read(tmp_path):
    root = store(tmp_path)
    blob = next(p for p in (root / "blobs").iterdir() if p.read_bytes() == APACHE.encode())
    blob.unlink()
    os.mkfifo(blob)
    assert licensing.ollama_model("qwen3.5:4b", root)["held"]
    blob.unlink()
    (tmp_path / "elsewhere").write_text(APACHE)
    blob.symlink_to(tmp_path / "elsewhere")
    assert licensing.ollama_model("qwen3.5:4b", root)["held"]


# -- use qualification ------------------------------------------------------------------------------------------

def test_use_qualification_reads_a_model_assessment_and_binds_its_weights(tmp_path):
    a = licensing.ollama_model("qwen3.5:4b", store(tmp_path))
    q = licensing.qualify_use([a], licensing.GREG_USE, a["subject"])
    assert q["verdict"] == licensing.COMPATIBLE
    other = licensing.qualify_use([a], licensing.GREG_USE, {**a["subject"], "weights": ["sha256:" + "0" * 64]})
    assert other["assessment_digest"] != q["assessment_digest"]
    held = licensing.ollama_model("llama3.1:8b", store(tmp_path / "b", "registry.ollama.ai/library/llama3.1/8b",
                                                      licenses=("LLAMA 3.1 COMMUNITY LICENSE AGREEMENT\n",)))
    assert licensing.qualify_use([held], licensing.GREG_USE, held["subject"])["verdict"] == licensing.INCOMPATIBLE
