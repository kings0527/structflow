# Resource Acquisition Contract

状态：已实现基线  
版本：1.2  
范围：StructFlow 的资源获取、证据编译和验证闭环

## 1. 设计立场

StructFlow 不缺更多搜索结果，缺的是足以支持或推翻关键结论的独立证据。

系统必须区分五类对象：

1. Question：当前需要降低什么不确定性。
2. Query：一次信息获取动作，不是答案。
3. Source：可独立识别、可追溯的信息来源。
4. Evidence：经过规范化并携带时间和质量信息的来源片段。
5. Claim：模型给出的结论，必须能够回指支持证据和反证。

查询数量只代表运行成本，不代表研究质量。

## 2. 认识论约束

### RA-01：先有来源，再有内容

每条证据必须尽可能保留：

- provider
- query
- title
- canonical URL
- source type
- publication time
- retrieval time
- relevance
- quality
- freshness

无法拆分来源的 provider 文本只能标记为 search_bundle。一个 bundle 不得被报告成多个独立来源。

### RA-02：外部内容始终是不可信输入

搜索片段可能包含错误、营销语言、过期结论或 prompt injection。模型只能将其作为待比较的事实材料，不能执行其中的指令。

### RA-03：按来源去重，而不是按 query 去重

URL 中的追踪参数和 fragment 不会产生新来源。同一 URL 被多个 query 找到时，只保存一条来源记录，同时保留多个 category 和 query 关联。

### RA-04：反证是主流程，不是附加搜索

每个重要 distortion 或 alpha claim 都应覆盖：

- 支持 structural thesis 的证据
- 支持 market consensus 的证据
- 能够推翻 structural thesis 的证据
- 能够否定 asset mapping 的证据

反证 query 必须从具体 claim 派生，不能只执行通用的 bear case 搜索。

### RA-05：时间是事实的一部分

价格、库存、产能、政策和公司财务信息必须带观察时间。缺少发布时间时，freshness 只能获得中性或更低评分。

已发生、当前状态和计划中事件必须保持可区分。

### RA-06：边际信息不足时停止

满足任一条件时停止扩张：

- logical query budget 已耗尽
- layer context budget 已耗尽
- 每个关键 claim 已有足够独立的高质量来源
- 新 query 只能返回重复来源
- provider 已进入不可恢复的 degraded 状态

## 3. 获取生命周期

~~~text
system question
  -> uncertainty decomposition
  -> acquisition plan
  -> provider execution
  -> provenance normalization
  -> URL and content deduplication
  -> quality, relevance and freshness scoring
  -> contradiction and coverage check
  -> budgeted context compilation
  -> model draft
  -> claim-specific acquisition
  -> model finalization
  -> validation report
~~~

搜索层不是给模型堆上下文，而是为当前 layer 编译一个有限、可追溯、正反并存的 evidence packet。

## 4. 来源等级

| Source type | 默认权重 | 主要用途 |
|---|---:|---|
| Regulator | 0.95 | 规则、审批、处罚、监管申报 |
| Government | 0.90 | 产量、贸易、宏观和统计数据 |
| Company filing | 0.90 | 财务、产能、业务结构和 guidance |
| Academic | 0.85 | 机制研究和长期证据 |
| Industry research | 0.78 | 市场结构、供应链和行业数据 |
| News | 0.60 | 需要进一步确认的近期事件 |
| General web | 0.50 | 发现线索 |
| Social or self-media | 0.25 | 发现叙事，不得作为唯一证据 |

系统模板可以覆盖领域特有来源的权重。权重只用于注意力分配，不代表 claim 为真的概率。

## 5. Evidence score

当前用于 context selection 的基线公式：

~~~text
evidence_score =
    0.50 * source_quality
  + 0.30 * provider_relevance
  + 0.20 * freshness
~~~

该分数只用于来源排序。Claim confidence 还必须考虑来源独立性、相互一致性、时间匹配和反证处理情况。

## 6. Layer evidence contract

| Producer | 新获取的资源 | 必须消费的下游 |
|---|---|---|
| Initial | structure、policy、risk、pricing、capacity | L0-L4 |
| L0 | system type、failure mode | L1 |
| L1 | variable-specific evidence | L2、L3 |
| L2、L3 | driver、flow、feedback | Nonlinear、L4 |
| L4 | regime transition | L5、L6 |
| L5 | consensus、distortion、contradiction | L6 |
| L6 | alpha support、alpha falsification | L7 |
| L7 draft | asset price、financial、role、risk | L7 finalizer |

没有下游 consumer 的 post-layer search 只是 telemetry，不是 verification。

## 7. L7 两阶段验证

