"""V2.2 Report output — 9-section Meta System Report format.

1. System Mapping (SV/FV/CV/LV)   2. Driver System
3. Flow + Feedback System          4. Regime Engine Output
5. Distortion Engine Output        6. Nonlinear Cycle State
7. Alpha Signal (bounded)          8. Investment Mapping
9. Cross-Layer Validation Report
"""

from __future__ import annotations

from structflow.models import ScanOutput


def render_report(output: ScanOutput) -> str:
    return "\n".join([
        _header(output),
        _section_system_mapping(output),
        _section_drivers(output),
        _section_flow_feedback(output),
        _section_regime(output),
        _section_distortion(output),
        _section_nonlinear(output),
        _section_alpha(output),
        _section_portfolio(output),
        _section_fragilities(output),
        _section_gates(output),
    ])


def _header(o: ScanOutput) -> str:
    r = f" ({o.region})" if o.region else ""
    return f"# Meta System Report v2.2: {o.industry}{r}\n\n**Time Horizon**: {o.time_horizon.value}\n**As Of**: {o.as_of_date or 'unspecified'}\n**System**: Nonlinear State-Space Engine V2.2\n\n---"


def _section_system_mapping(o: ScanOutput) -> str:
    m, v = o.meta, o.variables
    lines = ["## 1. System Mapping", "", f"**System Type**: {m.system_type}", "",
             f"**Core Function**: {m.core_function}", "",
             f"**System Boundary**: {m.system_boundary}", "",
             f"**Failure Mode**: {m.failure_mode}", "",
             "### State Variables (SV)"]
    lines += [f"- {x}" for x in v.state_variables]
    lines += ["", "### Flow Variables (FV)"]
    lines += [f"- {x}" for x in v.flow_variables]
    lines += ["", "### Control Variables (CV)"]
    lines += [f"- {x}" for x in v.control_variables]
    lines += ["", "### Latent Variables (LV)"]
    lines += [f"- {x}" for x in v.latent_variables]
    return "\n".join(lines) + "\n---\n"


def _section_drivers(o: ScanOutput) -> str:
    lines = ["## 2. Driver System", "",
             "| Driver | Category | Maps To | Direction | Elasticity | Volatility | Lag | Regime Dep |",
             "|--------|----------|---------|-----------|------------|------------|-----|------------|"]
    for d in o.drivers.drivers:
        lines.append(f"| {d.name} | {d.category} | {d.maps_to_variable} | {d.direction} | {d.elasticity:.2f} | {d.volatility:.2f} | {d.lag} | {d.regime_dependency:.2f} |")
    return "\n".join(lines) + "\n---\n"


def _section_flow_feedback(o: ScanOutput) -> str:
    ff = o.flow_feedback
    lines = ["## 3. Flow + Feedback System", "", "### Flow Types"]
    lines += [f"- {t}" for t in ff.flow_types]
    lines += ["", "### Feedback Loops"]
    for l in ff.feedback_loops:
        lines.append(f"- **{l.loop_name}** ({l.type}, amp={l.amplification_factor:.0%}): {l.mechanism}")
        lines.append(f"  - Trigger: {l.trigger}")
    return "\n".join(lines) + "\n---\n"


def _section_regime(o: ScanOutput) -> str:
    r = o.regime
    lines = ["## 4. Regime Engine Output", "",
             f"- **Current Regime**: {r.current_regime}",
             f"- **Confidence**: {r.confidence:.0%}",
             f"- **Transition**: → {r.transition_probability.next_regime} (probability: {r.transition_probability.probability:.0%})"]
    return "\n".join(lines) + "\n---\n"


def _section_distortion(o: ScanOutput) -> str:
    d = o.distortion
    lines = ["## 5. Distortion Engine Output", "",
             f"### Market Belief\n{d.market_belief}", "",
             f"### Structural Truth\n{d.structural_truth}", "",
             "### Mispricing Sources"]
    lines += [f"- {s}" for s in d.mispricing_sources]
    lines += ["", f"- **Distortion Score**: {d.distortion_score:.0%}"]
    lines += [
        f"- **Supporting Evidence**: {', '.join(d.supporting_evidence_ids) or 'none'}",
        f"- **Contradicting Evidence**: {', '.join(d.contradicting_evidence_ids) or 'none'}",
    ]
    return "\n".join(lines) + "\n---\n"


