# 离线脚本工厂

[English](./README.md) | 简体中文

离线脚本工厂是一个轻量级 skill 项目，用来帮助代码 agent 把“已经解决过的一次性需求”沉淀成以后可重复运行的本地脚本 bundle。

它的核心目标不是生成一整套重量级 CLI 框架，而是把已经验证可行的解决方案快速固化下来，让用户以后直接本地运行，不需要每次都重新发起一次完整的 agent 对话。

## 快速开始

先安装这个 skill：

```powershell
git clone <你的仓库地址>
cd scripts_factory
.\skills\offline-script-factory\scripts\install.ps1
```

```bash
git clone <你的仓库地址>
cd scripts_factory
bash ./skills/offline-script-factory/scripts/install.sh
```

安装脚本默认按下面顺序寻找 skills 目录：

1. `OFFLINE_SCRIPT_FACTORY_SKILLS_DIR`
2. `CODEX_HOME/skills`
3. `~/.codex/skills`

如果你想手动指定目标目录，也可以这样执行：

```powershell
.\skills\offline-script-factory\scripts\install.ps1 -SkillsDir "D:\my-skills"
```

```bash
bash ./skills/offline-script-factory/scripts/install.sh --skills-dir "$HOME/.my-agent/skills"
```

安装后可以用类似这样的提示词调用：

```text
使用 $offline-script-factory 把当前已解决的需求沉淀成一个可离线运行的本地脚本。
```

## 这个项目在做什么

标准流程是：

1. 先把需求解决一次。
2. 提炼稳定的输入、输出和约束。
3. 生成离线脚本 bundle。
4. agent 自己立即运行脚本验证。
5. 如果运行失败，就继续修改并重新运行。

## 当前包含的内容

- 可复用的 skill：
  [`skills/offline-script-factory/SKILL.md`](./skills/offline-script-factory/SKILL.md)
- bundle 脚手架生成器：
  [`skills/offline-script-factory/scripts/init_offline_bundle.py`](./skills/offline-script-factory/scripts/init_offline_bundle.py)
- bundle 索引生成器：
  [`skills/offline-script-factory/scripts/update_bundle_index.py`](./skills/offline-script-factory/scripts/update_bundle_index.py)
- 元数据校验器：
  [`skills/offline-script-factory/scripts/validate_bundle_metadata.py`](./skills/offline-script-factory/scripts/validate_bundle_metadata.py)
- 离线可行性与验证清单：
  [`skills/offline-script-factory/references/offline-automation-checklist.md`](./skills/offline-script-factory/references/offline-automation-checklist.md)

## 核心理念

- 离线优先：能离线固化的部分就优先固化。
- 脚本优先于重复提问：尽量把重复需求沉淀成可执行产物。
- 用法内置：生成脚本默认通过 `--help` 或 `-Help` 提供使用说明。
- 自运行验证：脚本生成后必须实际运行。
- 失败自动回修：脚本跑不通就继续修，再运行。
- agent 中立：核心方法论尽量不绑定某一个模型厂商。

## 默认产物形态

除非任务明显更复杂，否则默认保持最小结构：

```text
<bundle-name>/
  <bundle-name>.py | <bundle-name>.ps1
  bundle.spec.json
  config.example.json
```

其中 `bundle.spec.json` 是 bundle 的机器可读元数据来源。

`config.example.json` 不是必选项，只有当任务确实存在稳定配置时才需要。

## 仓库结构

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
│           ├── install.sh
│           ├── update_bundle_index.py
│           └── validate_bundle_metadata.py
├── README.md
├── README_CN.md
└── LICENSE
```

## 如何使用

当前仓库已经提供了安装脚本，可以快速把 skill 复制到目标 skills 目录。

如果你在一个目录里沉淀了多个 bundle，可以运行索引脚本生成本地总索引：

```powershell
python .\skills\offline-script-factory\scripts\update_bundle_index.py --root .\my-bundles
```

它会生成 `bundles.index.json`，方便后续 agent 先检查本地已有工具，再决定是否新建。

如果你想在复用或发布前检查元数据是否完整，可以运行：

```powershell
python .\skills\offline-script-factory\scripts\validate_bundle_metadata.py .\my-bundles
```

如果你的 agent 平台不支持显式 skill 调用，也可以直接读取 [`SKILL.md`](./skills/offline-script-factory/SKILL.md)，按其中流程执行。

## 验证标准

在一个生成脚本被视为完成之前，agent 应至少做到：

1. 运行帮助命令。
2. 运行安全验证命令，例如 `--self-test`、`-SelfTest` 或 `--dry-run`。
3. 如果安全且可行，再跑一次小样本真实命令。
4. 若失败，则继续修复并重跑，直到通过或确认存在外部阻塞。

## 自动化测试

可以用下面的命令运行仓库测试：

```powershell
python -m unittest discover -s .\tests -v
```

当前自动化测试主要覆盖：

- Python bundle 生成
- PowerShell bundle 生成
- 元数据索引生成
- 元数据校验
- PowerShell 安装脚本行为

## 适用范围

这个项目更适合：

- 文件处理
- 本地自动化
- 可重复的桌面工作流
- 报表生成
- 小型工具脚本

它不适合掩盖不可避免的在线依赖。如果任务本质上仍然依赖网页、云 API 或托管模型，那么脚本只应固化离线部分，并明确剩余的在线边界。

## 当前状态

这个项目目前处于早期阶段，重点在于把“需求转脚本”的流程做稳定、做清晰、做可复用。

## 许可证

本仓库使用 MIT License，见 [`LICENSE`](./LICENSE)。
