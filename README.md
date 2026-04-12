# Offline Script Factory

English | [简体中文](./README_CN.md)

Offline Script Factory is a lightweight skill project that helps a coding agent turn a solved task into a reusable local script bundle.

Instead of asking the agent to solve the same task again and again, the workflow is:

1. Solve a task once.
2. Summarize the stable inputs, outputs, and constraints.
3. Generate an offline script bundle.
4. Run the generated script immediately.
5. If execution fails, fix it and run again.

The project is intentionally small. It does not try to generate a full production CLI framework. Its goal is to help users quickly preserve one-off solutions as local tools they can run later without repeating the same agent conversation.

## Quick Start

Install the skill:

```powershell
git clone <your-repo-url>
cd scripts_factory
.\skills\offline-script-factory\scripts\install.ps1
```

```bash
git clone <your-repo-url>
cd scripts_factory
bash ./skills/offline-script-factory/scripts/install.sh
```

By default, the installer uses the first available location below:

1. `OFFLINE_SCRIPT_FACTORY_SKILLS_DIR`
2. `CODEX_HOME/skills`
3. `~/.codex/skills`

You can also install to a custom skills directory explicitly:

```powershell
.\skills\offline-script-factory\scripts\install.ps1 -SkillsDir "D:\my-skills"
```

```bash
bash ./skills/offline-script-factory/scripts/install.sh --skills-dir "$HOME/.my-agent/skills"
```

Then invoke it with a prompt such as:

```text
Use $offline-script-factory to turn this completed task into a reusable offline script bundle.
```

## What This Project Includes

- A reusable skill at [`skills/offline-script-factory/SKILL.md`](./skills/offline-script-factory/SKILL.md)
- A bundle scaffolder at [`skills/offline-script-factory/scripts/init_offline_bundle.py`](./skills/offline-script-factory/scripts/init_offline_bundle.py)
- A checklist for offline feasibility and verification at [`skills/offline-script-factory/references/offline-automation-checklist.md`](./skills/offline-script-factory/references/offline-automation-checklist.md)

## Core Principles

- Offline-first: package the local part of the workflow whenever possible.
- Script over repeated prompting: prefer a reusable local artifact over re-solving the same task.
- Built-in help: generated scripts should expose usage through `--help` or `-Help`.
- Self-verification: the agent must run the generated script before delivery.
- Repair loop: if the generated script fails, the agent should patch it and rerun it.
- Agent-neutral methodology: the core workflow is written to be usable by different coding agents.

## Current Bundle Shape

Unless the task clearly needs more, the generated output should stay minimal:

```text
<bundle-name>/
  run.py | run.ps1
  config.example.json
```

`config.example.json` is optional and should only be created when stable configuration is useful.

## Repository Structure

```text
.
├── skills/
│   └── offline-script-factory/
│       ├── SKILL.md
│       ├── agents/
│       │   └── openai.yaml
│       ├── references/
│       │   └── offline-automation-checklist.md
│       └── scripts/
│           ├── init_offline_bundle.py
│           ├── install.ps1
│           └── install.sh
├── README.md
├── README_CN.md
└── LICENSE
```

## Usage

This repository now includes install scripts for quickly copying the skill into a skills directory.

If your agent platform does not support explicit skill invocation, you can still reuse the workflow by reading [`SKILL.md`](./skills/offline-script-factory/SKILL.md) directly.

## Verification Standard

Before a generated script is considered done, the agent should:

1. Run the help command.
2. Run a safe verification command such as `--self-test`, `-SelfTest`, or `--dry-run`.
3. Run a small realistic example when safe.
4. Fix failures and rerun until the script passes or an external blocker is confirmed.

## Scope

This project is a good fit for:

- file processing
- local automation
- repeatable desktop workflows
- report generation
- small utility scripts

This project is not meant to hide unavoidable online dependencies. If a task still needs a website, cloud API, or hosted model, the script should only package the offline portion and state the remaining online boundary clearly.

## Status

This project is currently an early-stage skill prototype focused on workflow quality and repeatability.

## License

This repository is released under the MIT License. See [`LICENSE`](./LICENSE).
