#!/usr/bin/env bash

set -euo pipefail

show_usage() {
  cat <<'EOF'
Usage:
  ./install.sh [--skills-dir <path>] [--force] [--help]

Installs the offline-script-factory skill into a skills directory.

Target skills directory resolution order:
  1. --skills-dir
  2. OFFLINE_SCRIPT_FACTORY_SKILLS_DIR
  3. $CODEX_HOME/skills
  4. $HOME/.codex/skills
EOF
}

resolve_skills_root() {
  if [[ -n "${SKILLS_DIR:-}" ]]; then
    printf '%s\n' "${SKILLS_DIR}"
    return
  fi

  if [[ -n "${OFFLINE_SCRIPT_FACTORY_SKILLS_DIR:-}" ]]; then
    printf '%s\n' "${OFFLINE_SCRIPT_FACTORY_SKILLS_DIR}"
    return
  fi

  if [[ -n "${CODEX_HOME:-}" ]]; then
    printf '%s\n' "${CODEX_HOME}/skills"
    return
  fi

  if [[ -n "${HOME:-}" ]]; then
    printf '%s\n' "${HOME}/.codex/skills"
    return
  fi

  echo "Unable to determine a skills directory. Pass --skills-dir explicitly." >&2
  exit 1
}

SKILLS_DIR=""
FORCE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skills-dir)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --skills-dir" >&2
        exit 1
      fi
      SKILLS_DIR="$2"
      shift 2
      ;;
    --force)
      FORCE=1
      shift
      ;;
    --help|-h)
      show_usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      show_usage >&2
      exit 1
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
SKILL_NAME="$(basename "${SKILL_DIR}")"
DEST_ROOT="$(resolve_skills_root)"
DEST_DIR="${DEST_ROOT}/${SKILL_NAME}"

mkdir -p "${DEST_ROOT}"

if [[ -e "${DEST_DIR}" ]]; then
  if [[ "${FORCE}" -ne 1 ]]; then
    echo "Refusing to overwrite existing skill: ${DEST_DIR}" >&2
    echo "Use --force to reinstall." >&2
    exit 1
  fi

  rm -rf "${DEST_DIR}"
fi

cp -R "${SKILL_DIR}" "${DEST_ROOT}/"

echo "Installed skill to: ${DEST_DIR}"
echo "Restart or reload your agent session if it does not detect the skill immediately."
