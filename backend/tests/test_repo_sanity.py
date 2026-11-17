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
