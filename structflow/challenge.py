"""Adversarial challenge: LLM challenges its own output for deeper analysis.

V2.1: challenges L1-L6 (L0 is meta, L7 is optional mapping).
Each challenge acts as "devil's advocate" to find gaps and errors.

Challenge layers:
- L1: Variable Mapping — are all variables correctly classified?
- L2: System Equation — are the weights correctly assessed?
- L3: Driver Set — are drivers truly from SV/FV/CV/LV?
- L4: Regime State — is the regime identification accurate?
- L5: Distortion Analysis — is the mispricing real or imagined?
- L6: Alpha Signal — is the signal actionable and grounded?
"""

from __future__ import annotations

from typing import Optional

from rich.console import Console

from structflow.llm_client import LLMClient
from structflow.models import (
    AlphaSignal,
    DistortionAnalysis,
    DriverSet,
    RegimeState,
    SystemEquation,
    VariableMapping,
)

console = Console()


# ── L1 Challenge: Variable Mapping ────────────────────────────

CHALLENGE_L1_PROMPT = """你是一个严格的系统分析师，现在需要你挑战以下变量映射的完整性和准确性。

## 原始分析
系统: {industry}

变量映射:
- 状态变量 (SV): {state_vars}
- 流变量 (FV): {flow_vars}
- 控制变量 (CV): {control_vars}
- 潜变量 (LV): {latent_vars}

## 你的任务
扮演"魔鬼代言人"，从以下角度挑战：

1. **变量分类错误**: 是否有变量被错误归类？(如：将流变量误分为状态变量)
2. **遗漏变量**: 是否有重要的变量被遗漏？特别是潜变量 (LV) 是否充分？
3. **去实体化**: 是否有变量实际上是实体名称而非变量？(如："苹果公司"不是变量，"智能手机市场份额"才是)
4. **去叙事化**: 叙事是否只出现在 LV 中？是否有叙事混入了 SV/FV/CV？
5. **变量粒度**: 变量是否太笼统或太具体？

请输出修正后的完整分析，用JSON格式。如果原始分析已足够好，直接返回原始分析。
"""


def challenge_l1(
    client: LLMClient,
    industry: str,
    l1: VariableMapping,
    context_data: Optional[str] = None,
) -> VariableMapping:
    """Challenge and refine L1 variable mapping."""
    prompt = CHALLENGE_L1_PROMPT.format(
        industry=industry,
        state_vars="; ".join(l1.state_variables),
        flow_vars="; ".join(l1.flow_variables),
        control_vars="; ".join(l1.control_variables),
        latent_vars="; ".join(l1.latent_variables),
    )
    console.print("  [dim]⚔ 挑战L1: 验证变量分类和完整性...[/dim]")
    return client.structured_call(prompt, VariableMapping, context_data=context_data)


# ── L2 Challenge: System Equation ─────────────────────────────

CHALLENGE_L2_PROMPT = """你是一个严格的系统动力学专家，现在需要你挑战以下系统方程的准确性。

## 原始分析
系统: {industry}

系统方程:
- 流变量权重 (α): {flow_weight}
- 控制变量权重 (β): {control_weight}
- 潜变量权重 (γ): {latent_weight}
- 总和: {total}

## 变量映射参考
- SV: {state_vars}
- FV: {flow_vars}
- CV: {control_vars}
- LV: {latent_vars}

## 你的任务
1. **权重合理性**: α/β/γ 的分配是否合理？哪种变量真的在驱动系统变化？
2. **遗漏维度**: 是否有重要的动态被忽略？
3. **时间维度**: 在不同时间尺度上，权重是否会变化？
4. **反馈回路**: 反馈回路是否被充分体现在权重中？

请输出修正后的完整分析，用JSON格式。确保 α+β+γ=1.0。
"""


