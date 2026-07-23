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
- have a measurable proxy;
- declare direction (`+`, `-`, or `nonlinear`);
- declare elasticity, volatility, lag, and regime dependency;
- represent a causal factor rather than a current-state description.

Use only the permitted categories: `macro`, `micro`, `policy`, `behavioral`,
`financial`, `structural`. Remove semantic duplicates and test whether the
direction changes across regimes.

## L3: flows and feedback

Trace capital, goods or service, information, risk, and subsidy flows when
present. Answer who funds the system, who captures value, where information is
delayed, where risk accumulates, and whether profit and risk are separated.

Model at least three causal feedback loops, including one reinforcing and one
balancing loop. Every loop needs a trigger, an explicit causal chain, and a
bounded amplification factor.

## Nonlinear dynamics

Never assume price is a linear function of cost without evidence. Model:

- inventory cycle stage, pressure, and price sensitivity;
- capex-to-capacity lag and supply response delay;
- demand elasticity and state dependency.

Check thresholds, saturation, delays, leverage, and sign reversals.

## L4: regime

Classify exactly one current regime: `expansion`, `contraction`, `transition`,
`bubble`, `collapse`, or `shock`. Estimate confidence and the next-regime
probability from weighted driver shocks, feedback state, inventory, leverage,
and capacity delay. Avoid false decimal precision and explain mixed signals.

## L5: distortion

Separate observable market consensus from structural reality. Every major claim
must trace to at least one L2 driver and one L1 variable.

- Cite at least two supporting evidence IDs.
- Cite at least one source that supports consensus or could falsify the thesis.
- Distinguish cycle, structural, liquidity, narrative, and policy distortion.
- Preserve event timing.
- Keep the distortion score low when the evidence is contested or stale.

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
- broken or one-sided feedback loops;
- linear assumptions;
- regime thresholds and shock alternatives;
- whether market consensus is real and current;
- strongest thesis falsifier and downside;
- confidence inflation and cross-layer contradictions;
- asset tradability, identity, price date, and evidence.

Revise only when evidence or logic warrants it. Preserve unresolved conflicts in
the report and lower confidence.
