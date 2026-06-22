"""V2.1 Report output — renders ScanOutput into Meta System Report format.

Report sections:
1. System Mapping (SV/FV/CV/LV) — L0 + L1
2. System Equation — L2
3. Driver Set — L3
4. Regime State — L4
5. Distortion Analysis — L5
6. Alpha Signal — L6
7. Investment Mapping (optional) — L7
+ Key Fragilities
+ Gate Validation
"""

from __future__ import annotations

from structflow.models import ScanOutput


def render_report(output: ScanOutput) -> str:
    """Render ScanOutput into the V2.1 Meta System Report format."""
    sections = [
        _header(output),
        _section_system_mapping(output),
        _section_system_equation(output),
        _section_driver_set(output),
        _section_regime_state(output),
        _section_distortion(output),
        _section_alpha_signal(output),
        _section_portfolio(output),
        _section_key_fragilities(output),
        _section_gate_validation(output),
    ]
    return "\n".join(sections)


def _header(output: ScanOutput) -> str:
    region_str = f" ({output.region})" if output.region else ""
    return f"""# Meta System Report: {output.industry}{region_str}

**Time Horizon**: {output.time_horizon.value}
**System**: Meta-Generalization Layer V2.1

---"""


def _section_system_mapping(output: ScanOutput) -> str:
    meta = output.meta
    var = output.variables
    lines = [
        "## 1. System Mapping",
        "",
        f"### System Type",
        f"{meta.system_type}",
        "",
        f"### Core Function",
        f"{meta.core_function}",
        "",
        f"### State Variables (SV)",
    ]
    for sv in var.state_variables:
        lines.append(f"- {sv}")
    lines.extend(["", f"### Flow Variables (FV)"])
    for fv in var.flow_variables:
        lines.append(f"- {fv}")
    lines.extend(["", f"### Control Variables (CV)"])
    for cv in var.control_variables:
        lines.append(f"- {cv}")
    lines.extend(["", f"### Latent Variables (LV)"])
    for lv in var.latent_variables:
        lines.append(f"- {lv}")
    lines.extend([
        "",
        f"### Exogenous Drivers",
    ])
    for ed in meta.exogenous_drivers:
        lines.append(f"- {ed}")
    lines.extend([
        "",
        f"### Endogenous Feedback Loops",
    ])
    for fl in meta.endogenous_feedback_loops:
        lines.append(f"- {fl}")
    lines.append("")
    return "\n".join(lines) + "---\n"


def _section_system_equation(output: ScanOutput) -> str:
    eq = output.equation
    total = eq.flow_weight + eq.control_weight + eq.latent_weight
    lines = [
        "## 2. System Equation",
        "",
        "ΔState = α × Flow + β × Control + γ × Latent",
        "",
        f"- **α (Flow Weight)**: {eq.flow_weight:.2f}",
        f"- **β (Control Weight)**: {eq.control_weight:.2f}",
        f"- **γ (Latent Weight)**: {eq.latent_weight:.2f}",
        f"- **Total (α+β+γ)**: {total:.2f}",
        "",
    ]
    return "\n".join(lines) + "---\n"


def _section_driver_set(output: ScanOutput) -> str:
    lines = ["## 3. Driver Set", ""]
    lines.append("| Driver | Type | Direction | Elasticity | Lag | Volatility | Dependency |")
    lines.append("|--------|------|-----------|------------|-----|------------|------------|")
    for d in output.drivers.drivers:
        lines.append(
            f"| {d.name} | {d.type} | {d.direction} | {d.elasticity:.2f} | {d.lag} | {d.volatility:.2f} | {d.system_dependency:.2f} |"
        )
    lines.append("")
    return "\n".join(lines) + "---\n"


def _section_regime_state(output: ScanOutput) -> str:
    reg = output.regime
    lines = [
        "## 4. Regime State",
        "",
        f"- **Current Regime**: {reg.current_regime}",
        f"- **Confidence**: {reg.regime_confidence:.0%}",
        f"- **Regime Drivers**:",
    ]
    for driver in reg.regime_drivers:
        lines.append(f"  - {driver}")
    lines.append("")
    return "\n".join(lines) + "---\n"


def _section_distortion(output: ScanOutput) -> str:
    dist = output.distortion
    lines = [
        "## 5. Distortion Analysis",
        "",
        f"### Market Belief",
        f"{dist.market_belief}",
        "",
        f"### True Drivers",
    ]
    for td in dist.true_drivers:
        lines.append(f"- {td}")
    lines.extend(["", f"### Mispricing Sources"])
    for ms in dist.mispricing_sources:
        lines.append(f"- {ms}")
    lines.extend([
        "",
        f"- **Distortion Score**: {dist.distortion_score:.0%}",
        "",
    ])
    return "\n".join(lines) + "---\n"


def _section_alpha_signal(output: ScanOutput) -> str:
    alpha = output.alpha
    lines = [
        "## 6. Alpha Signal",
        "",
        f"### Consensus View",
        f"{alpha.consensus_view}",
        "",
        f"### Structural View",
        f"{alpha.structural_view}",
        "",
        f"### Mispricing",
        f"{alpha.mispricing}",
        "",
        f"### Alpha Signal",
        f"{alpha.alpha_signal}",
        "",
        f"- **Confidence**: {alpha.confidence:.0%}",
        "",
    ]
    return "\n".join(lines) + "---\n"


def _section_portfolio(output: ScanOutput) -> str:
    if not output.portfolio:
        return ""
    portfolio = output.portfolio
    lines = ["## 7. Investment Mapping", ""]

    lines.append("### Best Positioned")
    for entity in portfolio.best_positioned_entities:
        lines.append(f"- **{entity.name}** ({entity.role}): {entity.reason}")
    lines.append("")

    lines.append("### Overvalued")
    for entity in portfolio.overvalued_entities:
        lines.append(f"- **{entity.name}** ({entity.role}): {entity.reason}")
    lines.append("")

    lines.append("### Fragile")
    for entity in portfolio.fragile_entities:
        lines.append(f"- **{entity.name}** ({entity.role}): {entity.reason}")
    lines.append("")
    return "\n".join(lines) + "---\n"


def _section_key_fragilities(output: ScanOutput) -> str:
    lines = ["## Key Fragilities", ""]
    if output.key_fragilities:
        for fragility in output.key_fragilities:
            lines.append(f"- ⚠️ {fragility}")
    else:
        lines.append("- No critical fragilities identified.")
    lines.append("")
    return "\n".join(lines) + "---\n"


def _section_gate_validation(output: ScanOutput) -> str:
    lines = ["## Gate Validation", ""]
    for gate in output.gate_validation.gates:
        icon = "✅" if gate.passed else "❌"
        lines.append(f"- {icon} **{gate.gate_name}**: {gate.reason}")
    lines.append("")
    if output.gate_validation.all_passed:
        lines.append("**All gates passed.** Output is structurally valid.")
    else:
        failed = ", ".join(g.gate_name for g in output.gate_validation.failed_gates)
        lines.append(f"**⚠️ Failed gates: {failed}** — Output may be incomplete.")
    return "\n".join(lines)