def challenge_l2(
    client: LLMClient,
    industry: str,
    l2: SystemEquation,
    l1: VariableMapping,
    context_data: Optional[str] = None,
) -> SystemEquation:
    """Challenge and refine L2 system equation."""
    total = l2.flow_weight + l2.control_weight + l2.latent_weight
    prompt = CHALLENGE_L2_PROMPT.format(
        industry=industry,
        flow_weight=l2.flow_weight,
        control_weight=l2.control_weight,
        latent_weight=l2.latent_weight,
        total=f"{total:.2f}",
        state_vars="; ".join(l1.state_variables),
        flow_vars="; ".join(l1.flow_variables),
        control_vars="; ".join(l1.control_variables),
        latent_vars="; ".join(l1.latent_variables),
    )
    console.print("  [dim]⚔ 挑战L2: 验证系统方程权重...[/dim]")
    return client.structured_call(prompt, SystemEquation, context_data=context_data)


# ── L3 Challenge: Driver Sources ──────────────────────────────

CHALLENGE_L3_PROMPT = """你是一个严格的驱动因子分析师，现在需要你挑战以下驱动因子集合的可靠性。

## 原始分析
系统: {industry}

驱动因子:
{drivers_summary}

## 变量映射参考
- SV: {state_vars}
- FV: {flow_vars}
- CV: {control_vars}
- LV: {latent_vars}

## 你的任务
1. **驱动溯源**: 每个驱动因子是否能追溯到 SV/FV/CV/LV 的变化？哪些无法追溯？
2. **去叙事化**: 是否有驱动因子实际上是叙事而非变量变化？
3. **遗漏驱动**: 是否有重要的驱动因子被遗漏？
4. **参数合理性**: elasticity/volatility/system_dependency 的评估是否准确？
5. **交互效应**: 驱动因子之间的交互效应是否被忽略？

请输出修正后的完整分析，用JSON格式。
"""


def challenge_l3(
    client: LLMClient,
    industry: str,
    l3: DriverSet,
    l1: VariableMapping,
    context_data: Optional[str] = None,
) -> DriverSet:
    """Challenge and refine L3 driver set."""
    drivers_summary = "\n".join(
        f"  - {d.name} (type={d.type}, dir={d.direction}, elasticity={d.elasticity}, lag={d.lag}, vol={d.volatility}, dep={d.system_dependency})"
        for d in l3.drivers
    )
    prompt = CHALLENGE_L3_PROMPT.format(
        industry=industry,
        drivers_summary=drivers_summary,
        state_vars="; ".join(l1.state_variables),
        flow_vars="; ".join(l1.flow_variables),
        control_vars="; ".join(l1.control_variables),
        latent_vars="; ".join(l1.latent_variables),
    )
    console.print("  [dim]⚔ 挑战L3: 验证驱动因子溯源...[/dim]")
    return client.structured_call(prompt, DriverSet, context_data=context_data)


# ── L4 Challenge: Regime State ────────────────────────────────

CHALLENGE_L4_PROMPT = """你是一个严格的宏观分析师，现在需要你挑战以下系统状态识别的准确性。

## 原始分析
系统: {industry}

当前状态: {current_regime} (置信度: {regime_confidence})
状态驱动因子: {regime_drivers}

## 驱动因子参考
{drivers_summary}

## 你的任务
1. **状态判断**: {current_regime} 是否准确？是否有可能实际上是另一个状态？
2. **置信度**: 置信度评估是否合理？是否过于自信？
3. **状态转换**: 系统是否正在从一种状态转向另一种？
4. **驱动因子**: 状态驱动因子是否充分？是否遗漏了关键信号？
5. **黑天鹅**: 是否有未被识别的尾部风险可能改变状态？

请输出修正后的完整分析，用JSON格式。
"""


def challenge_l4(
    client: LLMClient,
    industry: str,
    l4: RegimeState,
    l3: DriverSet,
    context_data: Optional[str] = None,
) -> RegimeState:
    """Challenge and refine L4 regime state."""
    drivers_summary = "\n".join(
        f"  - {d.name} ({d.type}, {d.direction}, dep={d.system_dependency})"
        for d in l3.drivers
    )
    prompt = CHALLENGE_L4_PROMPT.format(
        industry=industry,
        current_regime=l4.current_regime,
        regime_confidence=l4.regime_confidence,
        regime_drivers="; ".join(l4.regime_drivers),
        drivers_summary=drivers_summary,
    )
    console.print("  [dim]⚔ 挑战L4: 验证状态识别...[/dim]")
    return client.structured_call(prompt, RegimeState, context_data=context_data)


