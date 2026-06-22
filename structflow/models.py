"""All Pydantic data models for StructFlow Atlas V2.1 — Meta-Generalization Layer.

V2.1 Core Principle:
  World = Parameterizable Dynamic System
  Any industry is compressed into: SV (State Variables) + FV (Flow Variables)
  + CV (Control Variables) + LV (Latent Variables).

Hard Constraints:
  1. De-entity: no company lists as core output; must map to variable roles.
  2. De-narrative: narrative can only be LV (latent variable), not a driver.
  3. De-static: no pure structure description; must include dynamic change.
"""

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
    """Input schema for system scan."""
    industry: str = Field(description="Industry or system to scan")
    region: Optional[str] = Field(default=None, description="Geographic region (optional)")
    time_horizon: TimeHorizon = Field(default=TimeHorizon.MID, description="Analysis time horizon")
    peer_set: list[str] = Field(default_factory=list, description="Optional comparable entities")


# ──────────────────────────────────────────────
# L0: Meta System Definition
# ──────────────────────────────────────────────

class MetaSystemDefinition(BaseModel):
    """L0 output: meta system definition.

    The system is NOT described by industry semantics, but by its
    functional structure: what it does, what variables define it,
    and what drives it externally.
    """
    system_type: str = Field(description="Type of system (e.g., 'financial market', 'supply chain', 'platform economy')")
    core_function: str = Field(description="The irreducible function this system performs")
    state_variables: list[str] = Field(description="Stock variables — current存量结构 (e.g., capital stock, capacity, user base, reserves, leverage)")
    control_variables: list[str] = Field(description="Leverage points — variables that determine system behavior (e.g., interest rate, pricing power, entry rules, subsidies, standards)")
    exogenous_drivers: list[str] = Field(description="External forces that impact the system from outside")
    endogenous_feedback_loops: list[str] = Field(description="Internal feedback mechanisms within the system")


# ──────────────────────────────────────────────
# L1: Variable Mapping (SV / FV / CV / LV)
# ──────────────────────────────────────────────

class VariableMapping(BaseModel):
    """L1 output: maps any system into four types of base variables.

    All industries must be mapped to:
    (1) State Variables (SV) — system's current stock structure
    (2) Flow Variables (FV) — system's change paths
    (3) Control Variables (CV) — leverage points that determine behavior
    (4) Latent Variables (LV) — unobservable but decisive variables
    """
    state_variables: list[str] = Field(description="SV: current stock/存量 (e.g., capital stock, capacity, reserves, leverage)")
    flow_variables: list[str] = Field(description="FV: change paths (e.g., cash flow, information flow, goods flow, risk transfer flow)")
    control_variables: list[str] = Field(description="CV: leverage points (e.g., interest rate, pricing power, entry rules, subsidies, standards)")
    latent_variables: list[str] = Field(description="LV: unobservable but decisive (e.g., expectations, confidence, narrative, risk appetite, liquidity mismatch)")


# ──────────────────────────────────────────────
# L2: System Equation (Meta Dynamics Engine)
# ──────────────────────────────────────────────

class SystemEquation(BaseModel):
    """L2 output: system dynamics equation.

    ΔState = α * Flow Variables + β * Control Variables + γ * Latent Variables

    Hard constraint: α + β + γ = 1.0
    """
    flow_weight: float = Field(ge=0, le=1, description="α: weight of flow variables in driving system change")
    control_weight: float = Field(ge=0, le=1, description="β: weight of control variables in driving system change")
    latent_weight: float = Field(ge=0, le=1, description="γ: weight of latent variables in driving system change")


# ──────────────────────────────────────────────
# L3: Driver Set (Driver Abstraction Layer)
# ──────────────────────────────────────────────

class MetaDriver(BaseModel):
    """A driver factor in unified format.

    Hard rule: all drivers must come from changes in SV/FV/CV/LV.
    """
    name: str = Field(description="Driver name")
    type: str = Field(description="Driver type: macro | micro | policy | behavioral | financial")
    direction: str = Field(description="Direction of impact: '+' (positive) or '-' (negative)")
    elasticity: float = Field(ge=0, le=1, description="How sensitive the system is to this driver (0=inelastic, 1=highly elastic)")
    lag: str = Field(description="Time lag: short | mid | long")
    volatility: float = Field(ge=0, le=1, description="How volatile/unpredictable this driver is (0=stable, 1=highly volatile)")
    system_dependency: float = Field(ge=0, le=1, description="How dependent the system is on this driver (0=peripheral, 1=critical)")


class DriverSet(BaseModel):
    """L3 output: set of meta drivers.

    All drivers must trace back to changes in SV/FV/CV/LV.
    """
    drivers: list[MetaDriver] = Field(description="Ranked meta drivers — all must originate from SV/FV/CV/LV changes")


# ──────────────────────────────────────────────
# L4: Regime State (Meta Regime Layer)
# ──────────────────────────────────────────────

