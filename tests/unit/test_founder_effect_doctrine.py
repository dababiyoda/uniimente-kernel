from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _assert_effect_not_metaphor(text: str, source: str) -> None:
    lowered = text.lower()
    assert "effect" in lowered, source
    assert "literal" in lowered, source
    assert "metaphor" in lowered, source
    assert "preserve" in lowered, source


def test_canonical_effect_compiler_and_intent_record_exist() -> None:
    doctrine = _text("docs/FOUNDER_EFFECT_COMPILER.md")
    intent = _text("docs/intent/INTENT-0030-effect-not-metaphor.md")

    _assert_effect_not_metaphor(doctrine, "FOUNDER_EFFECT_COMPILER")
    assert "CapabilityDeficit" in doctrine
    assert "functional capability formation" in doctrine
    assert "INTENT-0030" in intent
    assert "REGRESS THE LITERAL INTERPRETATION" in intent


def test_agent_ingress_surfaces_effect_compiler() -> None:
    for path in (
        "AGENTS.md",
        "CLAUDE.md",
        ".github/copilot-instructions.md",
        "README.md",
        ".github/pull_request_template.md",
    ):
        _assert_effect_not_metaphor(_text(path), path)


def test_related_architecture_is_subordinate_to_effect() -> None:
    developmental = _text("developmental/README.md")
    morphogenesis = _text("morphogenesis/README.md")
    omnimorph = _text("omnimorph/README.md")
    foundry = _text("foundry/README.md")
    execution = _text("docs/CANONICAL_EXECUTION_ORDER.md")

    assert "Mechanism Research Laboratory" in developmental
    assert "not the canonical definition" in morphogenesis
    assert "optional organization-design" in omnimorph
    assert "mechanism anatomy atlas" in foundry
    assert "Compile founder intent into an effect" in execution


def test_doctrine_preserves_authority_separation() -> None:
    doctrine = _text("docs/FOUNDER_EFFECT_COMPILER.md")
    assert "Building software does not authorize installation" in doctrine
    assert "Installation does not authorize activation" in doctrine
    assert "Activation does not grant consequence authority" in doctrine
    assert "Alfonso remains root human authority" in doctrine


def test_effect_intent_id_does_not_collide_with_open_igc_allocation() -> None:
    doctrine = _text("docs/FOUNDER_EFFECT_COMPILER.md")
    ledger = _text("docs/FOUNDER_INTENT_LEDGER.md")
    assert "INTENT-0030-effect-not-metaphor.md" in doctrine
    assert "`INTENT-0030`" in ledger
    assert not (ROOT / "docs/intent/INTENT-0029-effect-not-metaphor.md").exists()
