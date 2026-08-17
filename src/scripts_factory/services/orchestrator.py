from __future__ import annotations

import asyncio
import json
from pathlib import Path

from sqlalchemy import select

from ..config import Settings
from ..database import Database
from ..models import AgentSession, Task, TaskNode
from ..providers import Provider, SessionRequest, SessionResult
from .approvals import is_approved
from .events import record_event
from .memory import remember_task_result
from .router import RouteDecision, infer_capabilities, route_task


class Orchestrator:
    def __init__(self, database: Database, settings: Settings, provider: Provider):
        self.database = database
        self.settings = settings
        self.provider = provider

    async def _invoke(self, request: SessionRequest) -> SessionResult:
        try:
            return await asyncio.wait_for(self.provider.run(request), timeout=request.timeout_seconds + 5)
        except TimeoutError:
            return SessionResult(success=False, content="", error="Provider session timed out")
        except Exception as exc:
            return SessionResult(success=False, content="", error=f"Provider error: {exc}")

    async def create_and_run(self, goal: str, working_directory: Path, mode: str = "auto") -> Task:
        decision = route_task(goal, mode)
        if mode == "auto" and 0.25 <= decision.score <= 0.45:
            decision = await self._review_route(goal, working_directory, decision)
        with self.database.session() as session:
            task = Task(goal=goal, mode=decision.mode, status="planning", provider=self.provider.name, working_directory=str(working_directory.resolve()), complexity_score=decision.score)
            session.add(task)
            session.flush()
            record_event(session, "task.created", {"mode": decision.mode, "score": decision.score, "reasons": decision.reasons}, task.id)
            task_id = task.id
        if decision.mode == "planned":
            await self._plan(task_id)
        else:
            with self.database.session() as session:
                session.add(TaskNode(task_id=task_id, title="执行任务", instructions=goal, required_capabilities_json=json.dumps(infer_capabilities(goal))))
        return await self.run(task_id)

    async def _review_route(self, goal: str, working_directory: Path, initial: RouteDecision) -> RouteDecision:
        request = SessionRequest(
            prompt=(
                "判断以下任务应直接执行还是先规划。只输出 JSON，例如 "
                '{"mode":"direct"} 或 {"mode":"planned"}。\n\n任务：' + goal
            ),
            working_directory=working_directory,
            title="route-task",
            model=self.settings.model,
            timeout_seconds=min(self.settings.session_timeout_seconds, 120),
            metadata={"role": "router", "goal": goal, "expected_output": {"mode": ["direct", "planned"]}},
        )
        result = await self._invoke(request)
        mode = result.data.get("mode") if result.success else None
        if result.success and mode is None:
            try:
                parsed = json.loads(result.content)
                mode = parsed.get("mode") if isinstance(parsed, dict) else None
            except json.JSONDecodeError:
                pass
        if mode in {"direct", "planned"}:
            return RouteDecision(mode, initial.score, [*initial.reasons, "provider boundary review"])
        return initial

    async def _plan(self, task_id: str) -> None:
        with self.database.session() as session:
            task = session.get(Task, task_id)
            assert task
            request = SessionRequest(
                prompt=(
                    "把任务拆成有向无环步骤。只输出 JSON 对象，字段 steps 为数组；每项包含 title、instructions、"
                    "dependencies（前置步骤的零基序号数组）和 required_capabilities。\n\n任务：" + task.goal
                ),
                working_directory=Path(task.working_directory),
                title=f"plan-{task.id[:8]}",
                model=self.settings.model,
                timeout_seconds=self.settings.session_timeout_seconds,
                metadata={"role": "planner", "goal": task.goal, "max_nodes": self.settings.max_nodes},
            )
        result = await self._invoke(request)
        if not result.success:
            with self.database.session() as session:
                task = session.get(Task, task_id)
                assert task
                task.status = "failed"
                task.error = result.error or "planner failed"
            return
        steps = result.data.get("steps")
        if not steps:
            try:
                parsed = json.loads(result.content)
                steps = parsed.get("steps") if isinstance(parsed, dict) else None
            except json.JSONDecodeError:
                steps = None
        steps = steps or [{"title": "执行目标", "instructions": result.content or task.goal, "dependencies": [], "required_capabilities": infer_capabilities(task.goal)}]
        with self.database.session() as session:
            for index, step in enumerate(steps[: self.settings.max_nodes]):
                instructions = step.get("instructions", "")
                capabilities = set(step.get("required_capabilities", [])) | set(infer_capabilities(instructions))
                session.add(TaskNode(task_id=task_id, title=step.get("title", f"步骤 {index + 1}"), instructions=instructions, sequence=index, dependencies_json=json.dumps(step.get("dependencies", [])), required_capabilities_json=json.dumps(sorted(capabilities))))
            record_event(session, "task.planned", {"node_count": min(len(steps), self.settings.max_nodes)}, task_id)

    async def run(self, task_id: str) -> Task:
        with self.database.session() as session:
            task = session.get(Task, task_id)
            if not task:
                raise ValueError(f"Task not found: {task_id}")
            if task.status == "failed" and not task.nodes:
                return task
            task.status = "running"
            all_nodes = list(session.scalars(select(TaskNode).where(TaskNode.task_id == task_id).order_by(TaskNode.sequence)))
            nodes = [node for node in all_nodes if node.status != "completed"]
            blocked = []
            for node in nodes:
                capabilities = json.loads(node.required_capabilities_json)
                if any(not is_approved(session, capability, Path(task.working_directory)) for capability in capabilities):
                    node.status = "awaiting_approval"
                    blocked.append(node.id)
            if blocked:
                task.status = "awaiting_approval"
                record_event(session, "task.approval_required", {"nodes": blocked}, task_id)
                return task

        completed_sequences: set[int] = {node.sequence for node in all_nodes if node.status == "completed"}
        semaphore = asyncio.Semaphore(self.settings.max_concurrency)
        pending = {node.id: node for node in nodes}
        while pending:
            ready = [node for node in pending.values() if set(json.loads(node.dependencies_json)).issubset(completed_sequences)]
            if not ready:
                with self.database.session() as session:
                    task = session.get(Task, task_id)
                    assert task
                    task.status = "failed"
                    task.error = "Task graph has unresolved dependencies"
                break
            results = await asyncio.gather(*(self._run_node(task_id, node.id, semaphore) for node in ready))
            for node, success in zip(ready, results, strict=True):
                pending.pop(node.id)
                if success:
                    completed_sequences.add(node.sequence)
                else:
                    pending.clear()
                    break

        with self.database.session() as session:
            task = session.get(Task, task_id)
            assert task
            failed = session.scalar(select(TaskNode).where(TaskNode.task_id == task_id, TaskNode.status == "failed").limit(1))
            if failed:
                task.status = "failed"
                task.error = failed.error
            elif task.status != "awaiting_approval":
                task.status = "completed"
                outputs = [node.result for node in session.scalars(select(TaskNode).where(TaskNode.task_id == task_id).order_by(TaskNode.sequence)) if node.result]
                task.summary = "\n".join(outputs)
                remember_task_result(session, task)
                record_event(session, "task.completed", {"node_count": len(nodes)}, task_id)
            return task

    async def _run_node(self, task_id: str, node_id: str, semaphore: asyncio.Semaphore) -> bool:
        async with semaphore:
            with self.database.session() as session:
                task = session.get(Task, task_id)
                node = session.get(TaskNode, node_id)
                assert task and node
                node.status = "running"
                agent_session = AgentSession(task_id=task_id, node_id=node_id, provider=self.provider.name, input_summary=node.instructions)
                session.add(agent_session)
                session.flush()
                session_id = agent_session.id
                request = SessionRequest(prompt=node.instructions, working_directory=Path(task.working_directory), title=node.title, model=self.settings.model, timeout_seconds=self.settings.session_timeout_seconds, metadata={"task_id": task_id, "node_id": node_id})
            result = await self._invoke(request)
            with self.database.session() as session:
                node = session.get(TaskNode, node_id)
                agent_session = session.get(AgentSession, session_id)
                assert node and agent_session
                agent_session.external_id = result.external_session_id
                agent_session.output = result.content
                agent_session.usage_json = json.dumps(result.usage)
                agent_session.error = result.error
                agent_session.status = "completed" if result.success else "failed"
                node.result = result.content
                node.error = result.error
                node.status = "completed" if result.success else "failed"
                record_event(session, "node.completed" if result.success else "node.failed", {"node_id": node_id, "error": result.error}, task_id)
            return result.success

    async def resume(self, task_id: str) -> Task:
        with self.database.session() as session:
            task = session.get(Task, task_id)
            if not task:
                raise ValueError(f"Task not found: {task_id}")
            if task.status not in {"failed", "awaiting_approval", "cancelled"}:
                raise ValueError(f"Task is not recoverable from status: {task.status}")
            for node in task.nodes:
                if node.status in {"running", "failed", "awaiting_approval"}:
                    node.status = "pending"
                    node.error = None
            task.status = "pending"
            task.error = None
        return await self.run(task_id)
