from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from sqlalchemy import select

from scripts_factory.config import Settings
from scripts_factory.database import Database, initialize_database
from scripts_factory.models import Memory, Skill, SkillCandidate
from scripts_factory.providers.fake import FakeProvider
from scripts_factory.providers.base import Provider, SessionRequest, SessionResult
from scripts_factory.services.approvals import grant_approval
from scripts_factory.services.memory import add_memory, add_profile_claim, confirm_profile_claim, promote_memory, search_memories
from scripts_factory.services.orchestrator import Orchestrator
from scripts_factory.services.sleep import consolidate
from scripts_factory.services.skills import promote_skill_candidate


@pytest.fixture()
def runtime(tmp_path: Path) -> tuple[Settings, Database]:
    settings = Settings(
        home=tmp_path,
        database_path=tmp_path / "state.db",
        bundles_dir=tmp_path / "bundles",
        candidates_dir=tmp_path / "candidates",
        provider="fake",
    )
    settings.ensure_directories()
    database = Database(settings.database_path)
    initialize_database(database.engine)
    return settings, database


def test_direct_task_creates_memory(runtime: tuple[Settings, Database], tmp_path: Path) -> None:
    settings, database = runtime
    task = asyncio.run(Orchestrator(database, settings, FakeProvider()).create_and_run("读取项目说明", tmp_path, "direct"))
    assert task.status == "completed"
    with database.session() as session:
        assert session.scalar(select(Memory).where(Memory.source_id == task.id)) is not None


def test_planned_task_generates_validated_skill_candidate(runtime: tuple[Settings, Database], tmp_path: Path) -> None:
    settings, database = runtime
    with database.session() as session:
        grant_approval(session, "filesystem.write", tmp_path)
    task = asyncio.run(Orchestrator(database, settings, FakeProvider()).create_and_run("分析文件，然后生成报表，并验证结果", tmp_path, "planned"))
    assert task.status == "completed"
    report = consolidate(database, settings, task.id)
    assert report.skill_candidates == 1
    with database.session() as session:
        candidate = session.scalar(select(SkillCandidate).where(SkillCandidate.task_id == task.id))
        assert candidate is not None
        assert candidate.status == "validated"
        assert Path(candidate.bundle_path, "bundle.spec.json").is_file()
        skill = promote_skill_candidate(session, settings, candidate.id)
        assert session.get(Skill, skill.id) is not None
        assert Path(skill.bundle_path, "bundle.spec.json").is_file()
        assert Path(settings.bundles_dir, "bundles.index.json").is_file()


def test_memory_requires_evidence_or_confirmation(runtime: tuple[Settings, Database]) -> None:
    _, database = runtime
    with database.session() as session:
        memory_id = add_memory(session, kind="preference", content="用户偏好中文输出", source_type="test", source_id="1").id
    with pytest.raises(ValueError):
        with database.session() as session:
            promote_memory(session, memory_id)
    with database.session() as session:
        assert promote_memory(session, memory_id, user_confirmed=True).status == "active"


def test_fts_search(runtime: tuple[Settings, Database]) -> None:
    _, database = runtime
    with database.session() as session:
        add_memory(session, kind="workflow", content="生成月度 CSV 报表", source_type="test", source_id="2")
    with database.session() as session:
        assert len(search_memories(session, "CSV")) == 1


def test_task_waits_for_approval_and_resumes(runtime: tuple[Settings, Database], tmp_path: Path) -> None:
    settings, database = runtime
    orchestrator = Orchestrator(database, settings, FakeProvider())
    task = asyncio.run(orchestrator.create_and_run("生成一个本地结果文件", tmp_path, "direct"))
    assert task.status == "awaiting_approval"
    with database.session() as session:
        grant_approval(session, "filesystem.write", tmp_path)
    assert asyncio.run(orchestrator.resume(task.id)).status == "completed"


def test_sensitive_profile_stays_candidate_until_confirmation(runtime: tuple[Settings, Database]) -> None:
    _, database = runtime
    with database.session() as session:
        claim = add_profile_claim(session, "personal", "用户的健康习惯", ["explicit-test"])
        claim_id = claim.id
        assert claim.sensitive is True
        assert claim.status == "candidate"
    with database.session() as session:
        assert confirm_profile_claim(session, claim_id).status == "confirmed"


class BrokenProvider(Provider):
    name = "broken"

    async def healthcheck(self) -> tuple[bool, str]:
        return False, "broken"

    async def run(self, request: SessionRequest) -> SessionResult:
        raise RuntimeError("simulated provider failure")


def test_provider_exception_becomes_failed_task(runtime: tuple[Settings, Database], tmp_path: Path) -> None:
    settings, database = runtime
    task = asyncio.run(Orchestrator(database, settings, BrokenProvider()).create_and_run("读取文件", tmp_path, "direct"))
    assert task.status == "failed"
    assert "simulated provider failure" in (task.error or "")
