"""CLI for the StructFlow skill's deterministic toolkit."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from pathlib import Path
from typing import Any

from structflow.market_data import ASSET_CLASSES, DATA_TYPES
from structflow.models import TimeHorizon
from structflow.skill_runtime import (
    GenerationMode,
    ResearchRequest,
    advance_stage,
    collect_provider_evidence,
    compile_layer_context,
    fetch_market_data,
    finalize_draft,
    import_evidence,
    initialize_run,
    methodology_for,
    record_resolution,
    save_profile,
    schema_for,
)


def _emit(payload: Any, *, stream=None) -> None:
    print(
        json.dumps(payload, ensure_ascii=False, indent=2),
        file=stream or sys.stdout,
    )


def _env_status(root: Path) -> dict[str, bool]:
    env_file = root / ".env"
    values: dict[str, str] = {}
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if "=" not in line or line.lstrip().startswith("#"):
                continue
            name, value = line.split("=", 1)
            values[name.strip()] = value.strip()
    return {
        "tavily": bool(os.getenv("TAVILY_API_KEY") or values.get("TAVILY_API_KEY")),
        "anysearch": bool(
            os.getenv("ANYSEARCH_API_KEY") or values.get("ANYSEARCH_API_KEY")
        ),
    }


def _setup(root: Path, *, check: bool) -> dict[str, Any]:
    status = _env_status(root)
    if check:
        return {
            "ok": True,
            "llm_key_required": False,
            "provider_search_optional": True,
            "host_search_supported": True,
            "optional_search_keys": status,
            "next_step": (
                "Configured providers are optional. Use host-agent search and "
                "`import-evidence` when they are unavailable or incomplete."
            ),
        }

    tavily = getpass.getpass(
        "Tavily API key (optional, hidden; Enter to keep/skip): "
    ).strip()
    anysearch = getpass.getpass(
        "AnySearch API key (optional, hidden; Enter to keep/skip): "
    ).strip()
    env_path = root / ".env"
    existing: list[str] = (
        env_path.read_text(encoding="utf-8").splitlines()
        if env_path.exists()
        else []
    )
    replacements = {
        "TAVILY_API_KEY": tavily,
        "ANYSEARCH_API_KEY": anysearch,
    }
    output: list[str] = []
    seen: set[str] = set()
    for line in existing:
        if "=" not in line or line.lstrip().startswith("#"):
            output.append(line)
            continue
        name = line.split("=", 1)[0].strip()
        if name in replacements:
            seen.add(name)
            output.append(
                f"{name}={replacements[name]}" if replacements[name] else line
            )
        else:
            output.append(line)
    for name, value in replacements.items():
        if name not in seen and value:
            output.append(f"{name}={value}")
    if output:
        env_path.write_text("\n".join(output) + "\n", encoding="utf-8")
        try:
            env_path.chmod(0o600)
        except OSError:
            pass
    return {
        "ok": True,
        "llm_key_required": False,
        "env_file": str(env_path),
        "optional_search_keys": _env_status(root),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="structflow",
        description=(
            "Deterministic evidence, schema, validation, and publication "
            "toolkit for the StructFlow skill."
        ),
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Workspace root containing scans/ (default: current directory)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    setup_parser = subparsers.add_parser(
        "setup", help="Configure optional search provider keys"
    )
    setup_parser.add_argument("--check", action="store_true")

    init_parser = subparsers.add_parser(
        "init", help="Initialize a subject workspace and report run"
    )
    init_parser.add_argument("subject")
    init_parser.add_argument("--region")
    init_parser.add_argument(
        "--horizon",
        choices=[item.value for item in TimeHorizon],
        default=TimeHorizon.MID.value,
    )
    init_parser.add_argument("--peer", action="append", default=[])
    init_parser.add_argument(
        "--mode",
        choices=[item.value for item in GenerationMode],
        default=GenerationMode.FULL.value,
    )
    init_parser.add_argument("--material", action="append", default=[])

    collect_parser = subparsers.add_parser(
        "collect", help="Use optional configured providers for broad evidence"
    )
    collect_parser.add_argument("subject")
    collect_parser.add_argument("--refresh", action="store_true")

    import_parser = subparsers.add_parser(
        "import-evidence", help="Merge host-agent search evidence"
    )
    import_parser.add_argument("subject")
    import_parser.add_argument("--input", required=True)

    market_parser = subparsers.add_parser(
        "fetch-market-data",
        help=(
            "Fetch structured market data (official sources first, "
            "fail-closed cross validation) and merge it as evidence"
        ),
    )
    market_parser.add_argument("subject")
    market_parser.add_argument(
        "--asset-class",
        required=True,
        choices=list(ASSET_CLASSES),
    )
    market_parser.add_argument(
        "--code",
        help="Instrument code (e.g. GLD, GC=F, ETH/USDT, CFTC market keyword)",
    )
    market_parser.add_argument(
        "--types",
        nargs="+",
        choices=list(DATA_TYPES),
        help="Data types to fetch (default: all supported by the asset class)",
    )
    market_parser.add_argument(
        "--date", help="Analysis cutoff YYYY-MM-DD (default: request date)"
    )

    context_parser = subparsers.add_parser(
        "context", help="Compile a bounded evidence packet"
    )
    context_parser.add_argument("subject")
    context_parser.add_argument(
        "--layer",
        required=True,
        choices=[
            "profile",
            "l0",
            "l1",
            "l2",
            "l3",
            "nonlinear",
            "l4",
            "l5",
            "l6",
            "l7",
        ],
    )
    context_parser.add_argument("--max-tokens", type=int, default=12_000)
    context_parser.add_argument("--output")

    schema_parser = subparsers.add_parser(
        "schema", help="Print a JSON Schema"
    )
    schema_parser.add_argument(
        "kind", choices=["profile", "analysis", "evidence"]
    )

    method_parser = subparsers.add_parser(
        "methodology", help="Return matching code-backed system methodology"
    )
    method_parser.add_argument("system_type")

    profile_parser = subparsers.add_parser(
        "save-profile", help="Validate and save the canonical input profile"
    )
    profile_parser.add_argument("subject")
    profile_parser.add_argument("--input", required=True)

    stage_parser = subparsers.add_parser(
        "stage",
        help=(
            "Validate one host-agent stage, save it, and run its post-stage "
            "search hook"
        ),
    )
    stage_parser.add_argument("subject")
    stage_parser.add_argument(
        "--stage",
        required=True,
        choices=[
            "profile",
            "l0",
            "l1",
            "l2",
            "l3",
            "nonlinear",
            "l4",
            "l5",
            "l6",
            "l7-draft",
            "l7-final",
        ],
    )
    stage_parser.add_argument("--input", required=True)
    stage_parser.add_argument("--run-dir", required=True)

    resolve_parser = subparsers.add_parser(
        "resolve",
        help=(
            "Grade the previous run's falsifiers and regime call before "
            "starting a new analysis"
        ),
    )
    resolve_parser.add_argument("subject")
    resolve_parser.add_argument("--input", required=True)
    resolve_parser.add_argument("--run-dir", required=True)

    finalize_parser = subparsers.add_parser(
        "finalize", help="Validate an agent-generated draft and publish a report"
    )
    finalize_parser.add_argument("subject")
    finalize_parser.add_argument(
        "--input",
        help=(
            "Optional complete draft. Omit to compose from validated stage "
            "artifacts in --run-dir."
        ),
    )
    finalize_parser.add_argument("--run-dir")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    root = Path(args.root).expanduser().resolve()
    try:
        if args.command == "setup":
            result = _setup(root, check=args.check)
        elif args.command == "init":
            result = initialize_run(
                ResearchRequest(
                    subject=args.subject,
                    region=args.region,
                    time_horizon=TimeHorizon(args.horizon),
                    peer_set=args.peer,
                    generation_mode=GenerationMode(args.mode),
                ),
                root=root,
                material_paths=args.material,
            )
        elif args.command == "collect":
            result = collect_provider_evidence(
                args.subject, root=root, refresh=args.refresh
            )
        elif args.command == "import-evidence":
            result = import_evidence(
                args.subject, args.input, root=root
            )
        elif args.command == "fetch-market-data":
            result = fetch_market_data(
                args.subject,
                asset_class=args.asset_class,
                code=args.code,
                data_types=args.types,
                as_of=args.date,
                root=root,
            )
        elif args.command == "context":
            text = compile_layer_context(
                args.subject,
                args.layer,
                root=root,
                max_tokens=args.max_tokens,
            )
            if args.output:
                output_path = Path(args.output)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(text, encoding="utf-8")
                result = {"ok": True, "context": str(output_path)}
            else:
                print(text)
                return
        elif args.command == "schema":
            result = schema_for(args.kind)
        elif args.command == "methodology":
            result = methodology_for(args.system_type)
        elif args.command == "save-profile":
            result = save_profile(
                args.subject, args.input, root=root
            )
        elif args.command == "stage":
            result = advance_stage(
                args.subject,
                args.stage,
                args.input,
                root=root,
                run_dir=args.run_dir,
            )
        elif args.command == "resolve":
            result = record_resolution(
                args.subject,
                args.input,
                root=root,
                run_dir=args.run_dir,
            )
        elif args.command == "finalize":
            result = finalize_draft(
                args.subject,
                args.input,
                root=root,
                run_dir=args.run_dir,
            )
        else:
            parser.error(f"Unknown command: {args.command}")
            return
        _emit(result)
        if isinstance(result, dict) and result.get("ok") is False:
            raise SystemExit(1)
    except SystemExit:
        raise
    except Exception as error:
        # Emit the error JSON on stdout: host agents read the JSON protocol
        # from stdout, and an empty stdout with exit 1 hides the real cause.
        _emit(
            {
                "ok": False,
                "error_type": type(error).__name__,
                "error": str(error),
            },
        )
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
