"""Adversarial challenge: LLM challenges its own output for deeper analysis.

V2: challenges L1-L6 (L0 is meta, L7 is optional mapping).
Each challenge acts as "devil's advocate" to find gaps and errors.
"""

from __future__ import annotations

from typing import Optional

from rich.console import Console

from structflow.llm_client import LLMClient
from structflow.models import (
    L1StructureDecomposition,
    L2FlowAnalysis,
    L3RiskAnalysis,
    L4DriverAnalysis,
    L5ScenarioAnalysis,
    L6AlphaAnalysis,
)

console = Console()

# ── L1 Challenge ──────────────────────────────────────────────

CHALLENGE_L1_PROMPT = """你是一个严格的行业分析师，现在需要你挑战以下行业结构分析的完整性和准确性。

## 原始分析
行业: {industry}
角色识别:
{roles_summary}

权力矩阵:
- 定价权: {pricing_power}
- 进入壁垒: {entry_power}
- 标准控制: {standard_power}
- 资本控制: {capital_power}
- 数据控制: {data_power}

## 你的任务
扮演"魔鬼代言人"，从以下角度挑战这个分析：

1. **遗漏角色**: 是否有重要的行业参与者被遗漏？特别是 Capital Provider 角色是否被充分识别？
2. **权力误判**: 权力矩阵中是否有维度被错误归因？谁实际上控制了什么？
3. **隐藏控制者**: 是否有看似不相关但实际上控制行业的实体？
4. **证据不足**: 每个角色的 evidence 是否足够具体？是否有"强"这种模糊表述？
5. **动态变化**: 当前的权力结构是否在快速变化？

请输出修正后的完整分析，用JSON格式。如果你认为原始分析已经足够好，直接返回原始分析即可。
"""


def challenge_l1(
    client: LLMClient,
    industry: str,
    l1: L1StructureDecomposition,
    context_data: Optional[str] = None,
) -> L1StructureDecomposition:
    """Challenge and refine L1 output."""
    power = l1.power_matrix
    roles_summary = "\n".join(
        f"- {r.role_type}: {', '.join(r.entities)} — {r.description} [evidence: {r.evidence}]"
        for r in l1.roles
    )
    prompt = CHALLENGE_L1_PROMPT.format(
        industry=industry,
        roles_summary=roles_summary,
        pricing_power=power.pricing_power,
        entry_power=power.entry_power,
        standard_power=power.standard_power,
        capital_power=power.capital_power,
        data_power=power.data_power,
    )
    console.print("  [dim]⚔ 挑战L1: 寻找遗漏角色和权力误判...[/dim]")
    return client.structured_call(prompt, L1StructureDecomposition, context_data=context_data)


# ── L2 Challenge ──────────────────────────────────────────────

CHALLENGE_L2_PROMPT = """你是一个严格的行业分析师，现在需要你挑战以下行业流动分析的完整性。

## 原始分析
行业: {industry}

现金流节点: {cash_nodes}
信息流节点: {info_nodes}
风险流节点: {risk_nodes}
注意力流节点: {attention_nodes}

## 你的任务
从以下角度挑战这个分析：

1. **遗漏的流动**: 是否有重要的资金流、信息流、风险流或注意力流被遗漏？
2. **注意力流**: 注意力流是否被充分分析？注意力如何转化为现金流？
3. **隐藏流动**: 是否有影子流动（如：衍生品市场、跨境流动、暗池）？
4. **时间维度**: 这些流动在短期内和长期内是否一致？
5. **极端情况**: 在极端情况下（如：金融危机、政策突变），这些流动会如何变化？

请输出修正后的完整分析，用JSON格式。
"""


