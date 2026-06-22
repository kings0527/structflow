"""All Pydantic data models for StructFlow Atlas V2 — Structural Alpha Discovery Engine."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

# ──────────────────────────────────────────────
# Input Schema
# ──────────────────────────────────────────────

class TimeHorizon(str, Enum):
    SHORT = "short"
    MID = "mid"
    LONG = "long"


class ScanInput(BaseModel):
    """Input schema for industry scan."""
    industry: str = Field(description="Industry name to scan")
    region: Optional[str] = Field(default=None, description="Geographic region (optional)")
    time_horizon: TimeHorizon = Field(default=TimeHorizon.MID, description="Analysis time horizon")
    peer_set: list[str] = Field(default_factory=list, description="Optional comparable companies")


# ──────────────────────────────────────────────
# L0: Meta Layer — industry ontology
# ──────────────────────────────────────────────

class L0IndustryDefinition(BaseModel):
    """L0 output: industry meta definition."""
    core_need: str = Field(description="The rigid demand this industry fulfills")
    substitution_risk: float = Field(ge=0, le=1, description="How easily can this be substituted (0=no, 1=yes)")
    demand_elasticity: float = Field(ge=0, le=1, description="Demand elasticity (0=inelastic/rigid, 1=elastic/discretionary)")
    narrative_dependency: float = Field(ge=0, le=1, description="Dependency on policy/narrative (0=independent, 1=dependent)")
    regulatory_dependency: float = Field(ge=0, le=1, description="Dependency on regulation (0=none, 1=fully dependent)")


# ──────────────────────────────────────────────
# L1: Structure Layer — power structure
# ──────────────────────────────────────────────

class IndustryRole(BaseModel):
    """A role identified in the industry structure."""
    role_type: str = Field(description="Producer | Consumer | Mediator | Controller | Capital Provider")
    entities: list[str] = Field(description="Companies or entities playing this role")
    description: str = Field(description="How this role functions in the industry")
    evidence: str = Field(description="Structural evidence backing this role assignment (e.g., 'controls 80% of distribution')")


class PowerMatrix(BaseModel):
    """Power distribution matrix — all fields must attribute to specific roles with evidence."""
    pricing_power: str = Field(description="Who decides price, attributed to role")
    entry_power: str = Field(description="Who controls entry barriers, attributed to role")
    standard_power: str = Field(description="Who defines industry standards, attributed to role")
    capital_power: str = Field(description="Who controls capital flow, attributed to role")
    data_power: str = Field(description="Who controls information/data, attributed to role")


class L1StructureDecomposition(BaseModel):
    """L1 output: structure decomposition with power matrix."""
    roles: list[IndustryRole] = Field(description="Five mandatory roles: Producer, Consumer, Mediator, Controller, Capital Provider")
    power_matrix: PowerMatrix = Field(description="Power distribution matrix")


# ──────────────────────────────────────────────
# L2: Flow Layer — value flow
# ──────────────────────────────────────────────

class FlowNode(BaseModel):
    """A node in a flow chain."""
    entity: str = Field(description="Entity name")
    role: str = Field(description="Role in the chain")
    description: str = Field(description="What happens at this node")


class L2FlowAnalysis(BaseModel):
    """L2 output: four mandatory flows."""
    cash_nodes: list[FlowNode] = Field(description="How money moves through the system")
    information_nodes: list[FlowNode] = Field(description="Who knows what, when — information asymmetry")
    risk_nodes: list[FlowNode] = Field(description="Where risk flows and accumulates")
    attention_nodes: list[FlowNode] = Field(description="How attention drives cash flow — attention economy")


# ──────────────────────────────────────────────
# L3: Risk Layer — true risk attribution
# ──────────────────────────────────────────────

class RiskConcentration(BaseModel):
    """A risk concentration point."""
    entity: str = Field(description="Entity that bears concentrated risk")
    risk_type: str = Field(description="Type of risk (e.g., credit, operational, regulatory)")
    severity: float = Field(ge=0, le=1, description="Severity of risk concentration (0=low, 1=critical)")


class ProfitRiskSeparation(BaseModel):
    """Profit-risk separation analysis."""
    profit_owner: str = Field(description="Who profits the most from this industry")
    risk_owner: str = Field(description="Who bears the most risk in this industry")
    gap_score: float = Field(ge=0, le=1, description="Gap between profit and risk ownership (0=aligned, 1=fully separated)")


class L3RiskAnalysis(BaseModel):
    """L3 output: risk concentration and profit-risk separation."""
    risk_concentrations: list[RiskConcentration] = Field(description="Where risk concentrates")
    profit_risk_separation: ProfitRiskSeparation = Field(description="Profit vs risk ownership analysis")


# ──────────────────────────────────────────────
# L4: Driver Layer — industry drivers
# ──────────────────────────────────────────────

class Driver(BaseModel):
    """An industry driver factor."""
    name: str = Field(description="Driver name")
    importance: float = Field(ge=0, le=1, description="Importance weight (all drivers must sum to 1.0)")
    direction: str = Field(description="Direction of impact: '+' (positive) or '-' (negative)")
    confidence: float = Field(ge=0, le=1, description="Confidence in this driver assessment")


class L4DriverAnalysis(BaseModel):
    """L4 output: industry driver factors."""
    drivers: list[Driver] = Field(description="Ranked industry drivers — importance weights must sum to 1.0 (100%)")


# ──────────────────────────────────────────────
# L5: Scenario Layer — counterfactual reasoning
# ──────────────────────────────────────────────

class Scenario(BaseModel):
    """A scenario with probability and triggers."""
    probability: float = Field(ge=0, le=1, description="Probability of this scenario")
    triggers: list[str] = Field(description="Events or conditions that would trigger this scenario")


class L5ScenarioAnalysis(BaseModel):
    """L5 output: three scenarios — probabilities must sum to 1.0 (100%)."""
    bull: Scenario = Field(description="Most optimistic scenario")
    base: Scenario = Field(description="Most likely scenario")
    bear: Scenario = Field(description="Most pessimistic scenario")


# ──────────────────────────────────────────────
# L6: Alpha Layer — market mispricing (CORE VALUE)
# ──────────────────────────────────────────────

class L6AlphaAnalysis(BaseModel):
    """L6 output: market mispricing discovery.

    This is the core value of V2: discovering the gap between market narrative
    and real structure, and quantifying the opportunity.
    """
    consensus: str = Field(description="What the market believes (market narrative)")
    reality: str = Field(description="What the structure actually shows (structural reality)")
    mispricing: str = Field(description="Where the market is wrong — the specific gap")
    alpha_thesis: str = Field(description="Actionable thesis: how to profit from this mispricing")


# ──────────────────────────────────────────────
# L7: Portfolio Layer (optional) — investment mapping
# ──────────────────────────────────────────────

class PortfolioEntity(BaseModel):
    """An entity mapped to an investment category."""
    name: str = Field(description="Entity name")
    role: str = Field(description="Structural role (from L1)")
    reason: str = Field(description="Why this entity is in this category")


class L7PortfolioMapping(BaseModel):
    """L7 output: investment target mapping."""
    best_positioned_entities: list[PortfolioEntity] = Field(description="Entities best positioned to profit")
    overvalued_entities: list[PortfolioEntity] = Field(description="Entities whose market value exceeds structural value")
    fragile_entities: list[PortfolioEntity] = Field(description="Entities structurally fragile to shocks")


# ──────────────────────────────────────────────
# Scoring (retained from V1, used by L7)
# ──────────────────────────────────────────────

class ScoreVector(BaseModel):
    """S Vector: structural score for an industry or company."""
    control_score: float = Field(ge=0, le=10, description="Control over the system")
    profit_capture_score: float = Field(ge=0, le=10, description="Ability to capture profit")
    risk_displacement_score: float = Field(ge=0, le=10, description="Ability to displace risk to others")
    information_advantage_score: float = Field(ge=0, le=10, description="Information advantage")
    incentive_alignment_score: float = Field(ge=0, le=10, description="Incentive alignment with value creation")


class CompanyScore(BaseModel):
    """Scored and ranked company."""
    name: str
    role: str
    score_vector: ScoreVector
    structural_health: float = Field(description="(Control x ProfitCapture x InfoAdvantage) / ((10-RiskDisplacement) + (10-IncentiveAlignment))")


# ──────────────────────────────────────────────
# Gate Validation Results
# ──────────────────────────────────────────────

class GateResult(BaseModel):
    """Result of a single gate check."""
    gate_name: str
    passed: bool
    reason: str = Field(default="", description="Why passed or failed")


class GateValidationReport(BaseModel):
    """All gate results."""
    gates: list[GateResult]

    @property
    def all_passed(self) -> bool:
        return all(gate.passed for gate in self.gates)

    @property
    def failed_gates(self) -> list[GateResult]:
        return [gate for gate in self.gates if not gate.passed]


# ──────────────────────────────────────────────
# Final Output Schema
# ──────────────────────────────────────────────

class ScanOutput(BaseModel):
    """Final output of the Structural Alpha Discovery Engine."""
    industry: str
    region: Optional[str] = None
    time_horizon: TimeHorizon = TimeHorizon.MID

    # L0-L3 (mandatory)
    meta: L0IndustryDefinition = Field(description="L0: Industry meta definition")
    structure: L1StructureDecomposition = Field(description="L1: Structure decomposition")
    flow: L2FlowAnalysis = Field(description="L2: Four-flow analysis")
    risk: L3RiskAnalysis = Field(description="L3: Risk attribution")

    # L4-L6 (V2 intelligence)
    drivers: Optional[L4DriverAnalysis] = Field(default=None, description="L4: Industry drivers")
    scenarios: Optional[L5ScenarioAnalysis] = Field(default=None, description="L5: Scenario analysis")
    alpha: Optional[L6AlphaAnalysis] = Field(default=None, description="L6: Alpha discovery")

    # L7 (optional)
    portfolio: Optional[L7PortfolioMapping] = Field(default=None, description="L7: Portfolio mapping")

    # Scoring (retained from V1, optional)
    industry_score: Optional[ScoreVector] = Field(default=None, description="Industry-level S-vector")
    companies_ranked: list[CompanyScore] = Field(default_factory=list, description="Companies ranked by structural health")

    # Gates
    gate_validation: GateValidationReport

    # Fragilities
    key_fragilities: list[str] = Field(description="Key structural fragilities identified")
