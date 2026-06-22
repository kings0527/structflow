"""Standardized report output — renders ScanOutput into structured markdown."""

from __future__ import annotations

from structflow.models import ScanOutput


def render_report(output: ScanOutput) -> str:
    """Render ScanOutput into the standardized Industry Scan Report format."""
    sections = [
        _header(output),
        _section_structure_map(output),
        _section_flow_map(output),
        _section_power_map(output),
        _section_risk_map(output),
        _section_score_vector(output),
        _section_structural_phase(output),
        _section_key_fragilities(output),
        _section_gate_validation(output),
    ]
    return "\n".join(sections)


def _header(output: ScanOutput) -> str:
    region_str = f" ({output.region})" if output.region else ""
    return f"""# Industry Scan Report: {output.industry}{region_str}

**Time Horizon**: {output.time_horizon.value}
**Core Need**: {output.industry_definition.core_need}
**Substitution Risk**: {output.industry_definition.substitution_risk} | **Demand Stability**: {output.industry_definition.demand_stability} | **Narrative Dependency**: {output.industry_definition.narrative_dependency}

---"""


def _section_structure_map(output: ScanOutput) -> str:
    lines = ["## 1. Structure Map", ""]
    for role in output.structure.roles:
        entities = ", ".join(role.entities)
        lines.append(f"### {role.role_type}")
        lines.append(f"- **Entities**: {entities}")
        lines.append(f"- **Description**: {role.description}")
        lines.append("")
    return "\n".join(lines) + "\n---\n"


def _section_flow_map(output: ScanOutput) -> str:
    flow = output.flow_analysis
    lines = ["## 2. Flow Map", ""]

    lines.append("### Cash Flow Chain")
    for node in flow.cash_flow_chain:
        lines.append(f"- **{node.entity}** ({node.role}): {node.description}")
    lines.append("")

    lines.append("### Value Capture Points")
    for node in flow.value_capture_points:
        lines.append(f"- **{node.entity}** ({node.role}): {node.description}")
    lines.append("")

    lines.append("### Information Asymmetry")
    for node in flow.information_asymmetry_nodes:
        lines.append(f"- **{node.entity}** ({node.role}): {node.description}")
    lines.append("")

    lines.append("### Hidden Subsidies")
    if flow.hidden_subsidy_sources:
        for node in flow.hidden_subsidy_sources:
            lines.append(f"- **{node.entity}** ({node.role}): {node.description}")
    else:
        lines.append("- None identified")
    lines.append("")

    lines.append("### Mandatory Answers")
    lines.append(f"- **Who subsidizes the system?** {flow.subsidy_answer}")
    lines.append(f"- **Where does risk concentrate?** {flow.risk_concentration_answer}")
    lines.append(f"- **Is profit separated from risk?** {flow.profit_risk_separation_answer}")
    lines.append("")

    return "\n".join(lines) + "\n---\n"


def _section_power_map(output: ScanOutput) -> str:
    power = output.power_map
    lines = [
        "## 3. Power Map",
        "",
        f"- **Pricing Power**: {power.pricing_power}",
        f"- **Entry Control**: {power.entry_control}",
        f"- **Data Control**: {power.data_control}",
        f"- **Switching Cost**: {power.switching_cost}",
        f"- **Standard Control**: {power.standard_control}",
        "",
    ]
    return "\n".join(lines) + "\n---\n"


def _section_risk_map(output: ScanOutput) -> str:
    lines = ["## 4. Risk Map", ""]
    risk_points = output.risk_map.get("risk_accumulation_points", [])
    for point in risk_points:
        lines.append(f"- **{point['entity']}** ({point['role']}): {point['description']}")
    lines.append("")
    lines.append(f"- **Risk Concentration**: {output.risk_map.get('risk_concentration', 'N/A')}")
    lines.append(f"- **Profit-Risk Separation**: {output.risk_map.get('profit_risk_separation', 'N/A')}")
    lines.append("")
    return "\n".join(lines) + "\n---\n"


def _section_score_vector(output: ScanOutput) -> str:
    score = output.industry_structure_score
    lines = [
        "## 5. Score Vector",
        "",
        "### Industry-Level Scores (0-10)",
        "",
        "| Dimension | Score |",
        "|-----------|-------|",
        f"| Control | {score.control_score} |",
        f"| Profit Capture | {score.profit_capture_score} |",
        f"| Risk Displacement | {score.risk_displacement_score} |",
        f"| Information Advantage | {score.information_advantage_score} |",
        f"| Incentive Alignment | {score.incentive_alignment_score} |",
        "",
        "### Company Rankings",
        "",
        "| Company | Role | Control | Profit | Risk Disp | Info Adv | Incentive | Health |",
        "|---------|------|---------|--------|-----------|----------|-----------|--------|",
    ]
    for company in output.companies_ranked:
        sv = company.score_vector
        lines.append(
            f"| {company.name} | {company.role} | {sv.control_score} | {sv.profit_capture_score} | "
            f"{sv.risk_displacement_score} | {sv.information_advantage_score} | {sv.incentive_alignment_score} | "
            f"{company.structural_health:.2f} |"
        )
    lines.append("")
    return "\n".join(lines) + "\n---\n"


def _section_structural_phase(output: ScanOutput) -> str:
    phase = output.structural_phase
    lines = [
        "## 6. Structural Phase",
        "",
        f"**Phase**: `{phase.stage.value}`",
        "",
        "**Reasoning Signals**:",
    ]
    for signal in phase.reasoning_signals:
        lines.append(f"- {signal}")
    lines.append("")
    return "\n".join(lines) + "\n---\n"


def _section_key_fragilities(output: ScanOutput) -> str:
    lines = ["## 7. Key Fragilities", ""]
    if output.key_fragilities:
        for fragility in output.key_fragilities:
            lines.append(f"- ⚠️ {fragility}")
    else:
        lines.append("- No critical fragilities identified.")
    lines.append("")
    return "\n".join(lines) + "\n---\n"


def _section_gate_validation(output: ScanOutput) -> str:
    lines = ["## Gate Validation", ""]
    for gate in output.gate_validation.gates:
        icon = "✅" if gate.passed else "❌"
        lines.append(f"- {icon} **{gate.gate_name}**: {gate.reason}")
    lines.append("")
    if output.gate_validation.all_passed:
        lines.append("**All gates passed.** Output is structurally valid and comparable.")
    else:
        failed = ", ".join(g.gate_name for g in output.gate_validation.failed_gates)
        lines.append(f"**⚠️ Failed gates: {failed}** — Output may be incomplete.")
    return "\n".join(lines)
