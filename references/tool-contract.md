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
  `scans/<subject>/report/<run-id>`. When the subject already has a published
  run, the previous L6/L4 commitments are copied into the new run as
  `prior_commitments.json` and the result flags `resolution_required`.
- `resolve SUBJECT --input FILE --run-dir DIR`: grade the previous run's
  commitments against fresh evidence before L0. The input is
  `{"verdicts": [{"commitment", "status", "evidence_ids", "note"}]}` with
  status one of `hit | miss | partial | indeterminate | not_yet_evaluable`.
  Verdicts append to `data/resolutions.json` and feed the published track
  record. The L0 stage is blocked until this runs.
- `collect SUBJECT`: run configured-provider broad evidence acquisition.
- `stage SUBJECT --stage ... --input FILE --run-dir DIR`: validate a
  host-generated profile/layer, persist it, and execute its post-stage search
  hook. `l7-draft` searches candidate assets; `l7-final` consumes those results
  without another search.
- `import-evidence SUBJECT --input FILE`: normalize and merge host-search
  evidence into the stable cache.
- `fetch-market-data SUBJECT --asset-class CLASS [--code CODE]
  [--types TYPE ...] [--date YYYY-MM-DD]`: fetch structured market data from
  official-first providers, cross-validate it, and merge it into the same
  evidence cache. See the dedicated section below.
- `context SUBJECT --layer NAME`: compile a bounded evidence packet for
  `profile`, `l0`, `l1`, `l2`, `l3`, `nonlinear`, `l4`, `l5`, `l6`, or `l7`.
  The packet embeds the layer's binding JSON schema; generate against that
  schema — field descriptions carry ranges, enums, and unit conventions.
- `schema profile|analysis|evidence`: print JSON Schema.
- `methodology SYSTEM_TYPE`: return matching code-backed variable methodology.
- `save-profile SUBJECT --input FILE`: validate financial, temporal, coverage,
  and source-ID integrity before establishing the canonical profile.
- `finalize SUBJECT --run-dir DIR`: compose accepted stage artifacts, validate,
  and publish. `--input FILE` remains available for validate-only use.

Commands emit a compact JSON result on standard output. A nonzero exit means the
requested state transition did not complete.

## fetch-market-data contract

```text
structflow [--root PATH] fetch-market-data SUBJECT
  --asset-class {equity|commodity|crypto|cn_stock|cn_sector}
  [--code CODE] [--types {price|positioning|macro|funding|flow|institutional|inventory} ...]
  [--date YYYY-MM-DD]
```

- `--asset-class` (required) routes to provider combinations: `commodity` ->
  CFTC COT positioning + dual-source price/ETF flow + SEC 13F institutional +
  EIA weekly energy inventory + macro anchors; `equity` -> dual-source
  price/ETF flow + SEC 13F institutional + macro anchors; `crypto` ->
  Binance/OKX spot price, open interest, funding rate + macro anchors;
  `cn_stock` -> EastMoney/Sina dual-upstream price + capital flow + margin +
  block trades + dragon-tiger list + macro anchors; `cn_sector` ->
  EastMoney/THS dual-upstream sector index + sector flow rank + sector ETF
  shares + macro anchors. Macro anchors come from two independent providers —
  FRED (US rates/dollar, needs `FRED_API_KEY`) and DBnomics (ECB, Eurostat,
  BIS official series, keyless) — each degrading on its own. A-share records
  are Tier 3 aggregator-grade (AkShare), annotated accordingly.
- `--code` is the instrument code (`GLD`, `GC=F`, `ETH/USDT`, `600519`, a
  sector name for `cn_sector`, or a CFTC market keyword). Required in
  practice for `equity`, `crypto`, and `cn_stock`; COT and `cn_sector` fall
  back to the subject keyword. A `PROVIDER/DATASET/SERIES`-shaped code (two
  or more slashes) is additionally fetched by DBnomics as a custom macro
  series.
- `--types` restricts data types; default is every type the asset class
  supports. `institutional` maps to SEC 13F for `equity`/`commodity`
  (requires the `EDGAR_IDENTITY` environment variable) and to block trades +
  dragon-tiger list for `cn_stock`. `inventory` maps to EIA weekly US
  crude/natural-gas stocks for `commodity` (requires `EIA_API_KEY`).
- `--date` sets the analysis cutoff; default is the request's analysis date.
  Records dated after the cutoff are rejected.

The JSON result is:

```json
{
  "ok": true,
  "asset_class": "commodity",
  "received": 4,
  "rejected_future_records": 0,
  "added_unique_sources": 4,
  "total_unique_sources": 52,
  "categories": ["market_data_positioning", "market_data_price"],
  "cross_validation": {"passed": [], "failed": []},
  "degraded": [],
  "failures": [],
  "search_cache": "scans/<subject>/data/search/search_data.json",
  "source_ids": ["src_001"]
}
```

- `ok` is true only when at least one record passed future-date rejection
  against the effective analysis date — i.e. the channel produced data usable
  on that date. An idempotent rerun keeps `ok: true` even with
  `added_unique_sources: 0` (the records are already in the store); if every
  record is rejected as future-dated (e.g. a backdated `--date`), `ok` is
  false. `ok: false` exits with code 1 but still prints the full JSON, so read
  `degraded` and `failures` from stdout to decide the fallback.
- `source_ids` lists every source ID in the merged store, not only the newly
  added ones.
- Fail-closed behavior: aggregator prices require two independent upstreams
  within 0.5% deviation and a 3-day observation window. A failed or
  single-source validation yields zero price records; the reason appears in
  `cross_validation.failed` and `degraded`. Missing dependencies, network
  errors, and a missing `FRED_API_KEY` never raise — they surface as
  structured `failures` entries. Wrong data is worse than no data.
- On any non-empty `degraded` or `failures`, cover the gap with host-agent
  search plus `import-evidence`.
- Configuration: `MARKET_DATA_ENABLED`, `MARKET_DATA_TIMEOUT`,
  `MARKET_DATA_PRICE_TOLERANCE`, `MARKET_DATA_LOOKBACK_DAYS`,
  `FRED_API_KEY`, and `EIA_API_KEY` in `.env`. Disabling the channel returns
  `ok: false` with a `degraded` notice.

## Workspace

```text
scans/<subject>/
  data/
    request.json
    entity_profile.json
    resolutions.json
    search/search_data.json
    materials/{originals,extracted,manifest.json}
  report/<run-id>/
    request.json
    entity_profile.schema.json
    analysis.schema.json
    prior_commitments.json
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
