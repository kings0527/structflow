# StructFlow Methodology

## Governing intent

Convert narrative into a falsifiable model of power, stocks, flows, controls,
latent expectations, feedback, risk transfer, and regime change. Do not produce
buy/sell advice, emotional analysis, or an unsupported story.

Use the canonical profile and imported evidence as binding factual boundaries.
The analysis may infer mechanisms, but it must label assumptions and must not
invent current facts, prices, dates, entities, financials, or source IDs.

## L0: system definition

Define the subject as a function, not as a name or marketing category.

- Identify the irreducible function and what breaks if it disappears.
- Set an explicit inside/outside boundary.
- Describe a failure cascade rather than saying only that the system fails.
- For a company, include every material segment and capital dimension from the
  profile. Return exact `SEG-nnn` and `DIM-nnn` IDs only for explicitly modeled
  items.

## L1: variable space

Derive system-specific variables:

- SV: slow-moving stocks such as capacity, inventory, installed capital, user
  base, reserves, or accumulated obligations.
- FV: rates and movements such as output, shipments, cash, orders, investment,
  information, or risk transfer.
- CV: manipulable constraints such as price rules, policy, standards, credit,
  access, tax, or capacity controls.
- LV: unobservable states such as expectations, trust, risk appetite,
  narrative, coordination quality, or uncertainty.

Use at least three of each. Remove entity names from variables. Narrative belongs
only in LV. Bind every material profile segment and dimension with exact IDs.

## L2: causal drivers

Each driver must:

- map to exactly one of SV, FV, CV, or LV;
- have a measurable `proxy` in its own field (an index, price, filing line
  item, or published statistic);
- declare direction (`+`, `-`, or `nonlinear`);
- declare elasticity, volatility, lag, and regime dependency — all scores
  are normalized magnitudes in [0, 1]; elasticity is the absolute value,
  sign belongs in `direction`;
- represent a causal factor rather than a current-state description.

Use only the permitted categories: `macro`, `micro`, `policy`, `behavioral`,
`financial`, `structural`. Remove semantic duplicates and test whether the
direction changes across regimes.

## L3: flows and feedback

Trace capital, goods or service, information, risk, and subsidy flows when
present. Answer who funds the system, who captures value, where information is
delayed, where risk accumulates, and whether profit and risk are separated.

Model at least three causal feedback loops, including one reinforcing and one
balancing loop. Every loop needs a trigger, an explicit causal chain, a bounded
amplification factor, and a `delay` (`short`, `mid`, or `long`).
`amplification_factor` is a normalized strength in [0, 1], not a gain
multiple — never emit values above 1.

Control-theory rule: a balancing loop with a long delay is an oscillation
source (bullwhip, hog cycle), not a stabilizer. Never describe such a loop as
a stabilizing force; assess its oscillation amplitude and period instead.

Network-science rule: assess the topological concentration of each material
flow in `chokepoints` (at least one entry). Classify each node as
`distributed`, `concentrated`, or `single_point`. A `single_point` chokepoint
— one node whose failure severs the flow — is a first-class structural
fragility: it must reappear in the L0 failure cascade or the L6 `falsifiers`,
never remain buried in a variable list. Closure is checked by name-token
overlap, so reuse the chokepoint's exact name in the failure cascade or
falsifier text.

## Nonlinear dynamics

Never assume price is a linear function of cost without evidence. Model:

- inventory cycle stage, pressure, and price sensitivity;
- capex-to-capacity lag and supply response delay;
- demand elasticity and state dependency — elasticity is the magnitude
  (absolute value) in [0, 1]; the sign convention is dropped.

Check thresholds, saturation, delays, leverage, and sign reversals.

## L4: regime

Classify exactly one current regime: `expansion`, `contraction`, `transition`,
`bubble`, `collapse`, or `shock`. Estimate confidence and the next-regime
probability from weighted driver shocks, feedback state, inventory, leverage,
and capacity delay. Avoid false decimal precision and explain mixed signals.

Bayesian discipline: emit `regime_distribution`, the full next-period
probability distribution over all six regimes including remaining in the
current one. It must sum to 1.0 in steps no finer than 0.05.
`transition_probability` must equal the distribution argmax among regimes
other than the current one. A single point estimate is not falsifiable; the
distribution is what future runs are scored against.