# ── L5 Challenge: Distortion Analysis ─────────────────────────

CHALLENGE_L5_PROMPT = """你是一个资深量化分析师，现在需要你挑战以下错配检测的可靠性。

## 原始分析
系统: {industry}

市场认知: {market_belief}
真实驱动: {true_drivers}
错配来源: {mispricing_sources}
错配程度: {distortion_score}

## 系统状态参考
当前状态: {current_regime} (置信度: {regime_confidence})

## 你的任务
1. **市场认知是否真实**: market_belief 的描述是否准确？是否是稻草人论证？
2. **真实驱动是否可靠**: true_drivers 是否有数据支撑？是否过度自信？
3. **错配是否真实存在**: 所谓的"错配"是否已经被市场修正？
4. **错配程度合理性**: distortion_score 是否被高估或低估？
5. **反面论证**: 如果站在市场共识一边，如何反驳这个错配检测？

请输出修正后的完整分析，用JSON格式。
"""


def challenge_l5(
    client: LLMClient,
    industry: str,
    l5: DistortionAnalysis,
    l4: RegimeState,
    context_data: Optional[str] = None,
) -> DistortionAnalysis:
    """Challenge and refine L5 distortion analysis."""
    prompt = CHALLENGE_L5_PROMPT.format(
        industry=industry,
        market_belief=l5.market_belief,
        true_drivers="; ".join(l5.true_drivers),
        mispricing_sources="; ".join(l5.mispricing_sources),
        distortion_score=l5.distortion_score,
        current_regime=l4.current_regime,
        regime_confidence=l4.regime_confidence,
    )
    console.print("  [dim]⚔ 挑战L5: 验证错配检测...[/dim]")
    return client.structured_call(prompt, DistortionAnalysis, context_data=context_data)


# ── L6 Challenge: Alpha Signal (MOST IMPORTANT) ───────────────

CHALLENGE_L6_PROMPT = """你是一个资深投资经理，现在需要你对抗性验证以下Alpha信号的可靠性。

## 原始分析
系统: {industry}

市场共识: {consensus_view}
结构视角: {structural_view}
错误定价: {mispricing}
Alpha信号: {alpha_signal}
置信度: {confidence}

## 错配分析参考
错配程度: {distortion_score}
市场认知: {market_belief}

## 你的任务
这是整个系统价值最高的部分。你必须严格挑战：

1. **共识是否真实**: consensus_view 的描述是否准确？
2. **结构视角是否可靠**: structural_view 是否有变量分析支撑？
3. **错误定价是否存在**: 这个"错误定价"是否已经被市场修正？
4. **Alpha信号可操作性**: 这个信号是否可执行？时间窗口是什么？
5. **反面论证**: 如果你站在市场共识一边，如何反驳这个Alpha信号？
6. **风险**: 如果这个信号是错的，最大的风险是什么？
7. **置信度**: confidence 是否合理？是否应考虑降低？

请输出修正后的完整分析，用JSON格式。只有发现真正问题时才修改。
"""


def challenge_l6(
    client: LLMClient,
    industry: str,
    l6: AlphaSignal,
    l5: DistortionAnalysis,
    context_data: Optional[str] = None,
) -> AlphaSignal:
    """Challenge and refine L6 alpha signal — the most important challenge."""
    prompt = CHALLENGE_L6_PROMPT.format(
        industry=industry,
        consensus_view=l6.consensus_view,
        structural_view=l6.structural_view,
        mispricing=l6.mispricing,
        alpha_signal=l6.alpha_signal,
        confidence=l6.confidence,
        distortion_score=l5.distortion_score,
        market_belief=l5.market_belief,
    )
    console.print("  [dim]⚔ 挑战L6: 对抗性验证Alpha信号...[/dim]")
    return client.structured_call(prompt, AlphaSignal, context_data=context_data)
