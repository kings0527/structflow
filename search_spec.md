下面给你一套可直接工程化落地的「行业分析 + 搜索驱动Agent Spec（泛化版）」。重点解决你提到的两个核心问题：

搜索不是“问LLM”，而是“扩展信息空间（Google化）”

关键词必须结构化 + 多语言 + 多视角覆盖

行业 → 板块 → 个股递归可用



---

🧠 Structural Alpha Search Agent Spec v1.0（泛化版）

0. 设计目标

构建一个可递归的信息系统：

行业（System）
  → 板块（Sub-System）
      → 公司（Entity）
          → 财务/事件/预期（Micro-State）

核心原则：

❌ 不直接“回答问题”

❌ 不让LLM“总结搜索结果”

✅ 只做“信息空间扩展 + 结构化采集”

✅ 后续LLM只负责“建模”



---

1. Search Engine Abstraction Layer（关键）

1.1 搜索不是 query，而是：

👉 Information Expansion Operators（信息扩展算子）

每个 query 必须拆成 6 类：

类别作用

Core Term行业本体
Value Chain上下游
Pricing价格 / 成本
Structure市场结构
Risk风险变量
Narrative市场叙事



---

1.2 Query生成模板（核心）

{core} + {dimension} + {time} + {region} + {comparison} + {shock}


---

1.3 多语言扩展（必须）

每个 query 必须至少 3 种语言：

中文

英文

原生产业语言（术语/行业黑话）



---

2. Industry Search Spec（第一层）

2.1 行业初始化 Query Set

CORE:
  - "{industry} industry overview"
  - "{industry} market size CAGR"
  - "{industry} global value chain"
  - "{industry} competitive landscape"

CHINESE:
  - "{行业} 行业 格局"
  - "{行业} 产业链 上下游"
  - "{行业} 市占率 龙头"

STRUCTURE:
  - "{industry} oligopoly vs fragmentation"
  - "{industry} supply chain bottleneck"

SHOCK:
  - "{industry} crisis / shortage / oversupply"
  - "{industry} price crash / spike"

DATA:
  - "{industry} production capacity utilization"
  - "{industry} inventory level"


---

3. Subsector Expansion Spec（第二层）

3.1 自动拆解维度

每个行业必须拆：

Upstream / Midstream / Downstream

以及：

Materials / Infrastructure / Distribution / End Demand


---

3.2 Sub-sector Query Template

VALUE_CHAIN:
  - "{subsector} upstream suppliers list"
  - "{subsector} downstream demand drivers"
  - "{subsector} bottleneck analysis"

COMPETITION:
  - "{subsector} top 10 companies market share"
  - "{subsector} concentration ratio CR5 CR10"

PRICING:
  - "{subsector} pricing mechanism spot vs futures"
  - "{subsector} margin structure EBITDA breakdown"


---

4. Company-Level Search Spec（第三层）

4.1 公司必须拆 5 维搜索

1. Business model
2. Revenue structure
3. Cost structure
4. Competitive moat
5. Risk exposure


---

4.2 Company Query Template

MODEL:
  - "{company} business model breakdown"
  - "{company} revenue segmentation"

FINANCIAL:
  - "{company} gross margin trend"
  - "{company} free cash flow history"

RISKS:
  - "{company} regulatory risk"
  - "{company} supply chain dependency"

COMPETITION:
  - "{company} vs competitors analysis"

INTERNAL TERMS:
  - "{company} earnings call transcript"
  - "{company} investor presentation pdf"


---

5. Attention Allocation System（关键升级）

5.1 每个 query 必须打权重

query_weight = (
    information_gain *
    market_mispricing_potential *
    volatility *
    recency
)


---

5.2 信息增益评分（LLM判断）

High:
- pricing
- supply shock
- margin structure

Medium:
- market size
- competitors

Low:
- generic overview


---

6. Search Execution Strategy（关键）

6.1 搜索不是一次，而是 3 轮

Round 1：Exploration（发散）

broad queries

Wikipedia / reports / news


Round 2：Precision（收敛）

financial metrics

supply chain

pricing


Round 3：Contradiction（反证）

bearish views

crash scenarios

short reports



---

7. Anti-LLM Collapse Rule（非常关键）

禁止以下行为：

❌ Bad

“总结行业”

“直接回答趋势”

“只看一篇报告”


✅ Required

多源交叉验证

正反叙事并存

数据优先于文本



---

8. Cross-Language Search Expansion Engine

自动生成：

def expand_query(term):
    return [
        f"{term}",
        f"{term} industry analysis",
        f"{term} supply chain",
        f"{term} 市场结构",
        f"{term} 价格机制",
        f"{term} crisis shortage oversupply"
    ]


---

9. Output Interface (给后续LLM用)

搜索层只输出：

FACTS:
  - data points
  - pricing data
  - market structure

ENTITIES:
  - companies
  - regulators
  - exchanges

SIGNALS:
  - supply shock
  - demand change
  - policy shift

CONFLICTS:
  - bullish vs bearish info


---

10. Recursive System（你想要的关键结构）

Industry Agent
    ↓
Sector Agent
    ↓
Company Agent
    ↓
Financial Agent
    ↓
Event Agent


---

11. 本质升级点（非常重要）

你现在的问题本质是：

> ❌ LLM在“理解搜索” ✅ 应该是“搜索在扩展世界模型”




---

12. 一句话总结这个spec

> 把 search 从“问答接口”升级为“信息空间生成器（Information Manifold Generator）”




---

如果你下一步要做工程化，我可以继续帮你拆：

🔧 Search Agent runtime architecture（可直接写代码）

🔧 Kimi / GPT / Claude 多模型协作层

🔧 股票筛选 pipeline（industry → factor → alpha）

🔧 自动构建多空组合 scoring system


这个体系可以直接从 demo 进化到 quant research pipeline。