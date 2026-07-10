# 特变电工：SOL 与 StructFlow 盲测对比

日期：2026-07-10  
测试输入：特变电工，中国，mid horizon  
StructFlow 模型：deepseek-v4-flash，thinking on  
搜索：Tavily + AnySearch  
测试方式：先冻结独立 SOL，再运行 StructFlow，最后比较

## 1. 实验产物

- 独立基线：特变电工_SOL_20260710.md
- StructFlow 报告：scans/特变电工_20260710_150950/scan_report.md
- StructFlow 证据：scans/特变电工_20260710_150950/search_data.json

StructFlow 运行约 11 分 41 秒，执行 54 个 logical query，保存 184 条去重 evidence record，无 provider failure。

## 2. 总结判断

StructFlow 的工程化输出结构明显优于人工 SOL，能够自动完成搜索、分层、challenge、L7 二次验证和 gate。

但就本次特变电工研究质量而言，独立 SOL 更可靠，原因不是语言表达，而是以下四个底层问题：

1. StructFlow 在 L0 错误缩窄了公司业务边界。
2. Price evidence 没有强时间约束，最终使用了过期价格。
3. 财务分析使用 headline profit，忽略扣非利润、经营现金流和资本开支。
4. Gate 只验证结构完整性，没有验证事实时效、业务覆盖和建议合规。

两份报告最终都给出正向但低至中等置信度的结构信号。结论方向相同，不代表推理质量相同。

## 3. Scorecard

评分范围 0 至 10。

| Dimension | SOL | StructFlow | 判断 |
|---|---:|---:|---|
| 公司身份与业务边界 | 9.0 | 4.0 | StructFlow 把复合公司当成设备制造系统 |
| 当前数据时效性 | 8.5 | 3.0 | StructFlow 使用 22.01，而当日收盘为 20.06 |
| 财务质量分析 | 8.5 | 5.0 | StructFlow 未区分归母、扣非和公允价值收益 |
| Driver 完整性 | 8.0 | 6.0 | StructFlow 缺煤炭、发电、融资和现金回款 |
| Nonlinear 建模 | 8.0 | 5.5 | StructFlow 给出参数，但缺业务分周期状态 |
| Contradiction 质量 | 8.0 | 5.0 | 有反证搜索，但最终仍形成单边 bullish narrative |
| 证据可追溯性 | 7.5 | 7.0 | StructFlow 有 manifest，但最终 claim 没有 source ID |
| 自动化与复现 | 5.0 | 9.0 | StructFlow 明显占优 |
| Gate 有效性 | 6.0 | 3.5 | 所有 gate 通过但存在多项实质错误 |
| 投资建议边界 | 8.0 | 2.0 | StructFlow 直接输出建议做多和目标价 |
| 整体研究可信度 | 8.1 | 5.1 | SOL 胜出 |

SOL 的主要缺陷是人工选择证据、概率仍带主观性、尚未实现 claim-level citation 和自动复现，因此不能视为绝对真值。

## 4. 两份报告一致的部分

### 4.1 输变电景气具有真实支撑

两者都识别到：

- 国家电网及新型电网投资增长
- 特高压和高压设备需求
- 海外订单增长
- 高端输变电设备存在技术和认证壁垒

这部分有国家电网投资计划、公司订单和年报分部收入支撑。

### 4.2 多晶硅是主要拖累

两者都认为多晶硅价格和产能过剩会压制公司利润。

独立 SOL 进一步要求观察：

- 单位现金成本
- 未满产停产损失
- 行业库存
- 价格是否高于完全成本

StructFlow 只把多晶硅价格作为一个 CV，没有将其建模成独立库存周期。

### 4.3 最终方向一致

- SOL：long bias，置信度 0.63
- StructFlow：long，置信度 0.55

两者都不是高置信度信号。SOL 的正向信号附带扣非利润、现金流和资本开支验证条件；StructFlow 主要依赖特高压、海外订单和券商目标价。

## 5. 核心分歧

### 5.1 System boundary

SOL 将特变电工定义为：

电网高端装备 + 多晶硅/新能源 + 煤炭/发电 + 新材料 + 重资本融资的复合系统。

StructFlow 将其定义为：

制造业供应链系统，边界止于输变电设备交付。

StructFlow 最终报告明确写出不包括电力交易与用电，却没有覆盖公司的煤炭、发电、新能源电站、新材料和大型煤制气投资。

这是全链路最重要的错误。L0 一旦缩窄：

- L1 不会生成煤炭储量、电站装机、硅料库存、净债务等状态变量。
- L2 不会把煤价、发电量、资本开支和融资列为核心 driver。
- L3 只剩设备制造反馈。
- L4 regime 代表设备行业，而不是上市公司整体。
- L5/L6 会高估输变电业务对整体利润的解释力。

### 5.2 Regime

SOL 当前 regime：

输变电扩张 + 多晶硅底部 + 煤炭常态化 + 重资本再投资。

