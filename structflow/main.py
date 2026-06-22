"""CLI entry point for StructFlow Industry Scanner Agent."""

from __future__ import annotations

import argparse
import sys

from rich.console import Console
from rich.panel import Panel

from structflow.agent import run_scan
from structflow.models import ScanInput, TimeHorizon
from structflow.reporter import render_report

console = Console()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="structflow",
        description="Industry Scanner Agent — Structural Intelligence System",
    )
    parser.add_argument("industry", help="Industry to scan (e.g. 'semiconductor', 'cloud computing')")
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
        default="terminal",
        help="Output format (default: terminal)",
    )
    parser.add_argument("--model", default=None, help="Override LLM model name")
    parser.add_argument("--api-key", default=None, help="Override OpenAI API key")
    parser.add_argument("--base-url", default=None, help="Override OpenAI base URL")
    parser.add_argument("--thinking", action="store_true", help="Enable DeepSeek thinking mode")
    parser.add_argument("--reasoning-effort", default=None, help="Reasoning effort level (e.g. high)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    scan_input = ScanInput(
        industry=args.industry,
        region=args.region,
        time_horizon=TimeHorizon(args.horizon),
        peer_set=args.peers or [],
    )

    console.print(Panel(
        f"[bold]StructFlow[/bold] — Industry Scanner Agent\n"
        f"Industry: [cyan]{scan_input.industry}[/cyan]\n"
        f"Region: {scan_input.region or 'global'} | Horizon: {scan_input.time_horizon.value}",
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
        scan_output = run_scan(scan_input, client)
    except Exception as error:
        console.print(f"[bold red]Scan failed: {error}[/bold red]")
        sys.exit(1)

    if args.output == "json":
        console.print_json(scan_output.model_dump_json(indent=2))
    elif args.output == "markdown":
        report = render_report(scan_output)
        console.print(report)
    else:
        report = render_report(scan_output)
        console.print(Panel(report, title="📊 Industry Scan Report", border_style="green"))


if __name__ == "__main__":
    main()
