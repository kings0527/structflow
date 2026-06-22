"""CLI entry point for StructFlow Industry Scanner Agent."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

# Load .env file if it exists
env_path = Path.cwd() / ".env"
if env_path.exists():
    load_dotenv(env_path)

from structflow.agent import run_scan
from structflow.models import ScanInput, TimeHorizon
from structflow.reporter import render_report

console = Console()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="structflow",
        description="Industry Scanner Agent — Structural Intelligence System",
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
    parser.add_argument("--model", default=None, help="Override LLM model name")
    parser.add_argument("--api-key", default=None, help="Override LLM API key")
    parser.add_argument("--base-url", default=None, help="Override LLM base URL")
    parser.add_argument("--thinking", action="store_true", help="Enable DeepSeek thinking mode")
    parser.add_argument("--reasoning-effort", default=None, help="Reasoning effort level (e.g. high)")

    # Data collection
    parser.add_argument("--no-search", action="store_true", help="Disable web search (use LLM knowledge only)")
    parser.add_argument("--tavily-key", default=None, help="Override Tavily API key")
    parser.add_argument("--anysearch-key", default=None, help="Override AnySearch API key")
    parser.add_argument("--no-challenge", action="store_true", help="Disable adversarial challenge (faster but shallower)")

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
        f"[bold]StructFlow[/bold] — Industry Scanner Agent\n"
        f"Industry: [cyan]{scan_input.industry}[/cyan]\n"
        f"Region: {scan_input.region or 'global'} | Horizon: {scan_input.time_horizon.value}\n"
        f"Web Search: {'[green]Enabled[/green]' if enable_search else '[yellow]Disabled[/yellow]'}",
        title="🔍 Scan Started",
        border_style="blue",
    ))

    from structflow.llm_client import LLMClient
    client = LLMClient(
        model=args.model,
        api_key=args.api_key,
        base_url=args.base_url,
        enable_thinking=args.thinking,
        reasoning_effort=args.reasoning_effort,
    )

    try:
        scan_output = run_scan(
            scan_input,
            client,
            enable_search=enable_search,
            tavily_key=args.tavily_key,
            anysearch_key=args.anysearch_key,
            enable_challenge=not args.no_challenge,
        )
    except Exception as error:
        console.print(f"[bold red]Scan failed: {error}[/bold red]")
        sys.exit(1)

    if args.output == "json":
        output_path = args.output_file or f"{scan_input.industry}_scan.json"
        Path(output_path).write_text(scan_output.model_dump_json(indent=2), encoding="utf-8")
        console.print(f"[green]✓ JSON report saved to: {output_path}[/green]")
    elif args.output == "markdown":
        report = render_report(scan_output)
        output_path = args.output_file or f"{scan_input.industry}_scan.md"
        Path(output_path).write_text(report, encoding="utf-8")
        console.print(f"[green]✓ Markdown report saved to: {output_path}[/green]")
    else:
        report = render_report(scan_output)
        console.print(Panel(report, title="📊 Industry Scan Report", border_style="green"))


if __name__ == "__main__":
    main()
