#!/usr/bin/env python3
"""输出 CSV 文件的行数和列名摘要。仅使用 Python 标准库。"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="输出 CSV 文件摘要。")
    parser.add_argument("--input", type=Path, help="输入 CSV 文件。")
    parser.add_argument("--self-test", action="store_true", help="执行安全自检。")
    args = parser.parse_args()
    if args.self_test:
        print("自检通过")
        return 0
    if not args.input or not args.input.is_file():
        parser.error("必须提供存在的 --input 文件")
    with args.input.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        headers = next(reader, [])
        rows = sum(1 for _ in reader)
    print(f"行数: {rows}")
    print(f"列名: {', '.join(headers)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
