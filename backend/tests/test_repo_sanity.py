"""Clean-clone sanity checks (Phase 0).

These tests guard the repository layout and docs against drifting away from
the code: a README that lists a directory that does not exist, a compose file
that is missing a service the config expects, and so on. They read files only
and need neither a database nor network access.
"""
import re
from pathlib import Path

import yaml

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


def _published_host_ports(service: dict) -> set[str]:
    """Host-side ports from a compose service's `ports:` list."""
    hosts = set()
    for entry in service.get("ports", []):
        parts = str(entry).split(":")
        hosts.add(parts[-2] if len(parts) >= 2 else parts[0])
    return hosts


def test_dev_compose_provides_redis_for_env_example():
    """`.env.example` points REDIS_URL at a local port; dev compose must serve it."""
    env_text = (REPO / ".env.example").read_text(encoding="utf-8")
    match = re.search(r"^REDIS_URL=redis://[^:/\s]+:(\d+)/", env_text, re.M)
    assert match, ".env.example should define REDIS_URL with an explicit port"
    port = match.group(1)

    compose = yaml.safe_load((REPO / "docker-compose.yml").read_text(encoding="utf-8"))
    services = compose.get("services", {})
    assert "redis" in services, "docker-compose.yml has no redis service"
    assert port in _published_host_ports(services["redis"]), (
        f"redis service does not publish host port {port} used by .env.example"
    )


def _alembic_script_dir():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    return ScriptDirectory.from_config(cfg)


def test_alembic_has_a_single_head():
    """Two heads means a forked history and `alembic upgrade head` is ambiguous."""
    heads = _alembic_script_dir().get_heads()
    assert len(heads) == 1, f"expected exactly one alembic head, found {heads}"


def test_migration_docstrings_match_down_revision():
    """The `Revises:` line in each migration docstring must match `down_revision`.

    Alembic only reads the Python variable, so a stale docstring is silently
    wrong and misleads anyone reading the history.
    """
    mismatches = []
    for rev in _alembic_script_dir().walk_revisions():
        doc = rev.module.__doc__ or ""
        found = re.search(r"^Revises:[ \t]*(\S*)[ \t]*$", doc, re.M)
        assert found, f"{rev.revision}: docstring has no 'Revises:' line"
        documented = found.group(1) or None
        if documented != rev.down_revision:
            mismatches.append((rev.revision, documented, rev.down_revision))
    assert not mismatches, (
        "docstring 'Revises:' disagrees with down_revision "
        f"(revision, documented, actual): {mismatches}"
    )
