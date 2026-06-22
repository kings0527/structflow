"""All Pydantic data models for StructFlow Industry Scanner Agent."""

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
# L0: Industry Definition Layer
# ──────────────────────────────────────────────

class L0IndustryDefinition(BaseModel):
    """L0 output: industry ontology definition."""
    core_need: str = Field(description="The rigid demand this industry fulfills")
    substitution_risk: float = Field(ge=0, le=1, description="How easily can this be substituted (0=no, 1=yes)")
    demand_stability: float = Field(ge=0, le=1, description="Demand stability (0=volatile, 1=stable)")
    narrative_dependency: float = Field(ge=0, le=1, description="Dependency on policy/narrative (0=independent, 1=dependent)")


# ──────────────────────────────────────────────
# L1: Structure Decomposition Layer
# ──────────────────────────────────────────────

class IndustryRole(BaseModel):
    """A role identified in the industry structure."""
    role_type: str = Field(description="Producer | Payer | Mediator | Controller")
    entities: list[str] = Field(description="Companies or entities playing this role")
    description: str = Field(description="How this role functions in the industry")


class PowerMatrix(BaseModel):
    """Power distribution matrix - all fields must attribute to specific roles."""
    pricing_power: str = Field(description="Who decides price, attributed to role")
    entry_control: str = Field(description="Who controls entry barriers, attributed to role")
    data_control: str = Field(description="Who controls information, attributed to role")
    switching_cost: str = Field(description="User exit difficulty, attributed to role")
    standard_control: str = Field(description="Who defines industry standards, attributed to role")


class L1StructureDecomposition(BaseModel):
    """L1 output: structure decomposition with power matrix."""
    roles: list[IndustryRole] = Field(description="Four mandatory roles: Producer, Payer, Mediator, Controller")
    power_matrix: PowerMatrix = Field(description="Power distribution matrix")


# ──────────────────────────────────────────────
# L2: Flow & Risk Layer
# ──────────────────────────────────────────────

class FlowNode(BaseModel):
    """A node in a flow chain."""
    entity: str = Field(description="Entity name")
    role: str = Field(description="Role in the chain")
    description: str = Field(description="What happens at this node")


class L2FlowRiskAnalysis(BaseModel):
    """L2 output: three flows + risk accumulation."""
    cash_flow_chain: list[FlowNode] = Field(description="How money moves through the system")
    value_capture_points: list[FlowNode] = Field(description="Where value is captured")
    information_asymmetry_nodes: list[FlowNode] = Field(description="Who knows first, who knows late")
    risk_accumulation_points: list[FlowNode] = Field(description="Where risk concentrates")
    hidden_subsidy_sources: list[FlowNode] = Field(description="Hidden subsidies in the system")
    subsidy_answer: str = Field(description="Who is continuously subsidizing the system?")
    risk_concentration_answer: str = Field(description="Where does risk ultimately concentrate?")
    profit_risk_separation_answer: str = Field(description="Is profit separated from risk?")


# ──────────────────────────────────────────────
# L3: Scoring & Ranking Layer
# ──────────────────────────────────────────────

class StructuralPhase(str, Enum):
    EMERGENT = "emergent"
    GROWTH = "growth"
    MATURE = "mature"
    DECLINE = "decline"
    DISRUPTED = "disrupted"


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
    structural_health: float = Field(description="(Control × ProfitCapture × InfoAdvantage) ÷ (RiskConcentration + IncentiveDistortion)")


class PhaseIdentification(BaseModel):
    """Industry structural phase."""
    stage: StructuralPhase
    reasoning_signals: list[str] = Field(description="Signals supporting this phase identification")


class L3ScoringRanking(BaseModel):
    """L3 output: scores, rankings, and phase."""
    industry_score: ScoreVector = Field(description="Overall industry structural score")
    companies_ranked: list[CompanyScore] = Field(description="Companies ranked by structural health")
    phase: PhaseIdentification = Field(description="Industry structural phase")


# ──────────────────────────────────────────────
# Gate Validation Results
# ──────────────────────────────────────────────

class GateResult(BaseModel):
    """Result of a single gate check."""
    gate_name: str
    passed: bool
    reason: str = Field(default="", description="Why passed or failed")


class GateValidationReport(BaseModel):
    """All 5 gate results."""
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
    """Final output of the Industry Scanner Agent."""
    industry: str
    region: Optional[str] = None
    time_horizon: TimeHorizon = TimeHorizon.MID

    # L0
    industry_definition: L0IndustryDefinition

    # L1
    structure: L1StructureDecomposition
    power_map: PowerMatrix

    # L2
    flow_analysis: L2FlowRiskAnalysis
    risk_map: dict = Field(default_factory=dict)

    # L3
    industry_structure_score: ScoreVector
    companies_ranked: list[CompanyScore]
    structural_phase: PhaseIdentification

    # Gates
    gate_validation: GateValidationReport

    # Fragilities
    key_fragilities: list[str] = Field(description="Key structural fragilities identified")
