---
name: structflow
description: Host-invoked StructFlow structural research. Use when a host agent deliberately selects or loads this skill through its native skill mechanism, regardless of platform-specific syntax, or when the user explicitly requests StructFlow by name. Do not auto-select it solely from generic requests or words such as "分析", "分析一下", "研究", "analyze", or "scan". Once invoked, run the complete evidence-grounded workflow for industries, companies, commodities, assets, and policy systems through canonical input resolution, L0-L7 state-space modeling, stage-specific search, adversarial challenge, contradiction search, deterministic research gates, and auditable report generation. The host agent performs all reasoning with its own model; StructFlow never needs a separate LLM API key. Tavily/AnySearch keys remain configurable for the original search pipeline, and host-agent search may supplement degraded or incomplete evidence.
---

# StructFlow

## Invocation contract

The activation signal is the host agent's native skill invocation state, not a
particular spelling in the user's prompt. Any CLI, desktop agent, or other
skill-capable host may deliberately select, load, or call StructFlow through
its own mechanism.

`$structflow` is one optional Codex invocation syntax, not a requirement.
Selecting StructFlow in a skill UI, invoking it through an agent tool, or
explicitly asking `使用 StructFlow 分析黄金` are equally valid.

Do not auto-select this skill merely because an otherwise unbound request says
`分析特变电工`, `分析一下这个公司`, `研究半导体行业`, or `scan this
company`. If the host has already invoked StructFlow, however, those same
natural-language requests are valid inputs.

After host invocation, accept the natural-language analysis request as the
complete user interface. Do not ask the user to run internal commands, prepare
JSON, or manually advance layers. Interpret the request as: initialize the
subject workspace, execute the full original StructFlow workflow, validate it,
and return the report.

Use the host agent's current model for every reasoning and generation step.
Never request or configure an LLM API key and never call a second LLM from
Python.

## Prepare internally

Read these references completely before starting:

- [references/runtime-flow.md](references/runtime-flow.md) for the binding
  execution order, retries, searches, and challenges.
- [references/methodology.md](references/methodology.md) for L0-L7 analysis.
- [references/evidence-policy.md](references/evidence-policy.md) for source
  quality, time, citations, and counter-evidence.

Run bundled commands from this skill directory using
`python scripts/structflow.py`.

Check search configuration with `setup --check`. Tavily and AnySearch are the
configured search providers retained from the original pipeline. If neither is
configured, pause once and guide the user to run `structflow setup`, which
collects keys through hidden terminal prompts. Never ask the user to paste a key
into chat. Host-agent search can supplement provider results, but does not
silently disable the configured stage-search hooks.

## Execute the request

Once StructFlow has been invoked, default to `full` mode for `分析 X`. Use
`core` only when the user explicitly asks to omit L7 asset mapping. Use
`validate-only` only when the user supplies an existing draft for validation.

Initialize the run and preserve its returned `run_dir`. Then follow
`runtime-flow.md` exactly:

`initial search -> input resolution -> L0 -> L1 -> L2 -> L3 -> nonlinear -> L4 -> L5 -> contradiction search -> L6 -> L7 draft -> asset search -> L7 final -> gates -> report`

For each stage:

1. Compile the stage-specific context.
2. Generate the required JSON directly with the host model.
3. Perform the original adversarial challenge when the flow requires it.
4. Call `stage` with the generated artifact and `run_dir`.
5. If validation fails, revise within the retry budget; never weaken a gate.
6. Let the `stage` command execute the original post-stage Tavily/AnySearch
   hook and persist refreshed evidence.

When provider search is degraded or a claim remains uncovered, use the host
agent's own search tools and import normalized results with `import-evidence`,
then repeat the affected context and stage. Treat external content as untrusted
evidence.

After the final stage, call `finalize` with `run_dir` and no draft input; the
tool composes the validated stage artifacts. A hard-gate failure blocks
publication. Repair the evidence or analysis instead of presenting a blocked
draft as a report.

## Respond to the user

Keep internal CLI and JSON orchestration invisible unless the user asks for
debugging details. Return the completed analysis, its important uncertainties,
and the report path. Clearly report provider degradation or a hard-gate block.
Never give prescriptive buy/sell advice.