def challenge_l2(
    client: LLMClient,
    industry: str,
    l2: L2FlowAnalysis,
    context_data: Optional[str] = None,
) -> L2FlowAnalysis:
    """Challenge and refine L2 output."""
    prompt = CHALLENGE_L2_PROMPT.format(
        industry=industry,
        cash_nodes=" -> ".join(n.entity for n in l2.cash_nodes),
        info_nodes="; ".join(f"{n.entity}({n.description})" for n in l2.information_nodes),
        risk_nodes="; ".join(f"{n.entity}({n.description})" for n in l2.risk_nodes),
        attention_nodes="; ".join(f"{n.entity}({n.description})" for n in l2.attention_nodes),
    )
    console.print("  [dim]⚔ 挑战L2: 寻找遗漏流动和注意力缺口...[/dim]")
    return client.structured_call(prompt, L2FlowAnalysis, context_data=context_data)


# ── L3 Challenge ──────────────────────────────────────────────

CHALLENGE_L3_PROMPT = """你是一个严格的风险分析师，现在需要你挑战以下风险归属分析的准确性。

## 原始分析
行业: {industry}

风险集中点:
{risk_concentrations}

利润-风险分离:
- 谁赚钱最多: {profit_owner}
- 谁承担风险最多: {risk_owner}
- 分离程度: {gap_score}

## 你的任务
从以下角度挑战这个分析：

1. **遗漏风险**: 是否有重要的风险集中点被遗漏？尾部风险在哪里？
2. **风险转移链**: 风险是否被多层转移？最终承担者真的是{risk_owner}吗？
3. **利润归属**: {profit_owner}真的是最大获利者吗？是否有隐形获利者？
4. **gap_score合理性**: 分离程度评分是否准确？是否有被低估的道德风险？
5. **系统性风险**: 如果最大风险实体崩溃，连锁反应如何？

请输出修正后的完整分析，用JSON格式。
"""


def challenge_l3(
    client: LLMClient,
    industry: str,
    l3: L3RiskAnalysis,
    context_data: Optional[str] = None,
) -> L3RiskAnalysis:
    """Challenge and refine L3 output."""
    risk_lines = "\n".join(
        f"  - {rc.entity}: {rc.risk_type} (severity={rc.severity})"
        for rc in l3.risk_concentrations
    )
    prompt = CHALLENGE_L3_PROMPT.format(
        industry=industry,
        risk_concentrations=risk_lines,
        profit_owner=l3.profit_risk_separation.profit_owner,
        risk_owner=l3.profit_risk_separation.risk_owner,
        gap_score=l3.profit_risk_separation.gap_score,
    )
    console.print("  [dim]⚔ 挑战L3: 验证风险归属和利润-风险分离...[/dim]")
    return client.structured_call(prompt, L3RiskAnalysis, context_data=context_data)


# ── L4 Challenge ──────────────────────────────────────────────

CHALLENGE_L4_PROMPT = """你是一个严格的行业策略师，现在需要你挑战以下驱动因子分析的完整性。

## 原始分析
行业: {industry}

驱动因子:
{drivers_summary}

权重总和: {total_weight}

## 你的任务
从以下角度挑战这个分析：

1. **遗漏驱动因子**: 是否有重要的驱动因子被遗漏？（如：技术变革、人口结构、地缘政治）
2. **权重合理性**: 各驱动因子的权重是否合理？最重要的因子是否被低估？
3. **方向判断**: 每个驱动因子的方向（+/-）是否准确？
4. **置信度**: 置信度评估是否过于乐观或悲观？
5. **交互效应**: 驱动因子之间是否有重要的交互效应被忽略？

请输出修正后的完整分析，用JSON格式。确保权重总和=1.0。
"""


def challenge_l4(
    client: LLMClient,
    industry: str,
    l4: L4DriverAnalysis,
    context_data: Optional[str] = None,
) -> L4DriverAnalysis:
    """Challenge and refine L4 output."""
    drivers_summary = "\n".join(
        f"  - {d.name}: importance={d.importance}, direction={d.direction}, confidence={d.confidence}"
        for d in l4.drivers
    )
    total_weight = sum(d.importance for d in l4.drivers)
    prompt = CHALLENGE_L4_PROMPT.format(
        industry=industry,
        drivers_summary=drivers_summary,
        total_weight=f"{total_weight:.2f}",
    )
    console.print("  [dim]⚔ 挑战L4: 验证驱动因子完整性和权重...[/dim]")
    return client.structured_call(prompt, L4DriverAnalysis, context_data=context_data)


