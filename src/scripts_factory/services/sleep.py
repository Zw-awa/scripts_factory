from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select

from ..config import Settings
from ..database import Database
from ..models import Memory, Task
from .memory import archive_stale_memories
from .skills import create_skill_candidate


@dataclass(slots=True)
class SleepReport:
    promoted_memories: int = 0
    archived_memories: int = 0
    skill_candidates: int = 0


def consolidate(database: Database, settings: Settings, task_id: str | None = None) -> SleepReport:
    report = SleepReport()
    with database.session() as session:
        for memory in session.scalars(select(Memory).where(Memory.status == "candidate", Memory.sensitive.is_(False))):
            if memory.evidence_count >= 2 and memory.confidence >= 0.65:
                memory.status = "active"
                report.promoted_memories += 1
        report.archived_memories = archive_stale_memories(session)
        query = select(Task).where(Task.status == "completed", Task.mode == "planned")
        if task_id:
            query = query.where(Task.id == task_id)
        for task in session.scalars(query):
            candidate = create_skill_candidate(session, settings, task)
            if candidate.status == "validated":
                report.skill_candidates += 1
    return report
