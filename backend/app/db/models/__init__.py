"""Import every model here so Alembic detects them during autogenerate."""
from app.db.base import Base  # noqa: F401
from app.db.models.tenant import Tenant  # noqa: F401
from app.db.models.agent import Agent  # noqa: F401
from app.db.models.decision import Decision  # noqa: F401
from app.db.models.policy import Policy, PolicyVersion  # noqa: F401
from app.db.models.audit_log import AuditLog  # noqa: F401
from app.db.models.approval import Approval  # noqa: F401