def _section_nonlinear(o: ScanOutput) -> str:
    nl = o.nonlinear_dynamics
    ic = nl.inventory_cycle
    cl = nl.capacity_lag
    de = nl.demand_elasticity
    lines = ["## 6. Nonlinear Cycle State", "",
             "### Inventory Cycle",
             f"- **Stage**: {ic.cycle_stage}",
             f"- **Inventory Pressure**: {ic.inventory_pressure:.0%}",
             f"- **Price Sensitivity**: {ic.price_sensitivity:.0%}", "",
             "### Capacity Lag",
             f"- **Capex Cycle Lag**: {cl.capex_cycle_lag}",
             f"- **Supply Response Delay**: {cl.supply_response_delay}", "",
             "### Demand Elasticity",
             f"- **Elasticity**: {de.elasticity:.0%}",
             f"- **State Dependency**: {de.state_dependency}"]
    return "\n".join(lines) + "\n---\n"


def _section_alpha(o: ScanOutput) -> str:
    a = o.alpha
    lines = ["## 7. Alpha Signal (Bounded)", "",
             f"### Consensus View\n{a.consensus_view}", "",
             f"### Structural View\n{a.structural_view}", "",
             f"### Mispricing\n{a.mispricing}", "",
             f"### Alpha Signal\n{a.alpha_signal}", "",
             f"- **Direction**: {a.direction}",
             f"- **Confidence**: {a.confidence:.0%}",
             f"- **Supporting Evidence**: {', '.join(a.supporting_evidence_ids) or 'none'}",
             f"- **Contradicting Evidence**: {', '.join(a.contradicting_evidence_ids) or 'none'}"]
    return "\n".join(lines) + "\n---\n"


def _section_portfolio(o: ScanOutput) -> str:
    if not o.portfolio:
        return ""
    p = o.portfolio
    lines = ["## 8. Investment Mapping", ""]
    for title, items in [("Best Positioned", p.best_positioned), ("Overvalued", p.overvalued), ("Fragile", p.fragile)]:
        lines.append(f"### {title}")
        for a in items:
            lines.append(f"- **{a.asset}** ({a.role}, exposure={a.exposure:.0%}): {a.risk_profile}")
            if a.sensitivity_to_drivers:
                lines.append(f"  - Sensitive to: {', '.join(a.sensitivity_to_drivers)}")
            lines.append(
                f"  - Verification: {a.verification_status}; "
                f"evidence: {', '.join(a.evidence_ids) or 'none'}"
            )
            if a.observed_price is not None:
                lines.append(
                    f"  - Observed price: {a.observed_price} "
                    f"as of {a.price_as_of or 'unknown'}"
                )
        lines.append("")
    return "\n".join(lines) + "---\n"


def _section_fragilities(o: ScanOutput) -> str:
    lines = ["## Key Fragilities", ""]
    if o.key_fragilities:
        lines += [f"- ⚠️ {f}" for f in o.key_fragilities]
    else:
        lines.append("- No critical fragilities identified.")
    return "\n".join(lines) + "\n---\n"


def _section_gates(o: ScanOutput) -> str:
    lines = ["## 9. Cross-Layer Validation Report", ""]
    for g in o.gate_validation.gates:
        icon = "✅" if g.passed else "❌"
        lines.append(f"- {icon} **{g.gate_name}**: {g.reason}")
    lines.append("")
    if o.gate_validation.all_passed:
        lines.append("**All gates passed.** Output is structurally valid.")
    else:
        lines.append(f"**⚠️ Failed: {', '.join(g.gate_name for g in o.gate_validation.failed_gates)}**")
    return "\n".join(lines)
