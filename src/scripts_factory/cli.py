from __future__ import annotations

import asyncio
import json
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer
from sqlalchemy import select

from .config import Settings
from .database import Database, initialize_database
from .models import Approval, Memory, ProfileClaim, Skill, SkillCandidate, Task, TaskNode
from .providers import build_provider
from .services.approvals import grant_approval
from .services.memory import confirm_profile_claim, promote_memory, search_memories
from .services.orchestrator import Orchestrator
from .services.router import route_task
from .services.skills import promote_skill_candidate
from .services.sleep import consolidate


app = typer.Typer(help="本地优先的 AI 任务、记忆与能力中枢。", no_args_is_help=True)
task_app = typer.Typer(help="创建、查看和恢复任务。", no_args_is_help=True)
memory_app = typer.Typer(help="检索和管理记忆。", no_args_is_help=True)
profile_app = typer.Typer(help="审核用户画像候选。", no_args_is_help=True)
skill_app = typer.Typer(help="管理 skill 候选和正式 bundle。", no_args_is_help=True)
approval_app = typer.Typer(help="管理能力与资源范围审批。", no_args_is_help=True)
config_app = typer.Typer(help="查看和校验配置。", no_args_is_help=True)
app.add_typer(task_app, name="task")
app.add_typer(memory_app, name="memory")
app.add_typer(profile_app, name="profile")
app.add_typer(skill_app, name="skill")
app.add_typer(approval_app, name="approval")
app.add_typer(config_app, name="config")


def context(config: Path | None = None) -> tuple[Settings, Database]:
    settings = Settings.load(config)
    settings.ensure_directories()
    database = Database(settings.database_path)
    initialize_database(database.engine)
    return settings, database


def short(value: str | None, length: int = 100) -> str:
    value = value or ""
    return value if len(value) <= length else value[: length - 3] + "..."


@app.command("init")
def init_command(config: Annotated[Path | None, typer.Option("--config")] = None, dry_run: bool = False) -> None:
    if dry_run:
        settings = Settings.load(config)
        typer.echo(f"演练模式：将初始化 {settings.home}")
        return
    settings, database = context(config)
    typer.echo(f"已初始化: {settings.home}")
    typer.echo(f"数据库: {settings.database_path}")
    typer.echo(f"bundle: {settings.bundles_dir}")
    database.engine.dispose()


@task_app.command("run")
def task_run(
    goal: Annotated[str, typer.Argument(help="要完成的目标。")],
    directory: Annotated[Path, typer.Option("--directory", "-C")] = Path.cwd(),
    mode: Annotated[str, typer.Option(help="auto、direct 或 planned。")] = "auto",
    provider_name: Annotated[str | None, typer.Option("--provider")] = None,
    config: Annotated[Path | None, typer.Option("--config")] = None,
    dry_run: bool = False,
) -> None:
    if mode not in {"auto", "direct", "planned"}:
        raise typer.BadParameter("mode 必须是 auto、direct 或 planned")
    if dry_run:
        decision = route_task(goal, mode)
        typer.echo(json.dumps({"action": "task.run", "mode": decision.mode, "score": decision.score, "directory": str(directory.resolve()), "provider": provider_name or Settings.load(config).provider}, ensure_ascii=False, indent=2))
        return
    settings, database = context(config)
    provider = build_provider(provider_name or settings.provider)
    task = asyncio.run(Orchestrator(database, settings, provider).create_and_run(goal, directory, mode))
    typer.echo(json.dumps({"id": task.id, "status": task.status, "mode": task.mode, "summary": task.summary, "error": task.error}, ensure_ascii=False, indent=2))


@task_app.command("list")
def task_list(config: Annotated[Path | None, typer.Option("--config")] = None) -> None:
    _, database = context(config)
    with database.session() as session:
        for task in session.scalars(select(Task).order_by(Task.created_at.desc())):
            typer.echo(f"{task.id}  {task.status:18} {task.mode:8} {short(task.goal)}")


@task_app.command("show")
def task_show(task_id: str, config: Annotated[Path | None, typer.Option("--config")] = None) -> None:
    _, database = context(config)
    with database.session() as session:
        task = session.get(Task, task_id)
        if not task:
            raise typer.BadParameter(f"未找到任务: {task_id}")
        payload = {"id": task.id, "goal": task.goal, "status": task.status, "mode": task.mode, "provider": task.provider, "summary": task.summary, "error": task.error, "nodes": [{"id": node.id, "title": node.title, "status": node.status, "result": node.result, "error": node.error} for node in sorted(task.nodes, key=lambda item: item.sequence)]}
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


@task_app.command("resume")
def task_resume(task_id: str, config: Annotated[Path | None, typer.Option("--config")] = None, dry_run: bool = False) -> None:
    if dry_run:
        typer.echo(f"演练模式：将恢复任务 {task_id}")
        return
    settings, database = context(config)
    task = asyncio.run(Orchestrator(database, settings, build_provider(settings.provider)).resume(task_id))
    typer.echo(f"{task.id}: {task.status}")


