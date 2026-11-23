"""
FinBridge - Top-Level Smoke Tests
Verifies that core modules, configurations, and directory structures conform to standards.
"""
from pathlib import Path


def test_repository_structure_complete():
    """Verify that all mandatory repository directories and files exist."""
    root = Path(__file__).resolve().parent.parent

    # Key directories
    assert (root / "backend").is_dir(), "backend directory missing"
    assert (root / "frontend").is_dir(), "frontend directory missing"
    assert (root / "docs").is_dir(), "docs directory missing"
    assert (root / "infrastructure").is_dir(), "infrastructure directory missing"
    assert (root / "scripts").is_dir(), "scripts directory missing"
    assert (root / "tests").is_dir(), "tests directory missing"

    # Key files
    assert (root / "README.md").is_file(), "README.md missing"
    assert (root / ".gitignore").is_file(), ".gitignore missing"
    assert (root / ".env.example").is_file(), ".env.example missing"
    assert (root / "docker-compose.yml").is_file(), "docker-compose.yml missing"


def test_no_hardcoded_secrets_in_env_example():
    """Verify .env.example contains placeholder values rather than actual secrets."""
    root = Path(__file__).resolve().parent.parent
    env_example = root / ".env.example"
    assert env_example.is_file()

    content = env_example.read_text(encoding="utf-8")
    assert "sk-" not in content, "Possible live OpenAI key detected in .env.example"
    assert "CHANGE_ME" in content.upper() or "YOUR-" in content.upper(), "Expected placeholders in .env.example"
