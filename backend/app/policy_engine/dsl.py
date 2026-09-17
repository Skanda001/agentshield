"""Load, parse, and validate YAML policy documents."""
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from app.schemas.policy import PolicyDocument


class PolicyParseError(Exception):
    """Raised when a YAML policy file cannot be parsed or validated."""


def load_yaml(path: Path | str) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise PolicyParseError(f"Policy file not found: {p}")
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError as e:
        raise PolicyParseError(f"Could not read {p}: {e}") from e

    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as e:
        raise PolicyParseError(f"Invalid YAML in {p}: {e}") from e

    if not isinstance(data, dict):
        raise PolicyParseError(f"Top-level YAML in {p} must be a mapping")

    return data


def validate_document(data: dict[str, Any]) -> PolicyDocument:
    try:
        return PolicyDocument.model_validate(data)
    except ValidationError as e:
        raise PolicyParseError(f"Policy validation failed: {e}") from e


def load_and_validate(path: Path | str) -> PolicyDocument:
    return validate_document(load_yaml(path))