SOL 对未来 12 至 24 个月的判断：

- 温和改善 50%
- 多业务共振 22%
- 重资本与商品拖累 28%

StructFlow：

- Current regime：transition
- Next regime：contraction
- Probability：50%

但 StructFlow 随后又给出 long 和约 50% 目标价上行空间，没有解释为何 contraction regime 与强 bullish alpha 可以同时成立。

这不是必然矛盾，逆周期 alpha 可以在 contraction 中出现，但报告必须说明：

- 市场价格已经反映多少 contraction
- 哪个 driver 将推动 regime reversal
- reversal 的触发条件和时间

当前报告没有完成该桥接。

### 5.3 Profit quality

StructFlow 使用：

- 2025 年归母净利润 59.54 亿元
- 2026Q1 归母净利润 18.15 亿元，同比增长 13.4%

但没有使用：

- 2025 年扣非净利润约 45.54 亿元
- 约 14.94 亿元公允价值变动收益
- 2026Q1 扣非净利润约 14.61 亿元，同比下降约 3.77%
- 2025 年经营现金流同比下降约 27.75%
- 2025 年投资现金净流出约 197.6 亿元

因此 StructFlow 将 accounting earnings improvement 直接解释为 fundamental improvement。

SOL 的核心判断是：必须等待 core earnings 和 cash conversion 追上订单叙事。

### 5.4 Price and valuation

2026-07-10 收盘价格：

- Google Finance：20.06 元，时间戳 15:00:03
- StructFlow evidence 中 7 月 8 日来源：20.05 元
- StructFlow 最终使用：22.01 元

StructFlow 的 22.01 元来自 TradingView 页面，published_at 缺失，evidence score 为 0.5919。

更接近当前的 20.05 元被包在 AnySearch search_bundle 中，bundle score 为 0.475。

这说明当前 selector 的实际行为是：

可独立解析的旧网页 > 包含新数据但未拆分的不透明 bundle。

最终报告还使用券商目标价 33.31 元，并宣称约 50% 上行空间。目标价不是结构事实，而是第三方预测；系统既没有验证估值模型，也没有处理当前价格变化。

### 5.5 Market belief

StructFlow 将市场信念定义为：

市场担忧多晶硅、产能过剩和电网招标降价。

这只是对股价下跌原因的推断，没有一致预期、分析师盈利修正、持仓或调查证据。

SOL 采用双向 distortion：

- 市场可能因商品业务而低估输变电质量。
- 市场也可能按纯设备公司估值而低估资本开支和商品风险。

双向结构更符合复合型公司的真实定价问题。

### 5.6 L7

StructFlow L7：

- Best：特变电工
- Overvalued：中国西电
- Fragile：大全能源

SOL L7：

- Best positioned：特变电工输变电业务、海外高压设备、自营发电资产
- Overvalued narrative：把整个 600089 当作纯变压器公司
- Fragile：新特能源多晶硅、煤制气项目、大型海外工程

StructFlow 把 L7 变成了同业股票挑选，却没有完成中国西电与大全能源的财务、估值和业务可比性分析。

虽然 L7 post-search 已经在 challenge 前执行，说明两阶段代码修复生效，但 challenge 没有修正 22.01 元价格，也没有阻止未经充分比较的 peer ranking。

## 6. Evidence acquisition audit

### 6.1 来源构成

184 条 evidence record 中：

| Source type | Count | Share |
|---|---:|---:|
| General web | 101 | 54.9% |
| Search bundle | 53 | 28.8% |
| Industry research | 19 | 10.3% |
| Government | 5 | 2.7% |
| Company filing | 2 | 1.1% |
| Regulator | 2 | 1.1% |
| News | 2 | 1.1% |

General web 与 opaque bundle 合计约 83.7%。

问题不是总量不足，而是 authoritative evidence 没有成为 context 的骨架。

### 6.2 Source classification 缺陷

年报通过新浪或普通 PDF 域名进入时，可能被识别为 web，而不是 company_filing。

财富号文章被赋予 0.6084 的 evidence score，高于部分年报 bundle。来源质量分类需要同时使用：

- domain
- title
- document type
- content signature
- issuer identity

仅依据 URL path 无法可靠分类法定披露。

### 6.3 Published time 丢失

本次多数证据 published_at 为 null。

AnySearch bundle 内部实际包含 Published 字段，但外层 EvidenceRecord 没有解析，导致：

- freshness 固定在中性值
- selector 无法比较 4 月价格和 7 月价格
- hard gate 无法判断 stale

### 6.4 Competitor discovery 错误

系统将“特变电工新闻-特变电工动态-国际能源网”识别成 competitor，并为它执行 revenue market share 搜索。

根因是从搜索标题直接抽公司名，而不是执行 entity resolution。

### 6.5 Query quality

54 个 logical query 中出现：

- capacity capacity stock
- inventory capacity stock
- interest rate regulation policy
- 对错误 competitor 的公司搜索
- 当前特变电工股价22.01元低于结构性价值中枢 alpha signal evidence

