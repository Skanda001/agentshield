"""Clean-clone sanity checks (Phase 0).

These tests guard the repository layout and docs against drifting away from
the code: a README that lists a directory that does not exist, a compose file
that is missing a service the config expects, and so on. They read files only
and need neither a database nor network access.
"""
import re
import tomllib
from pathlib import Path

import yaml
from packaging.requirements import Requirement

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


# --- SDK packaging -----------------------------------------------------------
# These distribution names are owned by other projects on PyPI (checked
# 2026-11-17). If our SDK, or a bare requirement, used one of them, `pip install`
# would pull a stranger's package instead of ours.
FOREIGN_PYPI_NAMES = {
    "agentshield",
    "agentshield-sdk",
    "agentshield-client",
    "agentshield-gateway-sdk",
    "agentshield-guard",
}
SDK_DIR = BACKEND / "sdk" / "python_sdk"
AGENT_DIR = REPO / "agent"


def _canon(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _sdk_dist_name() -> str:
    data = tomllib.loads((SDK_DIR / "pyproject.toml").read_text(encoding="utf-8"))
    return _canon(data["project"]["name"])


def test_sdk_dist_name_does_not_collide_with_foreign_pypi_package():
    assert _sdk_dist_name() not in {_canon(n) for n in FOREIGN_PYPI_NAMES}


def test_agent_requirements_install_sdk_from_local_path_not_pypi():
    lines = [
        raw.split("#")[0].strip()
        for raw in (AGENT_DIR / "requirements.txt").read_text(encoding="utf-8").splitlines()
    ]
    lines = [ln for ln in lines if ln]

    # No bare name that PyPI could resolve to someone else's package.
    unsafe = {_canon(n) for n in FOREIGN_PYPI_NAMES} | {_sdk_dist_name()}
    for ln in lines:
        if ln.startswith(("-", ".", "/")):
            continue
        assert _canon(Requirement(ln).name) not in unsafe, (
            f"agent/requirements.txt resolves {ln!r} from PyPI; install the SDK from its path"
        )

    # ...and the SDK must actually be installed from this repo (path relative to repo root).
    local = [ln for ln in lines if ln.startswith("./")]
    assert any((REPO / ln).resolve() == SDK_DIR.resolve() for ln in local), (
        "agent/requirements.txt must install the SDK from ./backend/sdk/python_sdk"
    )


def test_agent_pyproject_references_sdk_only_by_direct_url():
    data = tomllib.loads((AGENT_DIR / "pyproject.toml").read_text(encoding="utf-8"))
    sdk = _sdk_dist_name()
    unsafe = {_canon(n) for n in FOREIGN_PYPI_NAMES} | {sdk}
    seen_sdk = False
    for dep in data["project"]["dependencies"]:
        req = Requirement(dep)
        name = _canon(req.name)
        if name in unsafe:
            assert name == sdk, f"agent depends on foreign PyPI package {req.name!r}"
            assert req.url, f"{dep!r} must be a direct URL reference, not resolved from PyPI"
            seen_sdk = True
    assert seen_sdk, "agent/pyproject.toml must declare a dependency on the SDK"
