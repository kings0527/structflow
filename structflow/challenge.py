"""Adversarial challenge: LLM challenges its own output for deeper analysis.

V2.2: challenges L1-L6 with updated layer structure.
"""

from __future__ import annotations

from typing import Optional

from rich.console import Console

from structflow.llm_client import LLMClient
from structflow.models import (
    AlphaEngine,
    DistortionEngine,
    DriverSpace,
    FlowFeedbackSystem,
    InvestmentMapping,
    RegimeEngine,
    VariableMapping,
)

console = Console()


def challenge_l1(client, industry, l1: VariableMapping, context_data=None) -> VariableMapping:
    prompt = f"""你是一个严格的系统分析师，挑战以下变量映射。

系统: {industry}
SV: {'; '.join(l1.state_variables)}
FV: {'; '.join(l1.flow_variables)}
CV: {'; '.join(l1.control_variables)}
LV: {'; '.join(l1.latent_variables)}

挑战：1)变量分类错误 2)遗漏变量 3)去实体化(公司名≠变量) 4)叙事只在LV 5)变量粒度
输出修正后的JSON。"""
    console.print("  [dim]⚔ 挑战L1: 验证变量分类...[/dim]")
    return client.structured_call(prompt, VariableMapping, context_data=context_data)


def challenge_l2(client, industry, l2: DriverSpace, l1: VariableMapping, context_data=None) -> DriverSpace:
    drivers = "\n".join(f"  - {d.name} (maps={d.maps_to_variable}, cat={d.category}, dir={d.direction})" for d in l2.drivers)
    prompt = f"""你是一个严格的因果分析师，挑战以下驱动因子。

系统: {industry}
驱动因子:
{drivers}

挑战：1)每个driver是否真的maps_to_variable正确 2)遗漏驱动 3)叙事是否只映射LV 4)弹性/波动率合理性 5)非线性方向是否合理
输出修正后的JSON。"""
    console.print("  [dim]⚔ 挑战L2: 验证驱动绑定...[/dim]")
    return client.structured_call(prompt, DriverSpace, context_data=context_data)


def challenge_l3(client, industry, l3: FlowFeedbackSystem, l2: DriverSpace, context_data=None) -> FlowFeedbackSystem:
    loops = "\n".join(f"  - {l.loop_name} ({l.type}, amp={l.amplification_factor})" for l in l3.feedback_loops)
    prompt = f"""你是一个严格的系统动力学专家，挑战以下流与反馈系统。

系统: {industry}
流类型: {'; '.join(l3.flow_types)}
反馈回路:
{loops}

挑战：1)是否有重要流类型遗漏 2)回路机制是否真实 3)放大因子合理性 4)是否遗漏关键反馈 5)reinforcing/balancing分类是否准确
输出修正后的JSON。"""
    console.print("  [dim]⚔ 挑战L3: 验证反馈完整性...[/dim]")
    return client.structured_call(prompt, FlowFeedbackSystem, context_data=context_data)


def challenge_l4(client, industry, l4: RegimeEngine, l2: DriverSpace, context_data=None) -> RegimeEngine:
    prompt = f"""你是一个严格的宏观分析师，挑战以下状态识别。

系统: {industry}
当前状态: {l4.current_regime} (置信度: {l4.confidence})
下一状态: {l4.transition_probability.next_regime} (概率: {l4.transition_probability.probability})

挑战：1)状态判断是否准确 2)是否应考虑shock状态 3)转换概率合理性 4)是否遗漏关键驱动信号 5)阈值是否合理
输出修正后的JSON。"""
    console.print("  [dim]⚔ 挑战L4: 验证状态引擎...[/dim]")
    return client.structured_call(prompt, RegimeEngine, context_data=context_data)


def challenge_l5(client, industry, l5: DistortionEngine, l4: RegimeEngine, context_data=None) -> DistortionEngine:
    prompt = f"""你是一个资深量化分析师，挑战以下错配检测。

系统: {industry}
市场认知: {l5.market_belief}
结构真相: {l5.structural_truth}
错配来源: {'; '.join(l5.mispricing_sources)}
错配程度: {l5.distortion_score}

挑战：1)市场认知是否真实 2)结构真相是否有数据支撑 3)错配是否已被修正 4)distortion_score是否合理 5)反面论证
输出修正后的JSON。"""
    console.print("  [dim]⚔ 挑战L5: 验证错配检测...[/dim]")
    return client.structured_call(prompt, DistortionEngine, context_data=context_data)


def challenge_l6(client, industry, l6: AlphaEngine, l5: DistortionEngine, context_data=None) -> AlphaEngine:
    prompt = f"""你是一个资深投资经理，对抗性验证以下Alpha信号。

系统: {industry}
共识: {l6.consensus_view}
结构: {l6.structural_view}
错配: {l6.mispricing}
Alpha: {l6.alpha_signal}
方向: {l6.direction}
置信度: {l6.confidence}
错配程度: {l5.distortion_score}

挑战：1)Alpha是否与L2驱动一致(No Alpha Override) 2)是否参考了状态 3)方向是否合理 4)置信度是否过高 5)反面论证 6)如果Alpha是错的,最大风险
输出修正后的JSON。"""
    console.print("  [dim]⚔ 挑战L6: 对抗性验证Alpha信号...[/dim]")
    return client.structured_call(prompt, AlphaEngine, context_data=context_data)


# ── L7 Challenge (投资映射验证) ──────────────────────────────

def challenge_l7(client, industry, l7: InvestmentMapping, l6: AlphaEngine, context_data=None) -> InvestmentMapping:
    """挑战L7输出 — 检查与L6 alpha方向的一致性 + 资产合理性。"""
    best = ", ".join(a.asset for a in l7.best_positioned)
    overvalued = ", ".join(a.asset for a in l7.overvalued)
    fragile = ", ".join(a.asset for a in l7.fragile)
    prompt = f"""你是一个严格的投资组合经理，挑战以下投资映射。

系统: {industry}
L6 Alpha方向: {l6.direction} (置信度: {l6.confidence})
L6 Alpha信号: {l6.alpha_signal[:200]}

L7投资映射:
- Best Positioned: {best}
- Overvalued: {overvalued}
- Fragile: {fragile}

挑战：
1. **方向一致性**: L6说{l6.direction}，L7的best_positioned是否与这个方向一致？
   - 如果L6是long，best_positioned应该是做多候选；overvalued应该是做空候选
   - 如果L6是short，则相反
   - 如果矛盾，必须修正
2. **资产合理性**: 每个资产是否与系统结构相关？有无硬凑的？
3. **风险描述**: risk_profile是否基于实际价格？（不是编造的价格水平）
4. **遗漏**: 是否遗漏了重要的资产？
5. **暴露度**: exposure值是否合理？

输出修正后的JSON。"""
    console.print("  [dim]⚔ 挑战L7: 验证投资映射一致性...[/dim]")
    return client.structured_call(prompt, InvestmentMapping, context_data=context_data)
