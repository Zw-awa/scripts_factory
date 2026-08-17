from __future__ import annotations

import json

from sqlalchemy.orm import Session

from ..models import Event


def record_event(session: Session, event_type: str, payload: dict, task_id: str | None = None) -> None:
    session.add(Event(task_id=task_id, event_type=event_type, payload_json=json.dumps(payload, ensure_ascii=False)))
