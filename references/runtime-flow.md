# Binding Runtime Flow

The host agent generates each layer with its current model, then invokes
deterministic validation, persistence, and search hooks.

Do not collapse the stages into one unconstrained report-generation pass.

## 1. Initialization and initial acquisition

1. Run `setup --check`.
2. Run `init SUBJECT --mode full` unless the user explicitly requests another
   mode. Preserve `run_dir`.
3. Run `collect SUBJECT` to execute the existing bilingual broad search:
   structure, policy, risk, revenue, capacity, price, and peers.
4. If configured providers are degraded, supplement only the missing questions
   with host-agent search and `import-evidence`.

Search cache reuse remains the default. Refresh only when the user requests
fresh evidence or current facts cannot be established from cache.

## 2. Canonical input resolution

1. Compile `context --layer profile`.
2. Generate an `EntityProfile` using the emitted profile schema.
3. For companies, resolve identity, ticker, jurisdiction, latest reporting
   period, all material segments, capital projects, financial facts, quality
   flags, and focused evidence gaps.
4. Preserve source-reported values and units before normalization.
5. Run `stage --stage profile`. This validates and saves the profile, resolves a
   consensus market snapshot when possible, and searches declared evidence
   gaps.
6. If gaps were searched, recompile profile context, regenerate once, and run
   the profile stage again.

The canonical profile is binding downstream.

## 3. Repeated layer protocol

For L0-L6, use this protocol:

1. Compile the bounded context for the layer.
2. Generate the layer artifact using `methodology.md` and the JSON schema.
3. Run the layer's pre-challenge structural self-check.
4. For L1-L6 except nonlinear, perform the adversarial challenge specified
   below and revise when warranted.
5. Run `stage SUBJECT --stage STAGE --input FILE --run-dir RUN_DIR`.
6. If stage validation fails, revise and retry. Allow at most two repairs for
   L0-L6.
7. Continue only after the stage command passes and completes its post-stage
   search hook.

The stage command enforces dependency order and never performs LLM generation.

## 4. Layer sequence and search hooks

| Stage | Host-agent output | Challenge | Search performed after acceptance |
|---|---|---|---|
| L0 | Function, boundary, failure cascade, coverage IDs | Basic boundary/coverage check | system dynamics and failure-risk search; persist matched system template |
| L1 | SV/FV/CV/LV and coverage IDs | classification, omissions, de-entity, narrative only in LV | template-guided state/control/latent variable search |
| L2 | quantified causal drivers | binding, proxy, direction, lag, nonlinearity | top driver-impact searches |
| L3 | flows and at least three feedback loops | missing flows, causal validity, loop type, amplification | flow-dynamics and feedback-loop searches |
| nonlinear | inventory, capacity lag, demand elasticity | no separate old challenge; enforce nonlinear assumption | inventory-cycle and capacity-lag search |
| L4 | current regime and next-regime probability | shock alternative, thresholds, omitted drivers, confidence | current-regime and transition-indicator searches |
| L5 | consensus, structural truth, distortion, citations | whether consensus is real, thesis support, score inflation, opposing case | consensus and mispricing search, followed automatically by contradiction search |
| L6 | bounded signal, direction, conditions, falsifiers, citations | no alpha override, regime consistency, confidence, maximum failure case | alpha-support search |

Before generating each layer, consume the evidence acquired by earlier layers.
Do not perform a search whose results have no downstream consumer.

## 5. Contradiction search

The accepted L5 stage must automatically search:

- evidence supporting `market_belief`;
- criticism or rebuttal of `structural_truth`;
- bearish or downside theses;
- bubble, overvaluation, and crash scenarios.

Recompile L6 context after these searches. L6 must cite support and
counter-evidence from the refreshed store.

## 6. L7 two-phase finalization

Run L7 only in `full` mode:

1. Generate an L7 draft from L6 and current L7 context.
2. Run `stage --stage l7-draft`. Do not require verified status yet. This
   searches each candidate asset's price, fundamentals, business role, and bear
   case.
3. Recompile L7 context.
4. Challenge the draft for L6 direction consistency, tradability, ticker/venue,
   fabricated prices, exposure, omitted assets, and risk.
5. Generate the evidence-consuming final L7.
6. Run `stage --stage l7-final`. This validates asset evidence and performs no
   further search.

Search after final L7 cannot retroactively verify it.

## 7. Final validation and publication

Run `finalize SUBJECT --run-dir RUN_DIR` without `--input`. The runtime composes
the accepted stage artifacts and reruns:

- five structural gates;
- output completeness and cross-layer binding;
- entity and material-segment coverage;
- financial period, unit, and numeric consistency;
- L5/L6 citation and source-independence gates;
- temporal and price grounding;
- advice boundary;
- regime/alpha reconciliation;
- L7 tradability and evidence checks.

Hard failures block `scan_report.md` and preserve `analysis_draft.json`,
`validation.json`, and a blocked `run_manifest.json`. Soft failures remain
visible in the published validation section.
