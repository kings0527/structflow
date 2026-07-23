# Deterministic Tool Contract

## Generation modes

| Mode | Agent work | Required output |
|---|---|---|
| `full` | Evidence, profile, L0-L7, adversarial pass | Analysis with verified portfolio |
| `core` | Evidence, profile, L0-L6, adversarial pass | Analysis without portfolio |
| `validate-only` | No new generation | Validate an existing analysis draft |

Modes change scope, not evidence quality. `core` still requires contradiction
evidence for L5 and L6.

## Commands

- `setup [--check]`: report or securely prompt for optional Tavily/AnySearch
  keys. It never requests an LLM key.
- `init SUBJECT`: create `scans/<subject>/data` and a new
  `scans/<subject>/report/<run-id>`.
- `collect SUBJECT`: run configured-provider broad evidence acquisition.
- `stage SUBJECT --stage ... --input FILE --run-dir DIR`: validate a
  host-generated profile/layer, persist it, and execute its post-stage search
  hook. `l7-draft` searches candidate assets; `l7-final` consumes those results
  without another search.
- `import-evidence SUBJECT --input FILE`: normalize and merge host-search
  evidence into the stable cache.
- `context SUBJECT --layer NAME`: compile a bounded evidence packet for
  `profile`, `l0`, `l1`, `l2`, `l3`, `nonlinear`, `l4`, `l5`, `l6`, or `l7`.
- `schema profile|analysis|evidence`: print JSON Schema.
- `methodology SYSTEM_TYPE`: return matching code-backed variable methodology.
- `save-profile SUBJECT --input FILE`: validate financial, temporal, coverage,
  and source-ID integrity before establishing the canonical profile.
- `finalize SUBJECT --run-dir DIR`: compose accepted stage artifacts, validate,
  and publish. `--input FILE` remains available for validate-only use.

Commands emit a compact JSON result on standard output. A nonzero exit means the
requested state transition did not complete.

## Workspace

```text
scans/<subject>/
  data/
    request.json
    entity_profile.json
    search/search_data.json
    materials/{originals,extracted,manifest.json}
  report/<run-id>/
    request.json
    entity_profile.schema.json
    analysis.schema.json
    analysis_draft.json
    validation.json
    scan_output.json
    scan_report.md
    run_manifest.json
```

Reusable evidence stays in `data`. Every analysis attempt stays in its run
directory. A hard-gate failure writes draft, validation, and manifest artifacts
but does not write a successful report.

## Secret handling

Host-agent reasoning uses the host's model and therefore requires no LLM API
key. `setup` stores optional search keys in the working directory's `.env`.
Prompts use hidden input, existing values are never displayed, and keys should
never be passed as command-line arguments or pasted into conversation.
