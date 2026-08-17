from __future__ import annotations

import re

from .base import Provider, SessionRequest, SessionResult
from ..services.router import infer_capabilities


class FakeProvider(Provider):
    name = "fake"

    async def healthcheck(self) -> tuple[bool, str]:
        return True, "deterministic fake provider"

    async def run(self, request: SessionRequest) -> SessionResult:
        if request.metadata.get("role") == "router":
            goal = str(request.metadata.get("goal", request.prompt))
            planned = len(goal) > 80 or any(marker in goal for marker in ("然后", "同时", "系统", "架构"))
            return SessionResult(success=True, content="复杂度复核完成。", data={"mode": "planned" if planned else "direct"})
        if request.metadata.get("role") == "planner":
            goal = str(request.metadata.get("goal", request.prompt))
            fragments = [item.strip() for item in re.split(r"[，,；;。]", goal) if item.strip()]
            count = min(max(len(fragments), 2), 4)
            steps = [
                {
                    "title": f"步骤 {index + 1}",
                    "instructions": fragment if index < len(fragments) else f"完成目标的第 {index + 1} 个阶段",
                    "dependencies": [] if index == 0 else [index - 1],
                    "required_capabilities": infer_capabilities(fragment),
                }
                for index, fragment in enumerate((fragments + [goal] * count)[:count])
            ]
            return SessionResult(success=True, content="已生成任务计划。", data={"steps": steps})
        return SessionResult(
            success=True,
            content=f"已完成：{request.prompt}",
            external_session_id=request.external_session_id or f"fake-{abs(hash(request.title))}",
        )