class RegimeState(BaseModel):
    """L4 output: current system regime identification.

    The system must be in one of:
    expansion | contraction | transition | bubble | collapse
    """
    current_regime: str = Field(description="Current regime: expansion | contraction | transition | bubble | collapse")
    regime_confidence: float = Field(ge=0, le=1, description="Confidence in regime identification (0=uncertain, 1=certain)")
    regime_drivers: list[str] = Field(description="Key variables driving the current regime")


# ──────────────────────────────────────────────
# L5: Distortion Analysis (Meta Distortion Layer)
# ──────────────────────────────────────────────

class DistortionAnalysis(BaseModel):
    """L5 output: market认知 vs system真实结构的偏差检测.

    This is the core capability that detects where market belief
    diverges from structural reality.

    Must answer:
    - What does the market believe?
    - What truly drives the system?
    - Where is the gap?
    """
    market_belief: str = Field(description="What the market currently believes about this system")
    true_drivers: list[str] = Field(description="What actually drives the system based on structural analysis")
    mispricing_sources: list[str] = Field(description="Specific sources of mispricing — where market belief diverges from reality")
    distortion_score: float = Field(ge=0, le=1, description="Overall distortion level (0=market is correct, 1=massively distorted)")


# ──────────────────────────────────────────────
# L6: Alpha Signal (Meta Alpha Layer)
# ──────────────────────────────────────────────

class AlphaSignal(BaseModel):
    """L6 output: final alpha signal.

    Alpha = Mispricing × Sensitivity × Regime Alignment

    This is the ultimate output: converting structural analysis
    into an actionable investment signal.
    """
    consensus_view: str = Field(description="What the market consensus believes")
    structural_view: str = Field(description="What the structural analysis reveals")
    mispricing: str = Field(description="The specific gap between consensus and structure")
    alpha_signal: str = Field(description="Actionable signal: how to profit from this mispricing")
    confidence: float = Field(ge=0, le=1, description="Confidence in the alpha signal (0=low, 1=high)")


# ──────────────────────────────────────────────
# L7: Portfolio Layer (optional) — investment mapping
# ──────────────────────────────────────────────

class PortfolioEntity(BaseModel):
    """An entity mapped to an investment category."""
    name: str = Field(description="Entity name")
    role: str = Field(description="Variable role in the system (not industry-specific role)")
    reason: str = Field(description="Why this entity is in this category — linked to variable analysis")


class L7PortfolioMapping(BaseModel):
    """L7 output: investment target mapping (optional)."""
    best_positioned_entities: list[PortfolioEntity] = Field(description="Entities best positioned to profit from the identified alpha")
    overvalued_entities: list[PortfolioEntity] = Field(description="Entities whose market value exceeds structural value")
    fragile_entities: list[PortfolioEntity] = Field(description="Entities structurally fragile to regime shifts")


# ──────────────────────────────────────────────
# Scoring (retained for L7 optional use)
# ──────────────────────────────────────────────

class ScoreVector(BaseModel):
    """S Vector: structural score for a system or entity."""
    control_score: float = Field(ge=0, le=10, description="Control over the system")
    profit_capture_score: float = Field(ge=0, le=10, description="Ability to capture profit")
    risk_displacement_score: float = Field(ge=0, le=10, description="Ability to displace risk to others")
    information_advantage_score: float = Field(ge=0, le=10, description="Information advantage")
    incentive_alignment_score: float = Field(ge=0, le=10, description="Incentive alignment with value creation")


class CompanyScore(BaseModel):
    """Scored and ranked entity."""
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
    """Final output of the Meta-Generalization Layer.

    V2.1: World = Parameterizable Dynamic System
    """
    industry: str
    region: Optional[str] = None
    time_horizon: TimeHorizon = TimeHorizon.MID

    # L0-L6 (mandatory)
    meta: MetaSystemDefinition = Field(description="L0: Meta system definition")
    variables: VariableMapping = Field(description="L1: Variable mapping (SV/FV/CV/LV)")
    equation: SystemEquation = Field(description="L2: System equation (α+β+γ=1)")
    drivers: DriverSet = Field(description="L3: Meta driver set")
    regime: RegimeState = Field(description="L4: Regime state identification")
    distortion: DistortionAnalysis = Field(description="L5: Distortion analysis")
    alpha: AlphaSignal = Field(description="L6: Alpha signal")

    # L7 (optional)
    portfolio: Optional[L7PortfolioMapping] = Field(default=None, description="L7: Portfolio mapping (optional)")

    # Scoring (optional, for L7)
    industry_score: Optional[ScoreVector] = Field(default=None, description="System-level S-vector")
    companies_ranked: list[CompanyScore] = Field(default_factory=list, description="Entities ranked by structural health")

    # Gates
    gate_validation: GateValidationReport

    # Fragilities
    key_fragilities: list[str] = Field(description="Key structural fragilities identified")
