#!/usr/bin/env python3
"""创建一个最小离线脚本骨架，供后续补充真实逻辑。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

BASE_SPEC_NOTES = [
    "请优先把外部工具路径放进配置文件、环境变量或单独路径配置，不要散落硬编码在源码里。",
]


PYTHON_TEMPLATE = """#!/usr/bin/env python3
\"\"\"__TITLE__。

请把脚手架逻辑替换成真实业务逻辑。
\"\"\"

from __future__ import annotations

import argparse
import json
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="__TITLE__",
        epilog="示例: python __SCRIPT_NAME__ --input 输入.txt --output 输出.txt --dry-run",
    )
    parser.add_argument("--input", dest="input_path", help="输入文件或目录路径。")
    parser.add_argument("--output", dest="output_path", help="输出文件或目录路径。")
    parser.add_argument("--config", dest="config_path", help="可选 JSON 配置文件路径。")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="执行内置安全自检，不依赖真实业务输入。",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅打印计划，不写入任何变更。",
    )
    return parser


def load_config(config_path: str | None) -> dict:
    if not config_path:
        return {}

    path = Path(config_path)
    if not path.is_file():
        raise FileNotFoundError(f"未找到配置文件: {path}")

    return json.loads(path.read_text(encoding="utf-8"))


def run_self_test() -> int:
    print("自检通过：请将此处替换成真实校验逻辑。")
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    config = load_config(args.config_path)

    if args.self_test:
        return run_self_test()

    if args.dry_run:
        print("演练模式：请将此处替换成真实业务步骤。")
        print(f"输入: {args.input_path!r}")
        print(f"输出: {args.output_path!r}")
        print(f"配置项: {sorted(config)}")
        return 0

    print("脚手架已生成，请把 main() 替换成真实流程。")
    print(f"输入: {args.input_path!r}")
    print(f"输出: {args.output_path!r}")
    print(f"配置项: {sorted(config)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""


POWERSHELL_TEMPLATE = """<#
.SYNOPSIS
__TITLE__

.DESCRIPTION
请把脚手架逻辑替换成真实业务逻辑。

.PARAMETER InputPath
输入文件或目录路径。

.PARAMETER OutputPath
输出文件或目录路径。

.PARAMETER ConfigPath
可选 JSON 配置文件路径。

.PARAMETER SelfTest
执行内置安全自检，不依赖真实业务输入。

.PARAMETER DryRun
仅打印计划，不写入任何变更。

.PARAMETER Help
显示当前脚本的简要用法说明。

.EXAMPLE
./__SCRIPT_NAME__ -InputPath .\\输入.txt -OutputPath .\\输出.txt -DryRun
#>
[CmdletBinding()]
param(
    [string]$InputPath,
    [string]$OutputPath,
    [string]$ConfigPath,
    [switch]$Help,
    [switch]$SelfTest,
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Show-Usage {
    @"
用法:
  ./__SCRIPT_NAME__ [-InputPath <路径>] [-OutputPath <路径>] [-ConfigPath <路径>] [-Help] [-SelfTest] [-DryRun]

说明:
  -Help      显示本帮助
  -SelfTest  运行安全自检
  -DryRun    仅打印计划，不执行真实改动

示例:
  ./__SCRIPT_NAME__ -InputPath .\\输入.txt -OutputPath .\\输出.txt -DryRun
  Get-Help ./__SCRIPT_NAME__ -Detailed
"@ | Write-Host
}

function Read-Config {
    param([string]$Path)

    if (-not $Path) {
        return @{}
    }

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "未找到配置文件: $Path"
    }

    return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json -AsHashtable
}

$config = Read-Config -Path $ConfigPath

if ($Help) {
    Show-Usage
    exit 0
}

if ($SelfTest) {
    Write-Host "自检通过：请将此处替换成真实校验逻辑。"
    exit 0
}

if ($DryRun) {
    Write-Host "演练模式：请将此处替换成真实业务步骤。"
    Write-Host "输入: $InputPath"
    Write-Host "输出: $OutputPath"
    Write-Host ("配置项: " + (($config.Keys | Sort-Object) -join ', '))
    exit 0
}

Write-Host "脚手架已生成，请把脚本主体替换成真实流程。"
Write-Host "输入: $InputPath"
Write-Host "输出: $OutputPath"
Write-Host ("配置项: " + (($config.Keys | Sort-Object) -join ', '))
"""


CONFIG_TEMPLATE = {
    "example_setting": "replace-me",
    "notes": "把稳定配置放在这里，避免命令行参数过于冗长。",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="创建一个最小离线脚本 bundle。"
    )
    parser.add_argument("bundle_name", help="生成目录的名称。")
    parser.add_argument(
        "--display-name",
        help="可选的展示名称，默认使用 bundle_name。",
    )
    parser.add_argument(
        "--purpose",
        help="可选的用途说明，会写入 bundle.spec.json。",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path.cwd(),
        help="bundle 将被创建到这个目录下。",
    )
    parser.add_argument(
        "--runtime",
        choices=("python", "powershell"),
        default="python",
        help="脚手架脚本的主要运行时。",
    )
    parser.add_argument(
        "--with-config",
        action="store_true",
        help="同时创建 config.example.json。",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="如果目标文件已存在，则覆盖它们。",
    )
    return parser


def sanitize_folder_name(raw_name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "-", raw_name).strip()
    cleaned = re.sub(r"\s+", "-", cleaned).strip(".-")
    return cleaned or "offline-bundle"


def bundle_title(raw_name: str, folder_name: str) -> str:
    title = raw_name.strip()
    return title if title else folder_name


def command_examples(runtime: str, script_name: str) -> tuple[str, str]:
    if runtime == "python":
        return (
            f"python {script_name} --help",
            f"python {script_name} --self-test",
        )

    return (
        f".\\{script_name} -Help",
        f".\\{script_name} -SelfTest",
    )


def entry_point_name(bundle_name: str, runtime: str) -> str:
    suffix = ".py" if runtime == "python" else ".ps1"
    return f"{bundle_name}{suffix}"


def build_spec(
    *,
    bundle_name: str,
    display_name: str,
    purpose: str | None,
    runtime: str,
    script_name: str,
    with_config: bool,
) -> dict:
    help_command, self_test_command = command_examples(runtime, script_name)
    notes = list(BASE_SPEC_NOTES)
    if not purpose:
        notes.insert(0, "请把真实用途补充到 purpose。")

    return {
        "schema": "offline-script-factory.bundle/v1",
        "bundle_name": bundle_name,
        "display_name": display_name,
        "purpose": purpose or "请补充这个 bundle 的真实用途。",
        "runtime": runtime,
        "entry_point": script_name,
        "help_command": help_command,
        "self_test_command": self_test_command,
        "config_file": "config.example.json" if with_config else None,
        "environment_variables": [],
        "external_dependencies": [],
        "notes": notes,
    }


def render_script(runtime: str, title: str, script_name: str) -> tuple[str, str]:
    if runtime == "python":
        return (
            script_name,
            PYTHON_TEMPLATE.replace("__TITLE__", title).replace("__SCRIPT_NAME__", script_name),
        )

    return (
        script_name,
        POWERSHELL_TEMPLATE.replace("__TITLE__", title).replace("__SCRIPT_NAME__", script_name),
    )


def write_text_file(path: Path, content: str, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"拒绝覆盖已存在文件: {path}")

    path.write_text(content, encoding="utf-8", newline="\n")


def main() -> int:
    args = build_parser().parse_args()

    folder_name = sanitize_folder_name(args.bundle_name)
    output_root = args.output.resolve()
    bundle_dir = output_root / folder_name
    bundle_dir.mkdir(parents=True, exist_ok=True)
    display_name = args.display_name.strip() if args.display_name else bundle_title(
        args.bundle_name, folder_name
    )
    script_name = entry_point_name(folder_name, args.runtime)

    script_name, script_body = render_script(
        runtime=args.runtime,
        title=display_name,
        script_name=script_name,
    )
    script_path = bundle_dir / script_name
    write_text_file(script_path, script_body, args.force)

    spec_path = bundle_dir / "bundle.spec.json"
    spec_body = (
        json.dumps(
            build_spec(
                bundle_name=folder_name,
                display_name=display_name,
                purpose=args.purpose.strip() if args.purpose else None,
                runtime=args.runtime,
                script_name=script_name,
                with_config=args.with_config,
            ),
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )
    write_text_file(spec_path, spec_body, args.force)

    if args.with_config:
        config_path = bundle_dir / "config.example.json"
        config_body = json.dumps(CONFIG_TEMPLATE, indent=2, ensure_ascii=True) + "\n"
        write_text_file(config_path, config_body, args.force)

    print(f"已创建 bundle: {bundle_dir}")
    print(f"运行时: {args.runtime}")
    print(f"入口脚本: {script_path.name}")
    print("元数据文件: bundle.spec.json")
    if args.with_config:
        print("配置文件: config.example.json")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - CLI surface
        print(f"错误: {exc}", file=sys.stderr)
        raise SystemExit(1)