# ── L5 Challenge ──────────────────────────────────────────────

CHALLENGE_L5_PROMPT = """你是一个严格的情景分析师，现在需要你挑战以下场景推演的合理性。

## 原始分析
行业: {industry}

Bull (概率={bull_prob}): {bull_triggers}
Base (概率={base_prob}): {base_triggers}
Bear (概率={bear_prob}): {bear_triggers}
概率总和: {total_prob}

## 你的任务
从以下角度挑战这个分析：

1. **概率合理性**: 三个场景的概率分配是否合理？Base是否被高估？
2. **触发条件**: 触发条件是否足够具体？是否遗漏了关键触发因素？
3. **尾部风险**: Bear场景是否足够悲观？是否遗漏了黑天鹅事件？
4. **信号缺失**: 每个场景的触发条件是否可以被提前观测到？
5. **路径依赖**: 从Base到Bull/Bear的路径是否清晰？

请输出修正后的完整分析，用JSON格式。确保概率总和=1.0。
"""


def challenge_l5(
    client: LLMClient,
    industry: str,
    l5: L5ScenarioAnalysis,
    context_data: Optional[str] = None,
) -> L5ScenarioAnalysis:
    """Challenge and refine L5 output."""
    total_prob = l5.bull.probability + l5.base.probability + l5.bear.probability
    prompt = CHALLENGE_L5_PROMPT.format(
        industry=industry,
        bull_prob=l5.bull.probability,
        bull_triggers="; ".join(l5.bull.triggers),
        base_prob=l5.base.probability,
        base_triggers="; ".join(l5.base.triggers),
        bear_prob=l5.bear.probability,
        bear_triggers="; ".join(l5.bear.triggers),
        total_prob=f"{total_prob:.2f}",
    )
    console.print("  [dim]⚔ 挑战L5: 验证场景概率和触发条件...[/dim]")
    return client.structured_call(prompt, L5ScenarioAnalysis, context_data=context_data)


# ── L6 Challenge (MOST IMPORTANT) ─────────────────────────────

CHALLENGE_L6_PROMPT = """你是一个资深投资经理，现在需要你对抗性验证以下Alpha thesis的可靠性。

## 原始分析
行业: {industry}

市场共识: {consensus}
结构现实: {reality}
错误定价: {mispricing}
Alpha thesis: {alpha_thesis}

## 你的任务
这是整个系统价值最高的部分。你必须严格挑战这个Alpha thesis：

1. **共识是否真实**: 市场共识的描述是否准确？是否是稻草人论证？
2. **现实是否可靠**: 结构现实的判断是否有数据支撑？是否过度自信？
3. **错误定价是否存在**: 这个所谓的"错误定价"是否已经被市场修正？
4. **Alpha thesis可操作性**: 这个thesis是否可执行？时间窗口是什么？
5. **反面论证**: 如果你站在市场共识一边，如何反驳这个Alpha thesis？
6. **风险**: 如果这个thesis是错的，最大的风险是什么？

请输出修正后的完整分析，用JSON格式。只有当你发现真正的问题时才修改。
"""


def challenge_l6(
    client: LLMClient,
    industry: str,
    l6: L6AlphaAnalysis,
    context_data: Optional[str] = None,
) -> L6AlphaAnalysis:
    """Challenge and refine L6 output — the most important challenge."""
    prompt = CHALLENGE_L6_PROMPT.format(
        industry=industry,
        consensus=l6.consensus,
        reality=l6.reality,
        mispricing=l6.mispricing,
        alpha_thesis=l6.alpha_thesis,
    )
    console.print("  [dim]⚔ 挑战L6: 对抗性验证Alpha thesis...[/dim]")
    return client.structured_call(prompt, L6AlphaAnalysis, context_data=context_data)
