# StructFlow

StructFlow 现在是一个面向 Codex、Claude Code、ChatGPT Desktop 等宿主
Agent 的结构研究 Skill，而不是一个 Python 程序内部再次调用 LLM 的 Agent。

宿主 Agent 负责搜索、判断、逐层生成和对抗性复核；Python 工具箱只负责：

- 持久化搜索证据和本地材料；
- 为每层裁剪可追溯的 evidence packet；
- 提供 Profile / Analysis JSON Schema；
- 校验来源 ID、日期、财务单位、coverage、跨层绑定和投资标的；
- hard gate 未通过时阻止正式报告发布；
- 生成可审计的 JSON、Markdown 和运行 manifest。

这让同一个分析方法可以由 CLI、Desktop 或任何支持 Skill 的 Agent 调用，
并复用宿主本身的搜索能力，无需额外配置 LLM API Key。

## 使用方式

在 Codex、Claude Code、ChatGPT Desktop 或其他支持 Skill 的宿主中，通过
宿主自己的 Skill 选择、加载或调用机制主动调用 StructFlow。调用方式由宿主
决定，不要求用户输入美元符号或任何固定命令。

```text
选择/调用 StructFlow Skill
分析特变电工
```

也可以明确说“使用 StructFlow 分析黄金”。`$structflow` 只是 Codex
支持的一种可选写法，不是 StructFlow 的通用调用协议。

如果宿主没有主动调用 StructFlow，普通的“分析特变电工”“分析一下这个
公司”或“研究半导体行业”本身不应触发它。宿主一旦调用，后续输入可以只是
自然语言分析目标。

调用后，宿主 Agent 会在内部完成初始化、逐层搜索、L0-L7 生成、
challenge、反证、验证和报告发布；用户不需要手工运行 CLI 或准备 JSON。

内部工作流见 [SKILL.md](SKILL.md) 和
[references/runtime-flow.md](references/runtime-flow.md)。

## 生成模式

- `full`：完整 L0-L7，包括经过资产级证据验证的映射。
- `core`：完整 L0-L6，不生成 L7。
- `validate-only`：只校验已有 draft。

模式只改变输出范围，不降低证据要求。

## 初始化和 Key

Skill-native 模式不需要 `LLM_API_KEY`。原有 Tavily / AnySearch 搜索配置
继续使用。首次缺少搜索 Key 时运行一次：

```bash
python scripts/structflow.py setup
```

该命令用隐藏输入引导配置 Tavily / AnySearch Key，并把 `.env` 权限设为
当前用户可读写。不要把 Key 放进聊天或命令行参数。宿主 Agent 自身搜索可
用于补充 provider 降级或证据缺口，但不会替代原有逐层搜索流程。

## 工作区

```text
scans/<subject>/
  data/
    request.json
    entity_profile.json
    search/search_data.json
    materials/
  report/<run-id>/
    request.json
    entity_profile.schema.json
    analysis.schema.json
    analysis_draft.json
    validation.json
    scan_output.json
    scan_report.md
    run_manifest.json
```

`data/` 是可复用的可靠信息层，`report/<run-id>/` 是每次分析的独立产物。
hard gate 失败时会保留 draft、validation 和 manifest，但不会伪造成功报告。

## 开发验证

```bash
python -m pip install -e '.[test]'
pytest -q
python /Users/kk/.codex/skills/.system/skill-creator/scripts/quick_validate.py .
```

详细命令见 [CLI.md](CLI.md)，研究方法见
[references/methodology.md](references/methodology.md)。
