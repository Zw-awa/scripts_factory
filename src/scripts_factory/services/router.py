from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RouteDecision:
    mode: str
    score: float
    reasons: list[str]


COMPLEX_MARKERS = ("多个", "分别", "然后", "同时", "重构", "迁移", "系统", "架构", "计划", "并发", "数据库", "API")
RISK_MARKERS = ("删除", "覆盖", "发布", "部署", "推送", "联网", "支付", "权限")


def infer_capabilities(text: str) -> list[str]:
    capabilities = {"filesystem.read"}
    lowered = text.lower()
    if any(marker in lowered for marker in ("写", "生成", "修改", "创建", "覆盖", "write", "create", "modify")):
        capabilities.add("filesystem.write")
    if any(marker in lowered for marker in ("删除", "清理", "remove", "delete")):
        capabilities.add("filesystem.delete")
    if any(marker in lowered for marker in ("联网", "下载", "api", "推送", "发布", "network", "download", "push", "deploy")):
        capabilities.add("network.access")
    return sorted(capabilities)


def route_task(goal: str, requested_mode: str = "auto") -> RouteDecision:
    if requested_mode in {"direct", "planned"}:
        return RouteDecision(requested_mode, 1.0 if requested_mode == "planned" else 0.0, ["user selected mode"])
    reasons: list[str] = []
    score = min(len(goal) / 500, 0.3)
    for marker in COMPLEX_MARKERS:
        if marker.lower() in goal.lower():
            score += 0.12
            reasons.append(f"complex marker: {marker}")
    for marker in RISK_MARKERS:
        if marker.lower() in goal.lower():
            score += 0.08
            reasons.append(f"risk marker: {marker}")
    score = min(score, 1.0)
    return RouteDecision("planned" if score >= 0.35 else "direct", score, reasons or ["short single-focus request"])
