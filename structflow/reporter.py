"""V2 Report output — renders ScanOutput into structured markdown with 8 sections."""

from __future__ import annotations

from structflow.models import ScanOutput


def render_report(output: ScanOutput) -> str:
    """Render ScanOutput into the V2 Industry Scan Report format."""
    sections = [
        _header(output),
        _section_meta(output),
        _section_structure(output),
        _section_flow(output),
        _section_risk(output),
        _section_drivers(output),
        _section_scenarios(output),
        _section_alpha(output),
        _section_portfolio(output),
        _section_key_fragilities(output),
        _section_gate_validation(output),
    ]
    return "\n".join(sections)


def _header(output: ScanOutput) -> str:
    region_str = f" ({output.region})" if output.region else ""
    return f"""# Industry Scan Report: {output.industry}{region_str}

**Time Horizon**: {output.time_horizon.value}
**System**: Structural Alpha Discovery Engine V2

---"""


def _section_meta(output: ScanOutput) -> str:
    meta = output.meta
    lines = [
        "## 1. Meta",
        "",
        f"- **Core Need**: {meta.core_need}",
        f"- **Substitution Risk**: {meta.substitution_risk}",
        f"- **Demand Elasticity**: {meta.demand_elasticity}",
        f"- **Narrative Dependency**: {meta.narrative_dependency}",
        f"- **Regulatory Dependency**: {meta.regulatory_dependency}",
        "",
    ]
    return "\n".join(lines) + "---\n"


def _section_structure(output: ScanOutput) -> str:
    lines = ["## 2. Structure", ""]
    for role in output.structure.roles:
        entities = ", ".join(role.entities)
        lines.append(f"### {role.role_type}")
        lines.append(f"- **Entities**: {entities}")
        lines.append(f"- **Description**: {role.description}")
        lines.append(f"- **Evidence**: {role.evidence}")
        lines.append("")

    power = output.structure.power_matrix
    lines.append("### Power Matrix")
    lines.append(f"- **Pricing Power**: {power.pricing_power}")
    lines.append(f"- **Entry Power**: {power.entry_power}")
    lines.append(f"- **Standard Power**: {power.standard_power}")
    lines.append(f"- **Capital Power**: {power.capital_power}")
    lines.append(f"- **Data Power**: {power.data_power}")
    lines.append("")
    return "\n".join(lines) + "---\n"


def _section_flow(output: ScanOutput) -> str:
    flow = output.flow
    lines = ["## 3. Flow", ""]

    lines.append("### Cash Flow")
    for node in flow.cash_nodes:
        lines.append(f"- **{node.entity}** ({node.role}): {node.description}")
    lines.append("")

    lines.append("### Information Flow")
    for node in flow.information_nodes:
        lines.append(f"- **{node.entity}** ({node.role}): {node.description}")
    lines.append("")

    lines.append("### Risk Flow")
    for node in flow.risk_nodes:
        lines.append(f"- **{node.entity}** ({node.role}): {node.description}")
    lines.append("")

    lines.append("### Attention Flow")
    for node in flow.attention_nodes:
        lines.append(f"- **{node.entity}** ({node.role}): {node.description}")
    lines.append("")
    return "\n".join(lines) + "---\n"


def _section_risk(output: ScanOutput) -> str:
    risk = output.risk
    lines = ["## 4. Risk", ""]

    lines.append("### Risk Concentrations")
    for rc in risk.risk_concentrations:
        lines.append(f"- **{rc.entity}**: {rc.risk_type} (severity={rc.severity})")
    lines.append("")

    sep = risk.profit_risk_separation
    lines.append("### Profit-Risk Separation")
    lines.append(f"- **Profit Owner**: {sep.profit_owner}")
    lines.append(f"- **Risk Owner**: {sep.risk_owner}")
    lines.append(f"- **Gap Score**: {sep.gap_score}")
    lines.append("")
    return "\n".join(lines) + "---\n"


def _section_drivers(output: ScanOutput) -> str:
    if not output.drivers:
        return ""
    lines = ["## 5. Drivers", ""]
    lines.append("| Driver | Importance | Direction | Confidence |")
    lines.append("|--------|-----------|-----------|------------|")
    for d in output.drivers.drivers:
        lines.append(f"| {d.name} | {d.importance:.0%} | {d.direction} | {d.confidence:.0%} |")
    lines.append("")
    return "\n".join(lines) + "---\n"


def _section_scenarios(output: ScanOutput) -> str:
    if not output.scenarios:
        return ""
    sc = output.scenarios
    lines = ["## 6. Scenarios", ""]

    lines.append(f"### Bull (probability: {sc.bull.probability:.0%})")
    for trigger in sc.bull.triggers:
        lines.append(f"- {trigger}")
    lines.append("")

    lines.append(f"### Base (probability: {sc.base.probability:.0%})")
    for trigger in sc.base.triggers:
        lines.append(f"- {trigger}")
    lines.append("")

    lines.append(f"### Bear (probability: {sc.bear.probability:.0%})")
    for trigger in sc.bear.triggers:
        lines.append(f"- {trigger}")
    lines.append("")
    return "\n".join(lines) + "---\n"


def _section_alpha(output: ScanOutput) -> str:
    if not output.alpha:
        return ""
    alpha = output.alpha
    lines = [
        "## 7. Alpha",
        "",
        f"### Consensus (Market Narrative)",
        f"{alpha.consensus}",
        "",
        f"### Reality (Structural Truth)",
        f"{alpha.reality}",
        "",
        f"### Mispricing",
        f"{alpha.mispricing}",
        "",
        f"### Alpha Thesis",
        f"{alpha.alpha_thesis}",
        "",
    ]
    return "\n".join(lines) + "---\n"


def _section_portfolio(output: ScanOutput) -> str:
    if not output.portfolio:
        return ""
    portfolio = output.portfolio
    lines = ["## 8. Investment Mapping", ""]

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
