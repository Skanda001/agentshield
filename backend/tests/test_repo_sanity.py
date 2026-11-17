"""Clean-clone sanity checks (Phase 0).

These tests guard the repository layout and docs against drifting away from
the code: a README that lists a directory that does not exist, a compose file
that is missing a service the config expects, and so on. They read files only
and need neither a database nor network access.
"""
import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent


def test_external_agents_readme_lists_only_existing_dirs():
    """Every agent the README advertises as `dir/` must exist on disk."""
    readme = BACKEND / "external_agents" / "README.md"
    text = readme.read_text(encoding="utf-8")

    # Entries look like:  1. **Customer Support Agent** (`customer-support-agent/`):
    listed = re.findall(r"\*\*[^*]+\*\*\s*\(`([^`]+/)`\)", text)
    assert listed, "README should list at least one agent directory"

    missing = [d for d in listed if not (readme.parent / d).is_dir()]
    assert not missing, f"external_agents/README.md lists missing directories: {missing}"
