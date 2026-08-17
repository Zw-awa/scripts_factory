from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Approval


LOW_RISK_CAPABILITIES = {"filesystem.read", "metadata.read", "self_test"}


def is_approved(session: Session, capability: str, resource: Path) -> bool:
    if capability in LOW_RISK_CAPABILITIES:
        return True
    now = datetime.now(timezone.utc)
    approvals = session.scalars(select(Approval).where(Approval.capability == capability, Approval.status == "active")).all()
    resolved = resource.resolve()
    for approval in approvals:
        if approval.expires_at and approval.expires_at < now:
            continue
        scope = Path(approval.resource_scope).resolve()
        try:
            resolved.relative_to(scope)
            return True
        except ValueError:
            continue
    return False


def grant_approval(session: Session, capability: str, resource_scope: Path, risk_level: str = "medium") -> Approval:
    approval = Approval(capability=capability, resource_scope=str(resource_scope.resolve()), risk_level=risk_level)
    session.add(approval)
    session.flush()
    return approval
