from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return uuid4().hex


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)


class Task(Base, TimestampMixin):
    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    goal: Mapped[str] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(String(24), default="auto")
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    provider: Mapped[str] = mapped_column(String(32))
    working_directory: Mapped[str] = mapped_column(Text)
    complexity_score: Mapped[float] = mapped_column(Float, default=0)
    summary: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    nodes: Mapped[list["TaskNode"]] = relationship(back_populates="task", cascade="all, delete-orphan")


class TaskNode(Base, TimestampMixin):
    __tablename__ = "task_nodes"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(240))
    instructions: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    depth: Mapped[int] = mapped_column(Integer, default=0)
    dependencies_json: Mapped[str] = mapped_column(Text, default="[]")
    required_capabilities_json: Mapped[str] = mapped_column(Text, default="[]")
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    result: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    task: Mapped[Task] = relationship(back_populates="nodes")


class AgentSession(Base, TimestampMixin):
    __tablename__ = "agent_sessions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    node_id: Mapped[str | None] = mapped_column(ForeignKey("task_nodes.id", ondelete="SET NULL"))
    provider: Mapped[str] = mapped_column(String(32))
    external_id: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(32), default="running")
    input_summary: Mapped[str] = mapped_column(Text)
    output: Mapped[str | None] = mapped_column(Text)
    usage_json: Mapped[str] = mapped_column(Text, default="{}")
    error: Mapped[str | None] = mapped_column(Text)


class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str | None] = mapped_column(String(32), index=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(default=utc_now, index=True)


class Memory(Base, TimestampMixin):
    __tablename__ = "memories"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    scope: Mapped[str] = mapped_column(String(32), default="user", index=True)
    content: Mapped[str] = mapped_column(Text)
    normalized_content: Mapped[str] = mapped_column(Text, index=True)
    source_type: Mapped[str] = mapped_column(String(32))
    source_id: Mapped[str | None] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(24), default="candidate", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    evidence_count: Mapped[int] = mapped_column(Integer, default=1)
    use_count: Mapped[int] = mapped_column(Integer, default=0)
    sensitive: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime | None]


class ProfileClaim(Base, TimestampMixin):
    __tablename__ = "profile_claims"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    category: Mapped[str] = mapped_column(String(64), index=True)
    claim: Mapped[str] = mapped_column(Text)
    evidence_json: Mapped[str] = mapped_column(Text, default="[]")
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    sensitive: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(24), default="candidate", index=True)


class Approval(Base, TimestampMixin):
    __tablename__ = "approvals"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    capability: Mapped[str] = mapped_column(String(80), index=True)
    resource_scope: Mapped[str] = mapped_column(Text)
    risk_level: Mapped[str] = mapped_column(String(16), default="medium")
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    expires_at: Mapped[datetime | None]


class SkillCandidate(Base, TimestampMixin):
    __tablename__ = "skill_candidates"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    bundle_name: Mapped[str] = mapped_column(String(120))
    bundle_path: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="candidate", index=True)
    validation_json: Mapped[str] = mapped_column(Text, default="{}")


class Skill(Base, TimestampMixin):
    __tablename__ = "skills"
    __table_args__ = (UniqueConstraint("bundle_name"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    bundle_name: Mapped[str] = mapped_column(String(120), index=True)
    bundle_path: Mapped[str] = mapped_column(Text)
    source_candidate_id: Mapped[str | None] = mapped_column(String(32))
    use_count: Mapped[int] = mapped_column(Integer, default=0)
