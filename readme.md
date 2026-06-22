下面给一套行业扫描 Agent（Industry Scanner Agent）设计框架。目标不是“研究报告生成器”，而是一个可复用的结构识别 + 风险定位 + 机会排序系统。


---

一、系统目标（必须先锁死）

这个 Agent 只做三件事：

1. 识别行业结构（Structure Mapping）
2. 识别权力与风险分布（Power & Risk Mapping）
3. 输出可比较的评分向量（Comparable Score Vector）

不做：

不做“买卖建议”

不做情绪化分析

不做故事扩展



---

二、整体架构（四层系统）

L0：行业定义层（What is this system）
L1：结构拆解层（Who controls what）
L2：流动与风险层（How value moves）
L3：评分与排序层（How good is structure）


---

三、输入与输出定义

输入（Input Schema）

{
  "industry": "string",
  "region": "optional string",
  "time_horizon": "short|mid|long",
  "peer_set": ["optional comparable companies"]
}


---

输出（Output Schema）

{
  "industry_structure_score": {},
  "companies_ranked": [],
  "risk_map": {},
  "power_map": {},
  "key_fragilities": [],
  "structural_phase": ""
}


---

四、L0：行业定义层（必须强制执行）

任务

定义这个行业“本体”：

这个行业解决什么刚性需求？
是否可替代？
是否依赖政策/叙事？


---

强制输出

{
  "core_need": "",
  "substitution_risk": 0-1,
  "demand_stability": 0-1,
  "narrative_dependency": 0-1
}


---

五、L1：结构拆解层（核心）

必须识别四个角色

1. 生产者（Producer）
2. 支付者（Payer）
3. 中介者（Mediator）
4. 控制者（Controller）


---

必须输出“权力矩阵”

{
  "pricing_power": "谁决定价格",
  "entry_control": "谁控制进入门槛",
  "data_control": "谁掌握信息",
  "switching_cost": "用户退出难度",
  "standard_control": "谁定义行业标准"
}


---

关键约束（必须）

> 不允许只写描述，必须归因到“角色”



例如：

不能写“平台强”

必须写：“Controller dominates pricing + entry control”



---

六、L2：流动与风险层（最重要）

三条流必须完整追踪

1. Cash Flow（钱流）
2. Information Flow（信息流）
3. Risk Flow（风险流）


---

必须输出结构

{
  "cash_flow_chain": [],
  "value_capture_points": [],
  "information_asymmetry_nodes": [],
  "risk_accumulation_points": [],
  "hidden_subsidy_sources": []
}


---

强制规则

必须回答：

谁在持续补贴系统？
风险最终集中在哪里？
利润是否与风险分离？


---

七、L3：评分与排序层（核心输出）

1）结构评分向量（S Vector）

每个行业 / 公司必须输出：

{
  "control_score": 0-10,
  "profit_capture_score": 0-10,
  "risk_displacement_score": 0-10,
  "information_advantage_score": 0-10,
  "incentive_alignment_score": 0-10
}


---

2）结构健康度（关键）

Structural Health = 
(Control × Profit Capture × Info Advantage)
÷ (Risk Concentration + Incentive Distortion)


---

3）行业阶段识别（必须）

{
  "stage": "emergent | growth | mature | decline | disrupted",
  "reasoning_signals": []
}


---

八、关键“不可跳过节点”（Hard Gates）

Agent 必须强制执行以下检查：


---

Gate 1：是否识别控制权

如果没有：

> ❌ 直接判定输出无效




---

Gate 2：是否识别风险归属

必须回答：

利润归谁？风险归谁？


---

Gate 3：是否识别信息不对称

必须输出：

谁先知道

谁被延迟知道



---

Gate 4：是否存在隐藏流

必须检测：

补贴结构

政策依赖

账面利润 vs 真实现金流差异



---

Gate 5：是否可横向比较

输出必须可用于：

> 行业 vs 行业 / 公司 vs 公司



否则无效。


---

九、输出标准化（必须统一格式）

最终输出必须是：

# Industry Scan Report

## 1. Structure Map
## 2. Flow Map
## 3. Power Map
## 4. Risk Map
## 5. Score Vector
## 6. Structural Phase
## 7. Key Fragilities


---

十、Agent设计本质（非常关键）

这个系统不是：

NLP总结器

研报生成器


而是：

> 结构识别机器（Structural Intelligence System）



它的核心能力是：

把“叙事”还原成“权力 + 流动 + 风险结构”


---

十一、如果要进一步升级（可选扩展）

可以让代码agent再加三层：

L4：博弈层

行业内竞争策略互动


L5：反身性层

预期如何影响现实


L6：崩塌预测层

哪个结构最先断裂



---

十二、总结（最关键一句）

这个 Agent 的本质是：

> 用统一结构语言，把所有行业压缩成“权力-流动-风险”的可比较对象




---

如果下一步你要做工程实现，我可以帮你把这一套：

转成 Python 类结构

或 LangGraph / AutoGen agent graph

或 JSON schema + function calling spec


直接变成可运行系统。