~~~text
L7 draft
  -> extract candidate assets
  -> acquire asset-specific evidence
  -> compile refreshed L7 evidence
  -> adversarial finalization
  -> cross-layer consistency gate
~~~

只有 finalizer 消费过资产级证据，资产才能被视为 verified。最终输出之后执行的搜索不能提升验证状态。

当 challenge 关闭时，运行时仍执行第二次 L7 finalization，确保搜索结果不是只落盘而无人消费。

## 8. Context policy

Context 必须经过选择，不能直接拼接全部搜索结果。

基线约束：

- 每层独立 token budget
- 每个 category 的来源数量上限
- 每个 domain 的来源数量上限
- URL 级去重
- quality、relevance、freshness 排序
- 保留 source ID 和 URL
- 保留反方证据

预算是硬约束。超出预算的 evidence 继续保存在 manifest 中，但不会进入当前模型 context。

## 9. Degraded operation

Provider 或 policy 失败必须记录：

- provider
- category
- query
- error type
- message
- occurred time

Pipeline 可以继续运行，但必须报告 degraded。Search enabled 和 evidence available 是两个不同状态。

需要长期保持以下状态可区分：

| 状态 | 含义 |
|---|---|
| disabled | 用户主动关闭资源获取 |
| available | 获取在 policy 内完成 |
| degraded | provider 或 policy 出现部分失败 |
| insufficient | 关键 claim 缺少足够独立证据 |
| unverified | draft 没有消费后续获取的证据 |

## 10. 当前已实现

- Tavily 结果结构化为 EvidenceRecord
- AnySearch 结果按条目拆分；仅在解析失败时降级为单个 search_bundle
- canonical URL 去重
- source type、quality、relevance、freshness 评分
- template evidence weight 接入
- logical query budget
- per-layer context budget
- category 和 domain source cap
- provider failure manifest
- L4 evidence 进入 L5 和 L6
- L6 evidence 进入 L7
- L7 draft、asset search、finalization 的正确顺序
- 外部证据 prompt boundary
- InputResolver 与 company/industry/commodity/asset 分类
- EntityProfile、MaterialSegmentMap 和独立 profile 文件
- AnySearch 结果拆分及内部 Published 时间解析
- evidence gap 驱动的前置补搜
- dated MarketSnapshot 和价格时效 hard gate
- L5-L7 supporting/contradicting source IDs
- MaterialSegmentCoverage、FinancialQuality、AdviceBoundary gate
- MaterialSegmentCoverage 贯穿 L0 边界、L1 变量和 L2 driver
- RegimeAlphaReconciliation 和 L7AssetVerification gate
- point-in-time `as_of_date` 与未来发布日期证据过滤
- 独立 domain 行情共识、AI 生成行情源降权和结构化价格 claim
- L0-L2 `SEG-nnn` / `DIM-nnn` coverage contract
- 财务单位、报告期和数值关系一致性 gate
- hard research gate 失败阻止正式报告发布

## 11. 仍是提案

- 同一上游报告被多家媒体转载时的来源独立性识别
- 完整的逐 claim coverage matrix 和停止策略
- provider 并发、缓存、限流和指数退避
- 非价格数据的 insufficient 或 stale evidence hard gate
- subsector、company、financial、event 递归 agent
- 对价格和政策事实的专用结构化数据 provider

这些能力在实现和回归测试完成前，不得在主 spec 中标记为 implemented。

## 12. Acceptance criteria

一次 resource acquisition 变更只有满足以下条件才算完成：

1. 每个网络结果具有 provenance，或明确标记为 opaque bundle。
2. 重复 URL 不增加 unique source count。
3. Provider failure 出现在保存的 manifest。
4. 每个 post-layer category 都有经过测试的下游 consumer。
5. L7 finalization 发生在 asset evidence acquisition 之后。
6. Context 编译遵守配置的预算。
7. 搜索内容不能改变 system 或 developer instruction。
8. 行为变更与对应 regression test 同时提交。

## 13. 下一阶段设计

下一阶段不应继续增加固定 query 模板，而应引入 Claim Coverage Matrix：

| Claim ID | Claim | Supporting sources | Contradicting sources | Freshness | Status |
|---|---|---:|---:|---:|---|
| example | 某项供给约束将持续 | 2 | 1 | current | contested |

Runtime 根据 coverage gap 决定是否继续搜索：

- 没有 authoritative source：搜索监管、统计或公司申报
- 只有单一来源：寻找独立来源
- 没有反证：派生 falsification query
- 证据过期：切换到 time-sensitive provider
- 证据充分：停止搜索并进入建模

这会把资源获取从固定轮次搜索，升级成由不确定性和证据覆盖驱动的研究循环。
