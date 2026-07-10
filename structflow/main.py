"""CLI entry point for StructFlow Industry Scanner Agent."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

# Load .env file if it exists
env_path = Path.cwd() / ".env"
if env_path.exists():
    load_dotenv(env_path)

from structflow.agent import run_scan
from structflow.config import config
from structflow.models import ScanInput, TimeHorizon
from structflow.reporter import render_report
from structflow.workspace import ResearchWorkspace

console = Console()


def _write_run_manifest(
    output_dir: Path,
    workspace: ResearchWorkspace,
    scan_input: ScanInput,
    *,
    status: str,
    materials: list[str],
    error: str | None = None,
) -> None:
    payload = {
        "status": status,
        "subject": scan_input.industry,
        "region": scan_input.region,
        "time_horizon": scan_input.time_horizon.value,
        "created_at": datetime.now().astimezone().isoformat(),
        "data_dir": str(workspace.data_dir),
        "search_cache": str(workspace.search_cache_file),
        "materials": materials,
        "error": error,
    }
    (output_dir / "run_manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="structflow",
        description="StructFlow Atlas V2.2 — Nonlinear State-Space Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic scan with web search
  structflow "semiconductor" --region "China" --search

  # Scan with specific companies
  structflow "cloud computing" --peers AWS Azure GCP --search

  # Output as JSON
  structflow "EV battery" --output json --search

  # Use custom LLM configuration
  structflow "fintech" --model gpt-4o --api-key sk-xxx --base-url https://api.openai.com/v1

  # Disable web search (LLM knowledge only)
  structflow "semiconductor" --no-search

For detailed documentation, see CLI.md
        """,
    )

    # Required arguments
    parser.add_argument("industry", help="Industry to scan (e.g. 'semiconductor', 'cloud computing')")

    # Optional arguments
    parser.add_argument("--region", default=None, help="Geographic region (optional)")
    parser.add_argument(
        "--horizon",
        choices=["short", "mid", "long"],
        default="mid",
        help="Analysis time horizon (default: mid)",
    )
    parser.add_argument(
        "--peers",
        nargs="*",
        default=[],
        help="Comparable companies to include in scoring",
    )
    parser.add_argument(
        "--output",
        choices=["terminal", "markdown", "json"],
        default="markdown",
        help="Output format (default: markdown, writes to file)",
    )
    parser.add_argument(
        "--output-file",
        default=None,
        help="Output file path (default: auto-generated based on industry name)",
    )

    # LLM configuration
    parser.add_argument("--model", default=None,
                        help="LLM model: 'pro' (deepseek-v4-pro), 'flash' (deepseek-v4-flash, default), or full model name")
    parser.add_argument("--api-key", default=None, help="Override LLM API key")
    parser.add_argument("--base-url", default=None, help="Override LLM base URL")
    parser.add_argument("--no-thinking", action="store_true", help="Disable DeepSeek thinking mode (default: enabled)")
    parser.add_argument("--reasoning-effort", default=None, help="Reasoning effort level (e.g. high)")

    # Data collection
    parser.add_argument("--no-search", action="store_true", help="Disable web search (use LLM knowledge only)")
    parser.add_argument("--tavily-key", default=None, help="Override Tavily API key")
    parser.add_argument("--anysearch-key", default=None, help="Override AnySearch API key")
    parser.add_argument("--no-challenge", action="store_true", help="Disable adversarial challenge (faster but shallower)")
    parser.add_argument("--no-portfolio", action="store_true", help="Skip L7 Portfolio mapping (faster)")
    parser.add_argument(
        "--material",
        action="append",
        default=[],
        metavar="PATH",
        help="Add a Markdown/PDF/DOC/DOCX/text file or directory; repeatable",
    )
    parser.add_argument(
        "--refresh-search",
        action="store_true",
        help="Ignore the persistent search cache and fetch fresh evidence",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    scan_input = ScanInput(
        industry=args.industry,
        region=args.region,
        time_horizon=TimeHorizon(args.horizon),
        peer_set=args.peers or [],
    )

    # Determine search mode (default: enabled)
    enable_search = not args.no_search

    console.print(Panel(
        f"[bold]StructFlow Atlas V2.2[/bold] — Nonlinear State-Space Engine\n"
        f"Industry: [cyan]{scan_input.industry}[/cyan]\n"
        f"Region: {scan_input.region or 'global'} | Horizon: {scan_input.time_horizon.value}\n"
        f"Web Search: {'[green]Enabled[/green]' if enable_search else '[yellow]Disabled[/yellow]'}",
        title="🔍 V2.2 Scan Started",
        border_style="blue",
    ))

    from structflow.llm_client import LLMClient

    # Model shorthand: 'pro' → deepseek-v4-pro, 'flash' → deepseek-v4-flash
    MODEL_SHORTHAND = {
        "pro": "deepseek-v4-pro",
        "flash": "deepseek-v4-flash",
    }
    model_name = MODEL_SHORTHAND.get(args.model.lower(), args.model) if args.model else None

    client = LLMClient(
        model=model_name,
        api_key=args.api_key,
        base_url=args.base_url,
        enable_thinking=not args.no_thinking,
        reasoning_effort=args.reasoning_effort,
    )

    # Display model info
    actual_model = model_name or config.llm.model
    console.print(f"  [dim]Model: {actual_model} | Thinking: {'off' if args.no_thinking else 'on'}[/dim]")

    # ── Persistent subject workspace + per-run report directory ──
    workspace = ResearchWorkspace(Path.cwd() / "scans", scan_input.industry)
    workspace.prepare()
    migrated_cache = workspace.migrate_legacy_cache()
    if migrated_cache:
        console.print(f"  [dim]Search cache: {migrated_cache}[/dim]")
    if args.output_file:
        output_dir = Path(args.output_file).parent
        output_dir.mkdir(parents=True, exist_ok=True)
    else:
        output_dir = workspace.create_report_run(
            datetime.now().strftime("%Y%m%d_%H%M%S")
        )

    try:
        scan_output = run_scan(
            scan_input,
            client,
            enable_search=enable_search,
            tavily_key=args.tavily_key,
            anysearch_key=args.anysearch_key,
            enable_challenge=not args.no_challenge,
            enable_portfolio=not args.no_portfolio,
            output_dir=str(output_dir) if output_dir else None,
            data_dir=str(workspace.data_dir),
            material_paths=args.material,
            refresh_search=args.refresh_search,
        )
    except Exception as error:
        _write_run_manifest(
            output_dir,
            workspace,
            scan_input,
            status="failed",
            materials=args.material,
            error=str(error),
        )
        (output_dir / "run_failure.md").write_text(
            "# StructFlow Analysis Failed\n\n"
            f"**Subject**: {scan_input.industry}\n\n"
            f"**Reason**: {error}\n",
            encoding="utf-8",
        )
        console.print(f"[bold red]Scan failed: {error}[/bold red]")
        sys.exit(1)

    if args.output == "json":
        file_path = Path(args.output_file) if args.output_file else output_dir / "scan_output.json"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(scan_output.model_dump_json(indent=2), encoding="utf-8")
        console.print(f"[green]✓ JSON report saved to: {file_path}[/green]")
    elif args.output == "markdown":
        report = render_report(scan_output)
        file_path = Path(args.output_file) if args.output_file else output_dir / "scan_report.md"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(report, encoding="utf-8")
        console.print(f"[green]✓ Markdown report saved to: {file_path}[/green]")
    else:
        report = render_report(scan_output)
        console.print(Panel(report, title="📊 Industry Scan Report", border_style="green"))

    if output_dir:
        _write_run_manifest(
            output_dir,
            workspace,
            scan_input,
            status="completed",
            materials=args.material,
        )
        console.print(f"\n[dim]Report outputs: {output_dir}[/dim]")
        console.print(f"[dim]Persistent data: {workspace.data_dir}[/dim]")


if __name__ == "__main__":
    main()
