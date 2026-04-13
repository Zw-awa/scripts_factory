#!/usr/bin/env python3
"""校验 bundle.spec.json 和 bundles.index.json 的基本结构。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="校验离线 bundle 元数据。")
    parser.add_argument(
        "path",
        type=Path,
        help="单个元数据文件路径，或包含多个 bundle 的目录路径。",
    )
    return parser


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON 解析失败: {path}: {exc}") from exc


def require_string(data: dict, key: str, errors: list[str]) -> None:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"缺少非空字符串字段: {key}")


def require_optional_string(data: dict, key: str, errors: list[str]) -> None:
    value = data.get(key)
    if value is not None and not isinstance(value, str):
        errors.append(f"字段必须为字符串或 null: {key}")


def validate_bundle_spec(path: Path) -> list[str]:
    data = load_json(path)
    errors: list[str] = []

    if data.get("schema") != "offline-script-factory.bundle/v1":
        errors.append("schema 必须是 offline-script-factory.bundle/v1")

    for key in (
        "bundle_name",
        "display_name",
        "purpose",
        "runtime",
        "entry_point",
        "help_command",
        "self_test_command",
    ):
        require_string(data, key, errors)

    if data.get("runtime") not in {"python", "powershell"}:
        errors.append("runtime 必须是 python 或 powershell")

    require_optional_string(data, "config_file", errors)

    if not isinstance(data.get("environment_variables"), list):
        errors.append("environment_variables 必须是数组")

    if not isinstance(data.get("external_dependencies"), list):
        errors.append("external_dependencies 必须是数组")

    if not isinstance(data.get("notes"), list):
        errors.append("notes 必须是数组")

    return errors


def validate_index_file(path: Path) -> list[str]:
    data = load_json(path)
    errors: list[str] = []

    if data.get("schema") != "offline-script-factory.index/v1":
        errors.append("schema 必须是 offline-script-factory.index/v1")

    require_string(data, "root", errors)

    bundle_count = data.get("bundle_count")
    if not isinstance(bundle_count, int) or bundle_count < 0:
        errors.append("bundle_count 必须是非负整数")

    bundles = data.get("bundles")
    if not isinstance(bundles, list):
        errors.append("bundles 必须是数组")
        return errors

    if isinstance(bundle_count, int) and bundle_count != len(bundles):
        errors.append("bundle_count 与 bundles 数量不一致")

    required_entry_keys = (
        "bundle_name",
        "display_name",
        "purpose",
        "runtime",
        "entry_point",
        "help_command",
        "self_test_command",
        "relative_bundle_dir",
        "relative_spec_path",
    )
    for index, entry in enumerate(bundles):
        if not isinstance(entry, dict):
            errors.append(f"bundles[{index}] 必须是对象")
            continue
        for key in required_entry_keys:
            require_string(entry, key, errors)
        require_optional_string(entry, "config_file", errors)

    return errors


def validate_path(path: Path) -> list[tuple[Path, list[str]]]:
    if path.is_file():
        if path.name == "bundle.spec.json":
            return [(path, validate_bundle_spec(path))]
        if path.name == "bundles.index.json":
            return [(path, validate_index_file(path))]
        raise ValueError("仅支持校验 bundle.spec.json 或 bundles.index.json")

    if not path.is_dir():
        raise FileNotFoundError(f"路径不存在: {path}")

    results: list[tuple[Path, list[str]]] = []
    for spec_path in sorted(path.rglob("bundle.spec.json")):
        results.append((spec_path, validate_bundle_spec(spec_path)))
    for index_path in sorted(path.rglob("bundles.index.json")):
        results.append((index_path, validate_index_file(index_path)))

    if not results:
        raise FileNotFoundError(f"目录下未找到 bundle.spec.json 或 bundles.index.json: {path}")

    return results


def main() -> int:
    args = build_parser().parse_args()
    target = args.path.resolve()
    results = validate_path(target)

    failed = 0
    for path, errors in results:
        if errors:
            failed += 1
            print(f"[FAIL] {path}")
            for error in errors:
                print(f"  - {error}")
        else:
            print(f"[ OK ] {path}")

    if failed:
        print(f"校验失败文件数: {failed}", file=sys.stderr)
        return 1

    print(f"校验通过文件数: {len(results)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI surface
        print(f"错误: {exc}", file=sys.stderr)
        raise SystemExit(1)
