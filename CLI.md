# StructFlow Deterministic Toolkit

CLI 是 Skill 的内部执行面。宿主 Agent 通过自身的 Skill 机制调用
StructFlow 后，用户只需提供自然语言目标，例如：

```text
分析特变电工
```

这里不要求 `$structflow`；它只是部分宿主支持的一种调用语法。

以下命令由宿主 Agent 自动执行，主要用于调试。

## Setup

检查当前状态：

```bash
structflow setup --check
```

StructFlow 不需要 LLM Key。若宿主 Agent 没有自己的搜索工具，可安全配置
可选搜索 Provider：

```bash
structflow setup
```

Key 通过隐藏输入读取，不支持把 Key 作为命令行参数。

## init

```bash
structflow init SUBJECT \
  [--region REGION] \
  [--horizon short|mid|long] \
  [--mode full|core|validate-only] \
  [--peer ENTITY]... \
  [--material PATH]...
```

创建稳定的 `data/` 和本次 `report/<run-id>/`，并生成 Profile / Analysis
Schema。命令返回 JSON，其中的 `run_dir` 应传给最后的 `finalize`。

## import-evidence

```bash
structflow import-evidence SUBJECT --input evidence.json
```

导入宿主 Agent 自己搜索并规范化的证据。输入可以是数组，也可以是包含
`evidence` 数组的对象。字段说明见
[references/evidence-policy.md](references/evidence-policy.md)。

同一 canonical URL 会去重，同时保留多 category、多 query 关联。

## collect

```bash
structflow collect SUBJECT [--refresh]
```

这是宿主没有搜索能力时的可选 fallback，需要已配置 Tavily Key。默认合并
已有 cache；`--refresh` 忽略旧 cache 后重新采集 broad baseline。

## context

```bash
structflow context SUBJECT \
  --layer profile|l0|l1|l2|l3|nonlinear|l4|l5|l6|l7 \
  [--max-tokens 12000] \
  [--output context.md]
```

按层编译有限、去重、带 source ID 的证据包。未指定 `--output` 时输出到
stdout。

## schema

```bash
structflow schema profile
structflow schema analysis
structflow schema evidence
```

输出 JSON Schema。Analysis Schema 不含 gate 结果；gate 只能由代码计算。

## methodology

```bash
structflow methodology "manufacturing system"
```

根据 system type 返回代码内置的变量识别方法论。模板是“怎么想”，不是可
直接复制的答案。

## save-profile

```bash
structflow save-profile SUBJECT --input entity_profile.json
```

校验输入分类、公司身份与分部、来源 ID、财务日期和单位，并尝试从两个独立
行情来源形成一致的 `MarketSnapshot`。hard gate 失败时不会把输入建立为
canonical profile。

## stage

```bash
structflow stage SUBJECT \
  --stage profile|l0|l1|l2|l3|nonlinear|l4|l5|l6|l7-draft|l7-final \
  --input stage.json \
  --run-dir scans/SUBJECT/report/RUN_ID
```

校验宿主 Agent 生成的层级 JSON、按原顺序保存产物，并执行原有的 post-stage
Tavily/AnySearch hook。L5 会继续执行反证搜索；`l7-draft` 搜索候选资产，
`l7-final` 消费刷新后的证据且不再补搜。

## finalize

```bash
structflow finalize SUBJECT \
  [--run-dir scans/SUBJECT/report/RUN_ID]
```

默认从已通过的 stage 产物组成完整 draft，再执行 Schema、模式、证据数量、
引用、时间、财务、coverage、跨层绑定、反馈完整性、regime、建议边界和 L7
资产验证。`--input analysis_draft.json` 仅用于 validate-only 或调试。

成功时写入：

- `scan_output.json`
- `scan_report.md`
- `validation.json`
- `run_manifest.json`

失败时只保留 draft、validation 和 blocked manifest，并返回非零状态。

## 指定其他工作区根目录

所有命令都支持顶层参数：

```bash
structflow --root /path/to/project init SUBJECT
```

`--root` 必须放在子命令之前。
