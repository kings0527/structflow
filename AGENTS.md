# AGENTS.md

Guidance for coding agents working on this repository. The runtime execution
contract for *using* StructFlow lives exclusively in [SKILL.md](SKILL.md);
this file only covers developing the repository itself.

## Layout

- `structflow/` — core source code; `structflow/skill_runtime.py` is the
  runtime core that stages, validates, and finalizes reports.
- `tests/` — pytest suite.
- `scans/` — generated research outputs (workspaces and report runs), not
  source code. Do not treat them as core code or edit them by hand.
- `references/` — methodology, evidence policy, runtime order, and command
  contracts consumed by the host agent at runtime.

## Development commands

```bash
python -m pip install -e '.[test]'
python -m pytest -q
```

Requires Python 3.10+. The deterministic CLI entry is
`python scripts/structflow.py --help`.

## Domain red lines (defined in SKILL.md)

- Never weaken a research gate; a hard-gate failure blocks publication.
- Never give prescriptive buy/sell advice.
- Never commit `.env`; StructFlow needs no separate LLM API key.