@task_app.command("cancel")
def task_cancel(task_id: str, config: Annotated[Path | None, typer.Option("--config")] = None, dry_run: bool = False) -> None:
    if dry_run:
        typer.echo(f"演练模式：将取消任务 {task_id}")
        return
    _, database = context(config)
    with database.session() as session:
        task = session.get(Task, task_id)
        if not task:
            raise typer.BadParameter(f"未找到任务: {task_id}")
        task.status = "cancelled"
        for node in task.nodes:
            if node.status in {"pending", "running", "awaiting_approval"}:
                node.status = "cancelled"
    typer.echo(f"已取消任务: {task_id}")


@memory_app.command("list")
@memory_app.command("review")
def memory_list(status: str | None = None, config: Annotated[Path | None, typer.Option("--config")] = None) -> None:
    _, database = context(config)
    with database.session() as session:
        query = select(Memory).order_by(Memory.updated_at.desc())
        if status:
            query = query.where(Memory.status == status)
        for memory in session.scalars(query):
            typer.echo(f"{memory.id} {memory.status:10} {memory.kind:10} evidence={memory.evidence_count} {short(memory.content)}")


@memory_app.command("search")
def memory_search(query: str, limit: int = 10, config: Annotated[Path | None, typer.Option("--config")] = None) -> None:
    _, database = context(config)
    with database.session() as session:
        for memory in search_memories(session, query, limit):
            typer.echo(f"{memory.id} {memory.status:10} {memory.kind:10} {memory.content}")


@memory_app.command("promote")
def memory_promote(memory_id: str, confirm: Annotated[bool, typer.Option("--confirm")] = False, config: Annotated[Path | None, typer.Option("--config")] = None, dry_run: bool = False) -> None:
    if dry_run:
        typer.echo(f"演练模式：将晋升记忆 {memory_id}")
        return
    _, database = context(config)
    with database.session() as session:
        memory = promote_memory(session, memory_id, user_confirmed=confirm)
        typer.echo(f"已晋升记忆: {memory.id}")


@memory_app.command("archive")
def memory_archive(memory_id: str, config: Annotated[Path | None, typer.Option("--config")] = None, dry_run: bool = False) -> None:
    if dry_run:
        typer.echo(f"演练模式：将归档记忆 {memory_id}")
        return
    _set_memory_status(memory_id, "archived", config)


@memory_app.command("delete")
def memory_delete(memory_id: str, config: Annotated[Path | None, typer.Option("--config")] = None, dry_run: bool = False) -> None:
    if dry_run:
        typer.echo(f"演练模式：将删除记忆 {memory_id}")
        return
    _set_memory_status(memory_id, "deleted", config)


def _set_memory_status(memory_id: str, status: str, config: Path | None) -> None:
    _, database = context(config)
    with database.session() as session:
        memory = session.get(Memory, memory_id)
        if not memory:
            raise typer.BadParameter(f"未找到记忆: {memory_id}")
        memory.status = status
    typer.echo(f"记忆状态已更新: {status}")


@profile_app.command("show")
@profile_app.command("review")
def profile_show(config: Annotated[Path | None, typer.Option("--config")] = None) -> None:
    _, database = context(config)
    with database.session() as session:
        for claim in session.scalars(select(ProfileClaim).order_by(ProfileClaim.created_at.desc())):
            typer.echo(f"{claim.id} {claim.status:10} sensitive={claim.sensitive} [{claim.category}] {claim.claim}")


@profile_app.command("confirm")
def profile_confirm(claim_id: str, config: Annotated[Path | None, typer.Option("--config")] = None, dry_run: bool = False) -> None:
    if dry_run:
        typer.echo(f"演练模式：将确认画像 {claim_id}")
        return
    _, database = context(config)
    with database.session() as session:
        claim = confirm_profile_claim(session, claim_id)
        typer.echo(f"已确认画像: {claim.id}")


@profile_app.command("delete")
def profile_delete(claim_id: str, config: Annotated[Path | None, typer.Option("--config")] = None, dry_run: bool = False) -> None:
    if dry_run:
        typer.echo(f"演练模式：将删除画像 {claim_id}")
        return
    _, database = context(config)
    with database.session() as session:
        claim = session.get(ProfileClaim, claim_id)
        if not claim:
            raise typer.BadParameter(f"未找到画像: {claim_id}")
        session.delete(claim)
    typer.echo(f"已删除画像: {claim_id}")


@approval_app.command("grant")
def approval_grant(capability: str, resource: Path, risk: str = "medium", config: Annotated[Path | None, typer.Option("--config")] = None, dry_run: bool = False) -> None:
    if dry_run:
        typer.echo(f"演练模式：将授权 {capability} 到 {resource.resolve()}")
        return
    _, database = context(config)
    with database.session() as session:
        approval = grant_approval(session, capability, resource, risk)
        typer.echo(f"已授权: {approval.id}")


