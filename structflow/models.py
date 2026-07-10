"""All Pydantic data models for StructFlow Atlas V2.2 — Meta-Generalization + Nonlinear Regime.

V2.2 Core Principle:
  Industry = dynamic constrained system: SV + FV + CV + LV
  → nonlinear transformation → regime switch → mispricing emergence

V2.1 → V2.2 Key Changes:
  - L0: Simplified (system_boundary, failure_mode replace variable lists)
  - L2: Driver Engine with maps_to_variable + regime_dependency + nonlinear direction
  - L3: Flow + Feedback System (reinforcing/balancing loops, min 3)
  - NEW: NonlinearDynamics (inventory cycle, capacity lag, demand elasticity)
  - L4: Regime Engine with transition_probability + shock regime
  - L5: Distortion Engine (structural_truth replaces true_drivers)
  - L6: Alpha Engine with direction (long|short|neutral)
  - L7: Investment Mapping with exposure + sensitivity_to_drivers + risk_profile

Hard Constraints (NON-NEGOTIABLE):
  1. No Free Narrative Drivers — narrative maps to LV only
  2. No Entity-Driven Reasoning — entities are outputs, not drivers
  3. No Linear Assumption — all pricing is nonlinear unless proven stable
  4. No Alpha Override — Alpha cannot contradict Driver Layer
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator

# ──────────────────────────────────────────────
# Input Schema
# ──────────────────────────────────────────────

class TimeHorizon(str, Enum):
    SHORT = "short"
    MID = "mid"
    LONG = "long"


class ScanInput(BaseModel):
    industry: str = Field(description="Industry or system to scan")
    region: Optional[str] = Field(default=None, description="Geographic region (optional)")
    time_horizon: TimeHorizon = Field(default=TimeHorizon.MID, description="Analysis time horizon")
    peer_set: list[str] = Field(default_factory=list, description="Optional comparable entities")


# ──────────────────────────────────────────────
# L0: Meta System Definition (simplified)
# ──────────────────────────────────────────────

class MetaSystemDefinition(BaseModel):
    """L0 output: meta system definition.

    V2.2: simplified — variables moved to L1, feedback moved to L3.
    Focus on: what the system IS, what BREAKS if it disappears.
    """
    system_type: str = Field(description="Type of system (e.g., 'financial market', 'supply chain', 'platform economy')")
    core_function: str = Field(description="The irreducible function this system performs")
    system_boundary: str = Field(description="What is INSIDE vs OUTSIDE the system — where does the system end?")
    failure_mode: str = Field(description="How does this system break? What is the failure cascade?")
    covered_segment_ids: list[str] = Field(
        default_factory=list,
        description="Exact SEG IDs from the binding EntityProfile coverage contract",
    )
    covered_dimension_ids: list[str] = Field(
        default_factory=list,
        description="Exact DIM IDs from the binding EntityProfile coverage contract",
    )


# ──────────────────────────────────────────────
# L1: Variable Space (SV / FV / CV / LV)
# ──────────────────────────────────────────────

class VariableMapping(BaseModel):
    """L1 output: maps system into four variable types."""
    state_variables: list[str] = Field(description="SV: persistent stock variables (capacity, inventory, capital stock, market share)")
    flow_variables: list[str] = Field(description="FV: rate-of-change variables (production volume, cash flow, shipment, investment flow)")
    control_variables: list[str] = Field(description="CV: policy/pricing/constraint variables (interest rate, carbon tax, tariffs, regulation intensity)")
    latent_variables: list[str] = Field(description="LV: unobservable state drivers (expectation, sentiment, narrative, risk appetite, uncertainty)")
    covered_segment_ids: list[str] = Field(
        default_factory=list,
        description="Exact SEG IDs from the binding EntityProfile coverage contract",
    )
    covered_dimension_ids: list[str] = Field(
        default_factory=list,
        description="Exact DIM IDs from the binding EntityProfile coverage contract",
    )


# ──────────────────────────────────────────────
# L2: Driver Engine (Core Causal Layer)
# ──────────────────────────────────────────────

class Driver(BaseModel):
    """A quantified causal driver.

    V2.2: MUST map to exactly one variable group (SV/FV/CV/LV).
    Direction can be '+', '-', or 'nonlinear'.
    """
    name: str = Field(description="Driver name")
    category: str = Field(description="Driver category: macro | micro | policy | behavioral | financial | structural")
    maps_to_variable: str = Field(description="Which variable group this driver maps to: SV | FV | CV | LV")
    direction: str = Field(description="Direction of impact: '+' (positive), '-' (negative), or 'nonlinear'")
    elasticity: float = Field(ge=0, le=1, description="How sensitive the system is to this driver (0=inelastic, 1=highly elastic)")
    volatility: float = Field(ge=0, le=1, description="How volatile/unpredictable this driver is (0=stable, 1=highly volatile)")
    lag: str = Field(description="Time lag: short | mid | long")
    regime_dependency: float = Field(ge=0, le=1, description="How dependent on current regime this driver is (0=regime-independent, 1=fully regime-dependent)")

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category(cls, value: str) -> str:
        aliases = {
            "宏观": "macro",
            "微观": "micro",
            "政策": "policy",
            "行为": "behavioral",
            "金融": "financial",
            "结构": "structural",
        }
        normalized = str(value).strip().lower()
        return aliases.get(normalized, normalized)

    @field_validator("direction", mode="before")
    @classmethod
    def normalize_direction(cls, value: str) -> str:
        aliases = {
            "positive": "+",
            "negative": "-",
            "正向": "+",
            "负向": "-",
            "非线性": "nonlinear",
        }
        normalized = str(value).strip().lower()
        return aliases.get(normalized, normalized)


class DriverSpace(BaseModel):
    """L2 output: fully quantified driver space.

    Every driver MUST map to exactly one variable group.
    No free-text drivers. No duplicate semantic drivers.
    """
    drivers: list[Driver] = Field(description="Quantified causal drivers — each must map to SV/FV/CV/LV")
    covered_segment_ids: list[str] = Field(
        default_factory=list,
        description="Exact SEG IDs represented by at least one driver",
    )
    covered_dimension_ids: list[str] = Field(
        default_factory=list,
        description="Exact DIM IDs represented by at least one driver",
    )


# ──────────────────────────────────────────────
# L3: Flow + Feedback System
# ──────────────────────────────────────────────

class FeedbackLoop(BaseModel):
    """A feedback loop in the system."""
    loop_name: str = Field(description="Name of the feedback loop")
    type: str = Field(description="Loop type: reinforcing | balancing")
    mechanism: str = Field(description="How the loop works — the causal chain")
    trigger: str = Field(description="What triggers this loop to activate")
    amplification_factor: float = Field(ge=0, le=1, description="How much this loop amplifies changes (0=damping, 1=extreme amplification)")


class FlowFeedbackSystem(BaseModel):
    """L3 output: flow types and feedback loops.

    Minimum 3 feedback loops, including at least:
    - 1 reinforcing loop
    - 1 balancing loop
    """
    flow_types: list[str] = Field(description="Flow types present: capital flow, goods flow, information flow, risk flow, subsidy flow")
    feedback_loops: list[FeedbackLoop] = Field(description="Feedback loops in the system (min 3, ≥1 reinforcing + ≥1 balancing)")


# ──────────────────────────────────────────────
# Nonlinear Dynamics (cross-cutting module)
# ──────────────────────────────────────────────

class InventoryCycle(BaseModel):
    """Inventory cycle state — nonlinear price response driver."""
    cycle_stage: str = Field(description="Current stage: early | mid | late | crash")
    inventory_pressure: float = Field(ge=0, le=1, description="Inventory pressure level (0=low/no pressure, 1=extreme overhang)")
    price_sensitivity: float = Field(ge=0, le=1, description="How sensitive price is to inventory changes (0=insensitive, 1=extreme sensitivity)")


class CapacityLag(BaseModel):
    """Capacity lag module — supply response delay."""
    capex_cycle_lag: str = Field(description="Capital expenditure cycle lag in months (e.g., '18 months')")
    supply_response_delay: str = Field(description="Supply response delay: short | mid | long")


class DemandElasticityModule(BaseModel):
    """Demand elasticity module."""
    elasticity: float = Field(ge=0, le=1, description="Demand elasticity (0=inelastic/rigid, 1=highly elastic)")
    state_dependency: bool = Field(description="Whether demand depends on system state (true=state-dependent, false=state-independent)")


class NonlinearDynamics(BaseModel):
    """Nonlinear system dynamics — feeds into Regime Engine.

    Price ≠ linear function of cost.
    Price = f(inventory, leverage, sentiment, marginal_cost, liquidity)
    """
    inventory_cycle: InventoryCycle = Field(description="Inventory cycle state")
    capacity_lag: CapacityLag = Field(description="Capacity lag module")
    demand_elasticity: DemandElasticityModule = Field(description="Demand elasticity module")


# ──────────────────────────────────────────────
# L4: Nonlinear Regime Engine
# ──────────────────────────────────────────────

class RegimeTransition(BaseModel):
    """Regime transition probability."""
    next_regime: str = Field(description="Most likely next regime: expansion | contraction | transition | bubble | collapse | shock")
    probability: float = Field(ge=0, le=1, description="Probability of transitioning to next_regime")


class RegimeEngine(BaseModel):
    """L4 output: nonlinear regime state.

    Regime(t) = f(SV, FV, CV, LV, ΔDrivers)
    Regime changes only if: Σ(Weighted Driver Shocks) > Threshold
    Threshold = f(volatility, leverage, inventory level)
    """
    current_regime: str = Field(description="Current regime: expansion | contraction | transition | bubble | collapse | shock")
    confidence: float = Field(ge=0, le=1, description="Confidence in regime identification (0=uncertain, 1=certain)")
    transition_probability: RegimeTransition = Field(description="Most likely regime transition")


# ──────────────────────────────────────────────
# L5: Distortion Engine (Mispricing Layer)
# ──────────────────────────────────────────────

class DistortionEngine(BaseModel):
    """L5 output: gap between market belief and structural reality.

    Mispricing types: cycle | structural | liquidity | narrative | policy
    """
    market_belief: str = Field(description="What the market currently believes about this system")
    structural_truth: str = Field(description="What the structural analysis actually reveals")
    mispricing_sources: list[str] = Field(description="Specific sources of mispricing — where market belief diverges from reality")
    distortion_score: float = Field(ge=0, le=1, description="Overall distortion level (0=market correct, 1=massively distorted)")
    supporting_evidence_ids: list[str] = Field(
        default_factory=list,
        description="Source IDs supporting the structural truth",
    )
    contradicting_evidence_ids: list[str] = Field(
        default_factory=list,
        description="Source IDs supporting consensus or falsifying structural truth",
    )


# ──────────────────────────────────────────────
# L6: Alpha Engine
# ──────────────────────────────────────────────

class AlphaEngine(BaseModel):
    """L6 output: alpha signal under bounded uncertainty.

    Alpha = Σ(Driver × Weight × Regime Multiplier × Mispricing Factor)

    Constraints:
    - Alpha cannot override driver structure
    - Alpha must reference regime state
    - Alpha must include scenario uncertainty
    """
    consensus_view: str = Field(description="What the market consensus believes")
    structural_view: str = Field(description="What the structural analysis reveals")
    mispricing: str = Field(description="The specific gap between consensus and structure")
    alpha_signal: str = Field(description="Bounded structural signal with conditions and falsifiers; never prescriptive investment advice")
    direction: str = Field(description="Signal direction: long | short | neutral")
    confidence: float = Field(ge=0, le=1, description="Confidence in the alpha signal (0=low, 1=high)")
    supporting_evidence_ids: list[str] = Field(
        default_factory=list,
        description="Source IDs supporting the alpha signal",
    )
    contradicting_evidence_ids: list[str] = Field(
        default_factory=list,
        description="Source IDs representing material counter-evidence",
    )
    observed_price: Optional[float] = Field(
        default=None,
        gt=0,
        description="Optional observed market price used by the signal",
    )
    price_as_of: Optional[str] = Field(
        default=None,
        description="Observation date for observed_price in YYYY-MM-DD",
    )
    price_evidence_ids: list[str] = Field(
        default_factory=list,
        description="Evidence IDs supporting observed_price",
    )


# ──────────────────────────────────────────────
# L7: Investment Mapping Layer (optional)
# ──────────────────────────────────────────────

class AssetMapping(BaseModel):
    """An asset mapped to investment category with exposure metrics."""
    asset: str = Field(description="Asset name (company, commodity, instrument)")
    asset_type: str = Field(
        default="unknown",
        pattern="^(listed_equity|listed_subsidiary|commodity|fund|derivative|business_unit|unknown)$",
    )
    ticker: Optional[str] = None
    venue: Optional[str] = None
    is_tradable: bool = False
    role: str = Field(description="Variable role: SV_controller | FV_bottleneck | CV_beneficiary | LV_reflection")
    exposure: float = Field(ge=0, le=1, description="Exposure to the identified alpha (0=low, 1=high)")
    sensitivity_to_drivers: list[str] = Field(description="Which L2 drivers this asset is most sensitive to")
    risk_profile: str = Field(description="Risk profile — what could go wrong for this asset")
    evidence_ids: list[str] = Field(
        default_factory=list,
        description="Evidence IDs used to verify this asset mapping",
    )
    verification_status: str = Field(
        default="unverified",
        pattern="^(verified|partial|unverified)$",
    )
    observed_price: Optional[float] = Field(default=None, gt=0)
    price_as_of: Optional[str] = None


class InvestmentMapping(BaseModel):
    """L7 output: investment target mapping (optional)."""
    best_positioned: list[AssetMapping] = Field(description="Assets best positioned to profit from the identified alpha")
    overvalued: list[AssetMapping] = Field(description="Assets whose market value exceeds structural value")
    fragile: list[AssetMapping] = Field(description="Assets structurally fragile to regime shifts")


# ──────────────────────────────────────────────
# Scoring (retained for L7 optional use)
# ──────────────────────────────────────────────

class ScoreVector(BaseModel):
    control_score: float = Field(ge=0, le=10)
    profit_capture_score: float = Field(ge=0, le=10)
    risk_displacement_score: float = Field(ge=0, le=10)
    information_advantage_score: float = Field(ge=0, le=10)
    incentive_alignment_score: float = Field(ge=0, le=10)


class CompanyScore(BaseModel):
    name: str
    role: str
    score_vector: ScoreVector
    structural_health: float


# ──────────────────────────────────────────────
# Gate Validation Results
# ──────────────────────────────────────────────

class GateResult(BaseModel):
    gate_name: str
    passed: bool
    reason: str = Field(default="")


class GateValidationReport(BaseModel):
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
    """Final output of the V2.2 Nonlinear State-Space Engine."""
    industry: str
    region: Optional[str] = None
    time_horizon: TimeHorizon = TimeHorizon.MID

    # L0-L3 (mandatory)
    meta: MetaSystemDefinition = Field(description="L0: Meta system definition")
    variables: VariableMapping = Field(description="L1: Variable space (SV/FV/CV/LV)")
    drivers: DriverSpace = Field(description="L2: Driver engine (quantified causal factors)")
    flow_feedback: FlowFeedbackSystem = Field(description="L3: Flow + feedback system")
    nonlinear_dynamics: NonlinearDynamics = Field(description="Nonlinear dynamics (inventory/capacity/elasticity)")

    # L4-L6 (mandatory)
    regime: RegimeEngine = Field(description="L4: Nonlinear regime engine")
    distortion: DistortionEngine = Field(description="L5: Distortion engine")
    alpha: AlphaEngine = Field(description="L6: Alpha engine")

    # L7 (optional)
    portfolio: Optional[InvestmentMapping] = Field(default=None, description="L7: Investment mapping (optional)")

    # Scoring (optional)
    industry_score: Optional[ScoreVector] = Field(default=None)
    companies_ranked: list[CompanyScore] = Field(default_factory=list)

    # Gates
    gate_validation: GateValidationReport

    # Fragilities
    key_fragilities: list[str] = Field(description="Key structural fragilities identified")
