from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_canonical_effect_compiler_and_intent_record_exist() -> None:
    doctrine = _text("docs/FOUNDER_EFFECT_COMPILER.md")
    intent = _text("docs/intent/INTENT-0029-effect-not-metaphor.md")

    assert "Preserve the effect" in doctrine
    assert "Do not literalize" in doctrine
    assert "CapabilityDeficit" in doctrine
    assert "functional capability formation" in doctrine
    assert "INTENT-0029" in intent
    assert "REGRESS THE LITERAL INTERPRETATION" in intent


def test_agent_ingress_surfaces_effect_compiler() -> None:
    for path in (
        "AGENTS.md",
        "CLAUDE.md",
        ".github/copilot-instructions.md",
        "README.md",
        ".github/pull_request_template.md",
    ):
        text = _text(path)
        assert "Preserve the effect" in text, path
        assert "literal" in text.lower(), path


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
