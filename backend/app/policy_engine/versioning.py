"""Version management: hashing, persisting a new version, listing history."""
import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.policy import Policy, PolicyVersion
from app.schemas.policy import PolicyDocument


def canonical_hash(document: dict[str, Any]) -> str:
    """Stable SHA-256 of the policy document (sorted keys, no whitespace)."""
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def create_policy_version(
    db: AsyncSession,
    *,
    policy: Policy,
    document: PolicyDocument,
) -> PolicyVersion:
    next_version = policy.current_version + 1
    doc_dict = document.model_dump()

    version = PolicyVersion(
        policy_id=policy.id,
        version=next_version,
        document=doc_dict,
        document_hash=canonical_hash(doc_dict),
    )
    db.add(version)

    policy.current_version = next_version
    await db.commit()
    await db.refresh(version)
    await db.refresh(policy)
    return version


async def list_versions(
    db: AsyncSession, policy_id
) -> list[PolicyVersion]:
    result = await db.execute(
        select(PolicyVersion)
        .where(PolicyVersion.policy_id == policy_id)
        .order_by(PolicyVersion.version.desc())
    )
    return list(result.scalars().all())


async def get_version(
    db: AsyncSession, policy_id, version: int
) -> PolicyVersion | None:
    result = await db.execute(
        select(PolicyVersion).where(
            PolicyVersion.policy_id == policy_id,
            PolicyVersion.version == version,
        )
    )
    return result.scalar_one_or_none()