最后一类 query 尤其危险：它不是寻找反证，而是在搜索支持模型刚生成的结论，形成 confirmation loop。

## 7. Gate audit

现有 gate 全部通过，但没有发现以下问题：

| Problem | Current gate result | Required gate |
|---|---|---|
| 公司业务边界漏掉主要分部 | Pass | MaterialSegmentCoverage |
| 当前价格过期 | Pass | TemporalGrounding |
| 使用目标价和买入建议 | Pass | AdviceBoundary |
| 归母与扣非利润混用 | Pass | FinancialQuality |
| contraction 与 long 未解释 | Pass | RegimeAlphaReconciliation |
| competitor 是文章标题 | Pass | EntityResolution |
| L7 peer 缺少可比性证据 | Pass | AssetVerification |
| Claim 没有 source ID | Pass | ClaimCitation |

当前 All gates passed 只能解释为 schema 完整，不应写成 output is structurally valid 之外的质量背书。

## 8. 思想设计升级

### 8.1 在 L0 之前增加 Input Resolution

~~~text
raw input
  -> input type classifier
  -> canonical entity resolver
  -> ticker and jurisdiction
  -> latest filing period
  -> material business segments
  -> current market snapshot
  -> L0 system modeling
~~~

Input type 至少区分：

- industry
- company
- commodity
- financial asset
- policy or event

特变电工作为 company 输入，必须先读取年报分部，再定义 system boundary。

### 8.2 Material Segment Coverage

L0 boundary 必须覆盖：

- 收入占比超过 5% 的分部
- 毛利润占比超过 5% 的分部
- 资本开支或负债风险重大的项目

若无法覆盖，应停止进入 L1，而不是依赖 challenge 事后修补。

### 8.3 Claim Evidence Model

每个 material claim 应具有：

~~~text
claim_id
claim_text
claim_type
value
unit
as_of
source_ids
supporting_sources
contradicting_sources
verification_status
staleness
confidence
~~~

最终报告不能只携带自然语言段落。

### 8.4 Time-sensitive hard gate

不同 claim 使用不同 freshness policy：

| Claim type | Maximum age |
|---|---|
| Current stock price | 1 trading day |
| Market cap and valuation | 1 trading day |
| Quarterly financials | Latest disclosed period |
| Annual segment data | Latest annual report |
| Policy plan | Latest effective document |
| Capacity and orders | Latest filing or IR record |

Published_at 缺失的来源不能支持 current、today、latest 等表达。

### 8.5 Authoritative evidence first

Context 选择顺序应调整为：

1. 法定披露、监管和官方统计建立事实骨架。
2. 行业协会和高质量研究解释机制。
3. 新闻补充近期事件。
4. General web 只用于发现。
5. 社区和财富号不能独立支持 material claim。

不能让 100 条 general web 通过数量压过 2 条公司法定披露。

### 8.6 Adaptive acquisition

从固定三轮搜索升级为 Claim Coverage Matrix：

~~~text
identify claim gap
  -> select required source type
  -> execute targeted query
  -> normalize source
  -> update coverage
  -> stop or search contradiction
~~~

本例应自动发现：

- 有归母利润，缺扣非利润
- 有利润，缺现金流
- 有设备订单，缺分部利润和回款
- 有股价，缺可靠 as_of
- 有煤制气项目，缺资本回报和融资影响

### 8.7 L7 verification semantics

L7 finalizer 必须输出：

| Asset | Price as of | Financial period | Evidence IDs | Verified | Rejection reason |
|---|---|---|---|---|---|

Challenge 只做语言重写或方向一致性检查，不等于 asset verification。

## 9. P0 改动清单

1. 新增 InputResolver 和 EntityProfile。
2. 从最新年报自动建立 MaterialSegmentMap。
3. 将 AnySearch bundle 拆成独立 EvidenceRecord。
4. 解析来源内部 publication time。
5. 为价格、估值和最新财务增加 TemporalGrounding gate。
6. 为所有 L5-L7 material claim 增加 source_ids。
7. 禁止建议买入、建议做多、目标价和上行空间措辞。
8. 新增 RegimeAlphaReconciliation gate。
9. competitor discovery 改用实体识别，不再使用标题切割。
10. 搜索计划改为 coverage gap 驱动。

## 10. 本次测试的最终结论

代码层面的 evidence store、URL 去重、budget、failure manifest 和 L7 两阶段顺序均正常生效。

但当前系统仍停留在：

大量检索 + 结构化 prompt + schema gate。

它尚未达到：

权威事实骨架 + claim-level evidence + 时间约束 + 可证伪研究。

本次最重要的思想结论是：

资源获取的目标不是让模型看到更多材料，而是让每个重要 claim 在正确时间、正确业务边界和正确来源等级下得到验证。

因此下一轮开发不应继续扩充 query 模板，应优先实现 Input Resolution、Material Segment Coverage、Temporal Grounding 和 Claim Citation。
