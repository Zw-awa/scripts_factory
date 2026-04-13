from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "skills" / "offline-script-factory" / "scripts"
INIT_BUNDLE = SCRIPTS_DIR / "init_offline_bundle.py"
UPDATE_INDEX = SCRIPTS_DIR / "update_bundle_index.py"
VALIDATE_METADATA = SCRIPTS_DIR / "validate_bundle_metadata.py"
INSTALL_PS1 = SCRIPTS_DIR / "install.ps1"
TEST_TMP_ROOT = REPO_ROOT / "tmp" / "test-runs"
TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)


def run_command(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def run_python(script: Path, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return run_command([sys.executable, str(script), *args], cwd=cwd)


def resolve_powershell() -> str | None:
    for name in ("pwsh", "powershell", "powershell.exe"):
        path = shutil.which(name)
        if path:
            return path
    return None


@contextmanager
def workspace_test_dir() -> Path:
    path = TEST_TMP_ROOT / f"case-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


class OfflineScriptFactoryTests(unittest.TestCase):
    def test_init_bundle_python_uses_bundle_name_as_entry_point(self) -> None:
        with workspace_test_dir() as root:
            result = run_python(
                INIT_BUNDLE,
                "csv-report-tool",
                "--purpose",
                "把输入 CSV 转成标准化报表。",
                "--output",
                str(root),
                "--runtime",
                "python",
                "--with-config",
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)

            bundle_dir = root / "csv-report-tool"
            script_path = bundle_dir / "csv-report-tool.py"
            spec_path = bundle_dir / "bundle.spec.json"

            self.assertTrue(script_path.is_file())
            self.assertFalse((bundle_dir / "run.py").exists())
            self.assertTrue(spec_path.is_file())

            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            self.assertEqual(spec["entry_point"], "csv-report-tool.py")
            self.assertEqual(spec["help_command"], "python csv-report-tool.py --help")
            self.assertEqual(spec["self_test_command"], "python csv-report-tool.py --self-test")

    def test_init_bundle_powershell_uses_bundle_name_as_entry_point(self) -> None:
        powershell = resolve_powershell()
        if not powershell:
            self.skipTest("PowerShell executable not found")

        with workspace_test_dir() as root:
            result = run_python(
                INIT_BUNDLE,
                "cleanup-logs",
                "--purpose",
                "清理旧日志并保留最近文件。",
                "--output",
                str(root),
                "--runtime",
                "powershell",
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)

            bundle_dir = root / "cleanup-logs"
            script_path = bundle_dir / "cleanup-logs.ps1"
            spec_path = bundle_dir / "bundle.spec.json"

            self.assertTrue(script_path.is_file())
            self.assertFalse((bundle_dir / "run.ps1").exists())

            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            self.assertEqual(spec["entry_point"], "cleanup-logs.ps1")
            self.assertEqual(spec["help_command"], ".\\cleanup-logs.ps1 -Help")
            self.assertEqual(spec["self_test_command"], ".\\cleanup-logs.ps1 -SelfTest")

            help_result = run_command(
                [
                    powershell,
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(script_path),
                    "-Help",
                ]
            )
            self.assertEqual(help_result.returncode, 0, msg=help_result.stderr or help_result.stdout)
            self.assertIn("用法:", help_result.stdout)
            self.assertIn("cleanup-logs.ps1", help_result.stdout)

    def test_update_index_and_validate_directory(self) -> None:
        with workspace_test_dir() as root:
            first = run_python(
                INIT_BUNDLE,
                "csv-report-tool",
                "--purpose",
                "把输入 CSV 转成标准化报表。",
                "--output",
                str(root),
                "--runtime",
                "python",
                "--with-config",
            )
            second = run_python(
                INIT_BUNDLE,
                "cleanup-logs",
                "--purpose",
                "清理旧日志并保留最近文件。",
                "--output",
                str(root),
                "--runtime",
                "powershell",
            )
            self.assertEqual(first.returncode, 0, msg=first.stderr or first.stdout)
            self.assertEqual(second.returncode, 0, msg=second.stderr or second.stdout)

            index_result = run_python(UPDATE_INDEX, "--root", str(root))
            self.assertEqual(index_result.returncode, 0, msg=index_result.stderr or index_result.stdout)

            index_path = root / "bundles.index.json"
            self.assertTrue(index_path.is_file())
            index = json.loads(index_path.read_text(encoding="utf-8"))
            self.assertEqual(index["bundle_count"], 2)
            self.assertEqual(
                [bundle["bundle_name"] for bundle in index["bundles"]],
                ["cleanup-logs", "csv-report-tool"],
            )

            validate_result = run_python(VALIDATE_METADATA, str(root))
            self.assertEqual(
                validate_result.returncode, 0, msg=validate_result.stderr or validate_result.stdout
            )
            self.assertIn("校验通过文件数", validate_result.stdout)

    def test_validator_reports_missing_entry_point(self) -> None:
        with workspace_test_dir() as root:
            result = run_python(
                INIT_BUNDLE,
                "csv-report-tool",
                "--purpose",
                "把输入 CSV 转成标准化报表。",
                "--output",
                str(root),
                "--runtime",
                "python",
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)

            bundle_dir = root / "csv-report-tool"
            script_path = bundle_dir / "csv-report-tool.py"
            script_path.unlink()

            validate_result = run_python(VALIDATE_METADATA, str(bundle_dir / "bundle.spec.json"))
            self.assertNotEqual(validate_result.returncode, 0)
            self.assertIn("entry_point 指向的文件不存在", validate_result.stdout)

    def test_install_ps1_copies_skill_to_target_directory(self) -> None:
        powershell = resolve_powershell()
        if not powershell:
            self.skipTest("PowerShell executable not found")

        with workspace_test_dir() as root:
            result = run_command(
                [
                    powershell,
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(INSTALL_PS1),
                    "-SkillsDir",
                    str(root),
                ]
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)

            installed_skill = root / "offline-script-factory"
            self.assertTrue((installed_skill / "SKILL.md").is_file())
            self.assertTrue((installed_skill / "scripts" / "init_offline_bundle.py").is_file())


if __name__ == "__main__":
    unittest.main()