@approval_app.command("list")
def approval_list(config: Annotated[Path | None, typer.Option("--config")] = None) -> None:
    _, database = context(config)
    with database.session() as session:
        for approval in session.scalars(select(Approval).order_by(Approval.created_at.desc())):
            typer.echo(f"{approval.id} {approval.status:8} {approval.capability} {approval.resource_scope}")


@approval_app.command("revoke")
def approval_revoke(approval_id: str, config: Annotated[Path | None, typer.Option("--config")] = None, dry_run: bool = False) -> None:
    if dry_run:
        typer.echo(f"演练模式：将撤销授权 {approval_id}")
        return
    _, database = context(config)
    with database.session() as session:
        approval = session.get(Approval, approval_id)
        if not approval:
            raise typer.BadParameter(f"未找到授权: {approval_id}")
        approval.status = "revoked"
    typer.echo(f"已撤销授权: {approval_id}")


@app.command("sleep")
def sleep_command(task_id: str | None = None, dry_run: bool = False, config: Annotated[Path | None, typer.Option("--config")] = None) -> None:
    settings, database = context(config)
    if dry_run:
        typer.echo("演练模式：将整理候选记忆、归档低价值记忆，并为已完成复杂任务生成 skill 候选。")
        return
    report = consolidate(database, settings, task_id)
    typer.echo(json.dumps(asdict(report), ensure_ascii=False, indent=2))


@skill_app.command("list")
def skill_list(config: Annotated[Path | None, typer.Option("--config")] = None) -> None:
    _, database = context(config)
    with database.session() as session:
        for skill in session.scalars(select(Skill).order_by(Skill.created_at.desc())):
            typer.echo(f"{skill.id} {skill.bundle_name} {skill.bundle_path}")


@skill_app.command("review")
def skill_review(candidate_id: str | None = None, config: Annotated[Path | None, typer.Option("--config")] = None) -> None:
    _, database = context(config)
    with database.session() as session:
        query = select(SkillCandidate).order_by(SkillCandidate.created_at.desc())
        if candidate_id:
            query = query.where(SkillCandidate.id == candidate_id)
        for candidate in session.scalars(query):
            typer.echo(json.dumps({"id": candidate.id, "task_id": candidate.task_id, "name": candidate.bundle_name, "path": candidate.bundle_path, "status": candidate.status, "validation": json.loads(candidate.validation_json)}, ensure_ascii=False, indent=2))


@skill_app.command("promote")
def skill_promote(candidate_id: str, confirm: Annotated[bool, typer.Option("--confirm")] = False, config: Annotated[Path | None, typer.Option("--config")] = None, dry_run: bool = False) -> None:
    if dry_run:
        typer.echo(f"演练模式：将发布 skill 候选 {candidate_id}")
        return
    if not confirm:
        raise typer.BadParameter("正式发布 skill 必须提供 --confirm")
    settings, database = context(config)
    with database.session() as session:
        skill = promote_skill_candidate(session, settings, candidate_id)
        typer.echo(f"已发布 skill: {skill.bundle_path}")


@skill_app.command("reject")
def skill_reject(candidate_id: str, config: Annotated[Path | None, typer.Option("--config")] = None, dry_run: bool = False) -> None:
    if dry_run:
        typer.echo(f"演练模式：将拒绝 skill 候选 {candidate_id}")
        return
    _, database = context(config)
    with database.session() as session:
        candidate = session.get(SkillCandidate, candidate_id)
        if not candidate:
            raise typer.BadParameter(f"未找到候选: {candidate_id}")
        candidate.status = "rejected"
    typer.echo(f"已拒绝候选: {candidate_id}")


@config_app.command("show")
def config_show(config: Annotated[Path | None, typer.Option("--config")] = None) -> None:
    settings = Settings.load(config)
    typer.echo(json.dumps(settings.public_dict(), ensure_ascii=False, indent=2))


@config_app.command("validate")
def config_validate(config: Annotated[Path | None, typer.Option("--config")] = None) -> None:
    settings = Settings.load(config)
    settings.validate()
    typer.echo("配置有效")


@app.command("doctor")
def doctor(config: Annotated[Path | None, typer.Option("--config")] = None) -> None:
    settings, database = context(config)
    with database.engine.connect() as connection:
        checks = {"database": connection.exec_driver_sql("SELECT 1").scalar() == 1, "fts5": connection.exec_driver_sql("SELECT count(*) FROM memory_fts").scalar() >= 0, "opencode": bool(shutil.which("opencode")), "openai_key": bool(__import__("os").environ.get("OPENAI_API_KEY")), "provider": settings.provider}
    typer.echo(json.dumps(checks, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    app()
