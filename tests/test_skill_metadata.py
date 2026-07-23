from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_structflow_is_a_self_contained_final_skill() -> None:
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    metadata = (ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")

    assert "Evidence-first structural research" in skill
    assert "## Invocation contract" not in skill
    assert "original StructFlow" not in skill
    assert "allow_implicit_invocation: true" in metadata


def test_public_readme_defers_to_skill_contract() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "[SKILL.md](SKILL.md)" in readme
    assert "execution contract lives exclusively" in readme
    assert "not a second instruction set" in readme


def test_development_documents_are_not_distributed() -> None:
    removed = {
        "CLI.md",
        "RESEARCH_INTEGRITY.md",
        "RESOURCE_ACQUISITION.md",
        "WORKSPACE.md",
        "search_spec.md",
        "spec.md",
        "V2.1.md",
        "V2.2.md",
        "requirements.txt",
    }

    assert not {name for name in removed if (ROOT / name).exists()}
