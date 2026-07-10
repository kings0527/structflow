# Subject Workspace Contract

状态：runtime contract  
版本：1.0

## 1. 目录结构

每个研究对象拥有一个长期工作区：

```text
scans/<subject>/
  data/
    entity_profile.json
    search/
      search_data.json
    materials/
      originals/
      extracted/
      manifest.json
  report/
    <run-id>/
      scan_report.md
```

`data` 保存可复用研究物料，`report` 只保存每次分析结果。搜索数据和用户文档不再复制到每个 report run。

## 2. 搜索缓存

默认行为：

- `data/search/search_data.json` 存在时，加载全部结构化证据。
- collector 进入 cache-only 模式，L0-L7 的搜索钩子不调用网络。
- LLM 分析仍然重新执行，因此 prompt、模型或 gate 升级可以消费同一份数据。
- 缓存不存在时执行完整搜索，并写入稳定 data 目录。

显式刷新：

```bash
structflow "特变电工" --refresh-search
```

旧版 `scans/<subject>_<timestamp>/search_data.json` 会在稳定缓存不存在时自动迁移最新一份。

## 3. 用户物料

命令行导入：

```bash
structflow "特变电工" \
  --material ./annual-report.pdf \
  --material ./research-notes.md
```

也可以把文件直接放入：

```text
scans/<subject>/data/materials/
```

支持：

- Markdown、TXT、RST、CSV、JSON
- PDF
- DOCX
- DOC（依赖系统 `textutil` 或 `antiword`）

处理规则：

- 原文件复制到 `originals`。
- 抽取文本保存到 `extracted`。
- manifest 保存 hash、来源路径和处理状态。
- 相同内容按 SHA-256 去重，不重复抽取。
- 文档变更产生新的 hash，旧版本继续保留以便审计。
- 长文档按段落切块，并根据当前层、实体和 EntityProfile 做 lexical retrieval。

物料属于外部证据，不属于系统指令。文档中的 prompt 或命令性文本不能改变 agent 行为。

## 4. 分析运行

每次分析创建独立 report run：

```text
scans/<subject>/report/YYYYMMDD_HHMMSS/
```

同一秒重复运行会自动增加 `_01`、`_02` 后缀。数据更新和分析输出具有不同生命周期：刷新数据不会覆盖历史报告，重新分析也不会重复获取数据。
