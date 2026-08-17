from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from sqlalchemy.orm import Session

from ..config import Settings
from ..models import Skill, SkillCandidate, Task


def repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def slugify(value: str) -> str:
    import re

    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return slug[:60] or "reusable-workflow"


def create_skill_candidate(session: Session, settings: Settings, task: Task) -> SkillCandidate:
    existing = next((candidate for candidate in session.query(SkillCandidate).filter_by(task_id=task.id).all() if candidate.status != "rejected"), None)
    if existing:
        return existing
    bundle_name = f"task-{task.id[:8]}-{slugify(task.goal)[:32]}"
    init_script = repository_root() / "skills" / "offline-script-factory" / "scripts" / "init_offline_bundle.py"
    validate_script = repository_root() / "skills" / "offline-script-factory" / "scripts" / "validate_bundle_metadata.py"
    command = [sys.executable, str(init_script), bundle_name, "--purpose", task.goal, "--output", str(settings.candidates_dir), "--runtime", "python", "--force"]
    generated = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False, env={**__import__("os").environ, "PYTHONUTF8": "1"})
    bundle_path = settings.candidates_dir / bundle_name
    validation = subprocess.run([sys.executable, str(validate_script), str(bundle_path)], capture_output=True, text=True, encoding="utf-8", errors="replace", check=False, env={**__import__("os").environ, "PYTHONUTF8": "1"}) if generated.returncode == 0 else None
    self_test = subprocess.run([sys.executable, str(bundle_path / f"{bundle_name}.py"), "--self-test"], capture_output=True, text=True, encoding="utf-8", errors="replace", check=False, env={**__import__("os").environ, "PYTHONUTF8": "1"}) if validation and validation.returncode == 0 else None
    result = {
        "generation_returncode": generated.returncode,
        "generation_output": generated.stdout or generated.stderr,
        "validation_returncode": validation.returncode if validation else None,
        "validation_output": (validation.stdout or validation.stderr) if validation else None,
        "self_test_returncode": self_test.returncode if self_test else None,
        "self_test_output": (self_test.stdout or self_test.stderr) if self_test else None,
    }
    status = "validated" if self_test and self_test.returncode == 0 else "failed"
    candidate = SkillCandidate(task_id=task.id, bundle_name=bundle_name, bundle_path=str(bundle_path), status=status, validation_json=json.dumps(result, ensure_ascii=False))
    session.add(candidate)
    session.flush()
    return candidate


def promote_skill_candidate(session: Session, settings: Settings, candidate_id: str) -> Skill:
    candidate = session.get(SkillCandidate, candidate_id)
    if not candidate:
        raise ValueError(f"Skill candidate not found: {candidate_id}")
    if candidate.status != "validated":
        raise ValueError("Only validated candidates can be promoted")
    source = Path(candidate.bundle_path)
    destination = settings.bundles_dir / candidate.bundle_name
    if destination.exists():
        raise FileExistsError(f"Bundle already exists: {destination}")
    shutil.copytree(source, destination)
    update_index = repository_root() / "skills" / "offline-script-factory" / "scripts" / "update_bundle_index.py"
    index_result = subprocess.run(
        [sys.executable, str(update_index), "--root", str(settings.bundles_dir)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env={**__import__("os").environ, "PYTHONUTF8": "1"},
    )
    if index_result.returncode != 0:
        shutil.rmtree(destination, ignore_errors=True)
        raise RuntimeError(index_result.stderr or index_result.stdout)
    skill = Skill(bundle_name=candidate.bundle_name, bundle_path=str(destination), source_candidate_id=candidate.id)
    session.add(skill)
    candidate.status = "promoted"
    session.flush()
    return skill
