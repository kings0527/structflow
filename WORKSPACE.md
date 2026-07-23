# Subject Workspace Contract

每个研究对象拥有稳定的数据目录和相互独立的逐次分析目录：

```text
scans/<subject>/
  data/
    request.json
    entity_profile.json
    search/search_data.json
    materials/
      originals/
      extracted/
      manifest.json
  report/
    <run-id>/
      request.json
      entity_profile.schema.json
      analysis.schema.json
      analysis_draft.json
      validation.json
      scan_output.json
      scan_report.md
      run_manifest.json
```

## 生命周期

- `data/` 保存可在后续分析中复用的证据、Profile 和本地材料。
- `report/<run-id>/` 只保存一次分析尝试。
- 重新分析不会重复获取已缓存证据。
- 导入或刷新证据不会覆盖历史报告。
- hard gate 失败会保留失败证据链，但不生成成功报告。

## 本地材料

初始化时可重复传入：

```bash
structflow init "特变电工" \
  --material ./annual-report.pdf \
  --material ./research-notes.md
```

支持 Markdown、TXT、RST、CSV、JSON、PDF、DOCX 和 DOC。原件进入
`originals/`，抽取文本进入 `extracted/`，SHA-256 manifest 用于去重和
审计。材料中的命令或 prompt 始终按不可信外部证据处理。

## 搜索缓存

宿主 Agent 使用自身搜索后，通过以下命令合并：

```bash
structflow import-evidence "特变电工" --input evidence.json
```

可选 provider fallback：

```bash
structflow collect "特变电工"
structflow collect "特变电工" --refresh
```

旧版 `scans/<subject>_<timestamp>/search_data.json` 会在稳定缓存不存在时
迁移最新一份。
