"""Adversarial challenge: LLM challenges its own output for deeper analysis."""

from __future__ import annotations

from typing import Optional

from rich.console import Console

from structflow.llm_client import LLMClient
from structflow.models import (
    L1StructureDecomposition,
    L2FlowRiskAnalysis,
    L3ScoringRanking,
)

console = Console()

CHALLENGE_L1_PROMPT = """你是一个严格的行业分析师，现在需要你挑战以下行业结构分析的完整性和准确性。

## 原始分析
行业: {industry}
角色识别:
{roles_summary}

权力矩阵:
- 定价权: {pricing_power}
- 进入壁垒: {entry_control}
- 数据控制: {data_control}
- 切换成本: {switching_cost}
- 标准控制: {standard_control}

## 你的任务
扮演"魔鬼代言人"，从以下角度挑战这个分析：

1. **遗漏角色**: 是否有重要的行业参与者被遗漏？（如：供应商、替代品生产者、互补品提供者、行业协会）
2. **权力误判**: 权力矩阵中是否有维度被错误归因？谁实际上控制了什么？
3. **隐藏控制者**: 是否有看似不相关但实际上控制行业的实体？（如：评级机构、标准组织、基础设施提供者）
4. **动态变化**: 当前的权力结构是否在快速变化？哪些力量正在重塑权力分布？

请输出修正后的完整分析，用JSON格式。如果你认为原始分析已经足够好，直接返回原始分析即可。
"""

CHALLENGE_L2_PROMPT = """你是一个严格的行业分析师，现在需要你挑战以下行业流动与风险分析的完整性。

## 原始分析
行业: {industry}

钱流链条: {cash_flow_chain}
价值捕获点: {value_capture_points}
信息不对称节点: {info_asymmetry}
风险积累点: {risk_points}
隐藏补贴: {hidden_subsidies}

关键问题回答:
- 谁在补贴系统: {subsidy_answer}
- 风险集中在哪里: {risk_concentration}
- 利润与风险是否分离: {profit_risk_separation}

## 你的任务
从以下角度挑战这个分析：

1. **遗漏的流动**: 是否有重要的资金流、信息流或风险流被遗漏？（如：衍生品市场、影子银行、跨境流动）
2. **隐藏补贴**: 是否还有未识别的隐性补贴？（如：税收优惠、监管套利、数据变现、交叉补贴）
3. **风险转移链**: 风险是否被多层转移？最终承担者是谁？
4. **时间维度**: 这些流动在短期内和长期内是否一致？是否有周期性变化？
5. **尾部风险**: 极端情况下（如：金融危机、政策突变），这些流动会如何变化？

请输出修正后的完整分析，用JSON格式。
"""

CHALLENGE_L3_PROMPT = """你是一个严格的行业分析师，现在需要你挑战以下评分和排序的合理性。

## 原始评分
行业: {industry}

行业评分:
- 控制力: {industry_control}
- 利润捕获: {industry_profit}
- 风险转移: {industry_risk}
- 信息优势: {industry_info}
- 激励对齐: {industry_incentive}

公司排名:
{company_rankings}

行业阶段: {phase}
阶段信号: {phase_signals}

## 你的任务
从以下角度挑战这个评分：

1. **评分一致性**: 各公司的评分是否与其角色和权力矩阵一致？是否有公司被高估或低估？
2. **相对排名**: 公司之间的相对排名是否合理？为什么A比B高？
3. **阶段判断**: 行业阶段判断是否准确？是否有矛盾的信号？
4. **动态视角**: 这些评分在1-3年内会如何变化？哪些公司会上升/下降？
5. **对标验证**: 与类似行业（如：其他大宗商品、其他金融资产）相比，这些评分是否合理？

请输出修正后的完整评分，用JSON格式。确保每个公司的评分都有明确的区分度，不要给多家公司相同的分数。
"""


def _build_roles_summary(l1: L1StructureDecomposition) -> str:
    lines = []
    for role in l1.roles:
        entities = ", ".join(role.entities)
        lines.append(f"- {role.role_type}: {entities} — {role.description}")
    return "\n".join(lines)


