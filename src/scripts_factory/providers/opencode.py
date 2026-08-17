from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

from .base import Provider, SessionRequest, SessionResult


class OpenCodeProvider(Provider):
    name = "opencode"

    @staticmethod
    def command_prefix(executable: str) -> list[str]:
        suffix = Path(executable).suffix.lower()
        if suffix == ".ps1":
            powershell = shutil.which("pwsh") or shutil.which("powershell") or shutil.which("powershell.exe")
            if not powershell:
                raise RuntimeError("PowerShell is required to run the OpenCode shim")
            return [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", executable]
        if suffix in {".cmd", ".bat"}:
            return ["cmd.exe", "/d", "/c", executable]
        return [executable]

    async def healthcheck(self) -> tuple[bool, str]:
        executable = shutil.which("opencode")
        if not executable:
            return False, "opencode executable not found"
        try:
            prefix = self.command_prefix(executable)
        except RuntimeError as exc:
            return False, str(exc)
        process = await asyncio.create_subprocess_exec(*prefix, "--version", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await process.communicate()
        return process.returncode == 0, (stdout or stderr).decode("utf-8", errors="replace").strip()

    async def run(self, request: SessionRequest) -> SessionResult:
        executable = shutil.which("opencode")
        if not executable:
            return SessionResult(success=False, content="", error="opencode executable not found")
        try:
            args = [*self.command_prefix(executable), "run", request.prompt, "--format", "json", "--dir", str(request.working_directory), "--title", request.title]
        except RuntimeError as exc:
            return SessionResult(success=False, content="", error=str(exc))
        if request.model:
            args.extend(["--model", request.model])
        if request.external_session_id:
            args.extend(["--session", request.external_session_id])
        try:
            process = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=request.timeout_seconds)
        except TimeoutError:
            process.kill()
            await process.wait()
            return SessionResult(success=False, content="", error="OpenCode session timed out")
        output = stdout.decode("utf-8", errors="replace")
        error = stderr.decode("utf-8", errors="replace")
        events: list[dict] = []
        for line in output.splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        session_id = next((event.get("sessionID") or event.get("session_id") for event in events if event.get("sessionID") or event.get("session_id")), None)
        text_parts = [str(event.get("text")) for event in events if event.get("text")]
        content = "\n".join(text_parts) or output.strip()
        return SessionResult(success=process.returncode == 0, content=content, external_session_id=session_id, data={"events": events}, error=error.strip() or None)