Critical-transition rule (complex-systems science): examine
`early_warning_signals` before assigning transition probabilities. Systems
approaching a tipping point show measurable precursors — `critical_slowing`
(slower recovery from shocks), `rising_variance` (widening oscillation of
prices, spreads, or inventories), and `flickering` (brief jumps into another
state and back, including policy stance flip-flops). Report `none_observed`
with the proxy that was checked rather than omitting the assessment. A large
transition-away probability with no observed precursor requires an explicit
exogenous driver.

## L5: distortion

Separate observable market consensus from structural reality. Every major claim
must trace to at least one L2 driver and one L1 variable.

- Cite at least two supporting evidence IDs.
- Cite at least one source that supports consensus or could falsify the thesis.
- Distinguish cycle, structural, liquidity, narrative, and policy distortion.
- Preserve event timing.
- Keep the distortion score low when the evidence is contested or stale.
- Fill `persistence_mechanism` (limits to arbitrage): who is on the wrong side
  of the mispricing, and which concrete constraint — mandate, career risk,
  liquidity, position limits, information latency — prevents arbitrage from
  closing the gap. A mispricing without a persistence mechanism is only a
  disagreement with the market and must not drive L6.
- Classify `narrative_stage` on the diffusion curve (`emerging`, `spreading`,
  `saturated`, `fading`) with a measurable `narrative_stage_proxy` such as
  media volume slope or search-trend direction. The same story means opposite
  things early versus at saturation.

Then perform claim-specific contradiction searches before continuing.

## L6: bounded structural signal

Explain consensus, structural view, the precise gap, conditions under which it
persists, and falsifiers. `direction` is structural exposure (`long`, `short`,
or `neutral`), not a recommendation.

The signal cannot override L2 drivers or ignore L4. A long exposure under a
probable contraction must explicitly explain what is already priced, the
counter-cyclical mechanism, and reversal or failure triggers. Cite both support
and counter-evidence. Do not emit a price unless the canonical profile contains
a matching dated consensus snapshot.

Also required in L6:

- `falsifiers`: at least one concrete, observable condition that would
  invalidate the structural view, as a structured list — not buried in
  prose. These commitments are graded against reality in the next run.
- `crowding_assessment`: whether the structural view itself is already a
  crowded trade. Consult positioning evidence (fund flows, futures
  positioning, short interest, sell-side alignment) or state explicitly what
  was checked and found unavailable.
- `irreversibility`: classify the downside as `none`, `partial`, or
  `absorbing`. An absorbing state (bankruptcy, delisting, nationalization,
  technology zeroing) breaks expected-value reasoning; when declared, describe
  the concrete `ruin_path` and never weight it like a recoverable drawdown.
- `reference_class` and `prior_probability` (outside view first): name the
  historical class of situations this case belongs to and its rough base
  rate before arguing the inside view. Then list `evidence_adjustments` —
  cited, directional updates that move the prior toward the final
  confidence. Confidence that cannot be reached from the prior through cited
  adjustments is confidence inflation.
- Confidence is capped by evidence independence: with fewer than two
  independent upstream origins among the supporting citations, confidence
  cannot exceed 0.50; two origins cap it at 0.65, three at 0.80, four or
  more at 0.90. Two pages repeating one upstream report are one origin.

## L7: optional asset mapping

Run only in `full` mode. Separate tradable assets from operating nodes.

- `best_positioned` and `overvalued` must be tradable types and include
  ticker/venue where applicable.
- Every asset needs evidence IDs and a non-`unverified` status.
- A business unit may appear as a fragility node but not as a tradable asset.
- Regenerate L7 after asset-specific search so the final mapping consumes the
  verification evidence.

## Adversarial pass

Before finalization, challenge:

- classification mistakes and missing variables;
- driver direction, proxy, lag, and regime dependence;
- broken or one-sided feedback loops, and loops whose delay makes a
  "stabilizer" an oscillator;
- linear assumptions;
- regime thresholds and shock alternatives, and whether the regime
  distribution hides confidence in a single branch;
- whether market consensus is real and current;
- whether the persistence mechanism actually binds the arbitrageurs it names;
- whether the structural view itself is the crowded trade;
- strongest thesis falsifier and downside, including any absorbing state;
- confidence inflation and cross-layer contradictions;
- asset tradability, identity, price date, and evidence.

Revise only when evidence or logic warrants it. Preserve unresolved conflicts in
the report and lower confidence.