def _build_flow_summary(l2: L2FlowRiskAnalysis) -> dict[str, str]:
    return {
        "cash_flow_chain": " → ".join(n.entity for n in l2.cash_flow_chain),
        "value_capture_points": "; ".join(f"{n.entity}({n.description})" for n in l2.value_capture_points),
        "info_asymmetry": "; ".join(f"{n.entity}({n.description})" for n in l2.information_asymmetry_nodes),
        "risk_points": "; ".join(f"{n.entity}({n.description})" for n in l2.risk_accumulation_points),
        "hidden_subsidies": "; ".join(f"{n.entity}({n.description})" for n in l2.hidden_subsidy_sources) if l2.hidden_subsidy_sources else "无",
    }


def _build_company_rankings(l3: L3ScoringRanking) -> str:
    lines = []
    for company in l3.companies_ranked[:10]:
        sv = company.score_vector
        lines.append(
            f"- {company.name} ({company.role}): "
            f"控制={sv.control_score}, 利润={sv.profit_capture_score}, "
            f"风险转移={sv.risk_displacement_score}, 信息={sv.information_advantage_score}, "
            f"激励={sv.incentive_alignment_score}, 健康度={company.structural_health}"
        )
    return "\n".join(lines)


def challenge_l1(
    client: LLMClient,
    industry: str,
    l1: L1StructureDecomposition,
    context_data: Optional[str] = None,
) -> L1StructureDecomposition:
    """Challenge and refine L1 output."""
    power = l1.power_matrix
    prompt = CHALLENGE_L1_PROMPT.format(
        industry=industry,
        roles_summary=_build_roles_summary(l1),
        pricing_power=power.pricing_power,
        entry_control=power.entry_control,
        data_control=power.data_control,
        switching_cost=power.switching_cost,
        standard_control=power.standard_control,
    )
    console.print("  [dim]⚔ 挑战L1: 寻找遗漏角色和权力误判...[/dim]")
    return client.structured_call(prompt, L1StructureDecomposition, context_data=context_data)


def challenge_l2(
    client: LLMClient,
    industry: str,
    l2: L2FlowRiskAnalysis,
    context_data: Optional[str] = None,
) -> L2FlowRiskAnalysis:
    """Challenge and refine L2 output."""
    flow = _build_flow_summary(l2)
    prompt = CHALLENGE_L2_PROMPT.format(
        industry=industry,
        cash_flow_chain=flow["cash_flow_chain"],
        value_capture_points=flow["value_capture_points"],
        info_asymmetry=flow["info_asymmetry"],
        risk_points=flow["risk_points"],
        hidden_subsidies=flow["hidden_subsidies"],
        subsidy_answer=l2.subsidy_answer,
        risk_concentration=l2.risk_concentration_answer,
        profit_risk_separation=l2.profit_risk_separation_answer,
    )
    console.print("  [dim]⚔ 挑战L2: 寻找遗漏流动和隐藏补贴...[/dim]")
    return client.structured_call(prompt, L2FlowRiskAnalysis, context_data=context_data)


def challenge_l3(
    client: LLMClient,
    industry: str,
    l3: L3ScoringRanking,
    context_data: Optional[str] = None,
) -> L3ScoringRanking:
    """Challenge and refine L3 output."""
    score = l3.industry_score
    prompt = CHALLENGE_L3_PROMPT.format(
        industry=industry,
        industry_control=score.control_score,
        industry_profit=score.profit_capture_score,
        industry_risk=score.risk_displacement_score,
        industry_info=score.information_advantage_score,
        industry_incentive=score.incentive_alignment_score,
        company_rankings=_build_company_rankings(l3),
        phase=l3.phase.stage.value,
        phase_signals="; ".join(l3.phase.reasoning_signals),
    )
    console.print("  [dim]⚔ 挑战L3: 验证评分合理性和排名区分度...[/dim]")
    return client.structured_call(prompt, L3ScoringRanking, context_data=context_data)
