from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_structflow_uses_host_native_invocation() -> None:
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    metadata = (ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")

    assert "Host-invoked StructFlow" in skill
    assert "regardless of platform-specific syntax" in skill
    assert "`$structflow` is one optional Codex invocation syntax, not a requirement" in skill
    assert "Do not auto-select this skill merely because" in skill
    assert "allow_implicit_invocation: false" in metadata
