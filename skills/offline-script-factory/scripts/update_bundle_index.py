#!/usr/bin/env python3
"""扫描 bundle.spec.json 并生成本地 bundle 索引。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成本地离线 bundle 索引。")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="扫描 bundle 的根目录，默认是当前目录。",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="索引输出路径，默认写到 <root>/bundles.index.json。",
    )
    return parser


def load_spec(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"无法解析 JSON: {path}: {exc}") from exc


def build_entry(root: Path, spec_path: Path) -> dict:
    spec = load_spec(spec_path)
    bundle_dir = spec_path.parent

    return {
        "bundle_name": spec.get("bundle_name") or bundle_dir.name,
        "display_name": spec.get("display_name") or bundle_dir.name,
        "purpose": spec.get("purpose"),
        "runtime": spec.get("runtime"),
        "entry_point": spec.get("entry_point"),
        "help_command": spec.get("help_command"),
        "self_test_command": spec.get("self_test_command"),
        "config_file": spec.get("config_file"),
        "relative_bundle_dir": str(bundle_dir.relative_to(root)),
        "relative_spec_path": str(spec_path.relative_to(root)),
    }


def main() -> int:
    args = build_parser().parse_args()
    root = args.root.resolve()
    output = args.output.resolve() if args.output else root / "bundles.index.json"

    if not root.is_dir():
        raise NotADirectoryError(f"扫描根目录不存在: {root}")

    spec_paths = sorted(root.rglob("bundle.spec.json"))
    entries = [build_entry(root, spec_path) for spec_path in spec_paths]
    entries.sort(key=lambda item: item["bundle_name"])

    index = {
        "schema": "offline-script-factory.index/v1",
        "root": str(root),
        "bundle_count": len(entries),
        "bundles": entries,
    }
    output.write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print(f"已写入索引: {output}")
    print(f"bundle 数量: {len(entries)}")
    for entry in entries:
        print(f"- {entry['bundle_name']}: {entry['relative_bundle_dir']}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI surface
        print(f"错误: {exc}", file=sys.stderr)
        raise SystemExit(1)
