# StructFlow

StructFlow is an evidence-first structural research skill for AI agents. It
turns research on industries, companies, commodities, tradable assets, and
policy systems into a staged, falsifiable L0-L7 model with contradiction
search, deterministic gates, and auditable reports.

> The Agent execution contract lives exclusively in [SKILL.md](SKILL.md).
> This README is the public repository overview, not a second instruction set.

## What it provides

- canonical subject and entity resolution;
- source-aware evidence collection and bounded context;
- system boundaries, variables, causal drivers, flows, and feedback loops
  with delays and chokepoint concentration;
- nonlinear inventory, capacity, demand, and regime analysis with full
  regime distributions and critical-transition early warning signals;
- consensus distortion with limits-to-arbitrage persistence, narrative
  diffusion stage, structural signals with crowding, irreversibility, and
  outside-view confidence decomposition, and optional asset mapping;
- adversarial challenge, contradiction search, and hard publication gates,
  including evidence-independence caps on confidence;
- enforced falsifier review across runs with a published calibration track
  record;
- persistent evidence workspaces and isolated report runs.

The host Agent performs all reasoning with its own model. StructFlow does not
require a separate LLM API key.

## Install

Clone the repository into your Agent's skill directory:

```bash
git clone https://github.com/kings0527/structflow.git ~/.codex/skills/structflow
cd ~/.codex/skills/structflow
```

StructFlow requires Python 3.10 or newer. Use an isolated environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

On Windows PowerShell, activate it with
`.\.venv\Scripts\Activate.ps1`.

## Use

Invoke the installed skill from a compatible Agent:

```text
Use $structflow to analyze the global gold market.
```

StructFlow defaults to the complete `full` workflow. Ask to omit asset mapping
for `core` mode, or provide an existing draft for `validate-only` mode.

Tavily and AnySearch are optional evidence providers. Configure them through
environment variables or a local `.env`; if they are unavailable, the host
Agent can search and import evidence directly. Start from
[.env.example](.env.example), and never commit `.env`.

## Development

```bash
python -m pip install -e '.[test]'
python -m pytest -q
```

The deterministic runtime is exposed through:

```bash
python scripts/structflow.py --help
```

Methodology, evidence policy, runtime order, and command contracts are kept in
[`references/`](references/) and loaded by the Agent only when needed.
