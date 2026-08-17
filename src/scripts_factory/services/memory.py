from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..models import Memory, ProfileClaim, Task


SENSITIVE_MARKERS = ("健康", "疾病", "政治", "宗教", "财务", "收入", "身份证", "住址", "性取向")


def normalize_memory(content: str) -> str:
    return re.sub(r"\s+", " ", content.strip().lower())


def add_memory(
    session: Session,
    *,
    kind: str,
    content: str,
    source_type: str,
    source_id: str | None,
    confidence: float = 0.5,
    importance: float = 0.5,
    sensitive: bool | None = None,
) -> Memory:
    normalized = normalize_memory(content)
    existing = session.scalar(select(Memory).where(Memory.normalized_content == normalized, Memory.kind == kind, Memory.status != "deleted"))
    if existing:
        existing.evidence_count += 1
        existing.confidence = min(1.0, max(existing.confidence, confidence) + 0.05)
        existing.importance = max(existing.importance, importance)
        return existing
    memory = Memory(
        kind=kind,
        content=content,
        normalized_content=normalized,
        source_type=source_type,
        source_id=source_id,
        confidence=confidence,
        importance=importance,
        sensitive=any(marker in content for marker in SENSITIVE_MARKERS) if sensitive is None else sensitive,
    )
    session.add(memory)
    session.flush()
    return memory


def remember_task_result(session: Session, task: Task) -> None:
    add_memory(session, kind="episodic", content=f"任务目标：{task.goal}\n结果：{task.summary or '完成'}", source_type="task", source_id=task.id, confidence=0.7, importance=0.6)
    if task.mode == "planned":
        add_memory(session, kind="workflow", content=f"可复用流程：{task.goal}", source_type="task", source_id=task.id, confidence=0.65, importance=0.75)
    if any(marker in task.goal for marker in ("偏好", "习惯", "以后", "请用", "不要")):
        add_profile_claim(session, "behavior", task.goal, [f"task:{task.id}"], confidence=0.55)


def search_memories(session: Session, query: str, limit: int = 10) -> list[Memory]:
    tokens = re.findall(r"\w+", query, flags=re.UNICODE)
    if not tokens:
        return []
    fts_query = " AND ".join(f'"{token}"' for token in tokens)
    rows = session.execute(
        text("SELECT m.id FROM memory_fts f JOIN memories m ON m.id=f.memory_id WHERE memory_fts MATCH :query AND m.status IN ('candidate','confirmed','active') ORDER BY bm25(memory_fts), m.importance DESC LIMIT :limit"),
        {"query": fts_query, "limit": limit},
    ).all()
    if not rows:
        return []
    ids = [row[0] for row in rows]
    memories = session.scalars(select(Memory).where(Memory.id.in_(ids))).all()
    by_id = {memory.id: memory for memory in memories}
    return [by_id[memory_id] for memory_id in ids if memory_id in by_id]


def promote_memory(session: Session, memory_id: str, user_confirmed: bool = False) -> Memory:
    memory = session.get(Memory, memory_id)
    if not memory:
        raise ValueError(f"Memory not found: {memory_id}")
    if memory.sensitive and not user_confirmed:
        raise ValueError("Sensitive memory requires explicit user confirmation")
    if not user_confirmed and memory.evidence_count < 2:
        raise ValueError("Memory requires repeated evidence or explicit user confirmation")
    memory.status = "active"
    memory.confidence = max(memory.confidence, 0.8)
    return memory


def add_profile_claim(session: Session, category: str, claim: str, evidence: list[str], confidence: float = 0.5) -> ProfileClaim:
    sensitive = any(marker in claim for marker in SENSITIVE_MARKERS)
    profile = ProfileClaim(category=category, claim=claim, evidence_json=__import__("json").dumps(evidence, ensure_ascii=False), confidence=confidence, sensitive=sensitive)
    session.add(profile)
    session.flush()
    return profile


def confirm_profile_claim(session: Session, claim_id: str) -> ProfileClaim:
    claim = session.get(ProfileClaim, claim_id)
    if not claim:
        raise ValueError(f"Profile claim not found: {claim_id}")
    claim.status = "confirmed"
    return claim


def archive_stale_memories(session: Session, max_idle_days: int = 180) -> int:
    now = datetime.now(timezone.utc)
    archived = 0
    for memory in session.scalars(select(Memory).where(Memory.status.in_(["candidate", "active"]))):
        age = (now - memory.updated_at.replace(tzinfo=timezone.utc) if memory.updated_at.tzinfo is None else now - memory.updated_at).days
        if age >= max_idle_days and memory.importance < 0.4 and memory.use_count == 0:
            memory.status = "archived"
            archived += 1
    return archived
