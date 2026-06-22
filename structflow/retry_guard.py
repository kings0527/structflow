"""Retry guard: automatically retry low-quality LLM outputs."""

from __future__ import annotations

from typing import Callable, TypeVar

from rich.console import Console

from structflow.models import GateResult, GateValidationReport

console = Console()

T = TypeVar("T")


class RetryGuard:
    """Retries LLM calls when output quality is below threshold."""

    def __init__(self, max_retries: int = 2, min_pass_rate: float = 0.8):
        self.max_retries = max_retries
        self.min_pass_rate = min_pass_rate

    def should_retry(self, gate_results: list[GateResult]) -> bool:
        """Determine if output quality is too low and should retry."""
        if not gate_results:
            return False
        pass_count = sum(1 for g in gate_results if g.passed)
        pass_rate = pass_count / len(gate_results)
        return pass_rate < self.min_pass_rate

    def run_with_retry(
        self,
        func: Callable[[], T],
        validate_func: Callable[[T], list[GateResult]],
        layer_name: str,
    ) -> T:
        """Run a function with retry logic based on validation quality."""
        for attempt in range(self.max_retries + 1):
            result = func()
            validation_results = validate_func(result)

            if not self.should_retry(validation_results):
                if attempt > 0:
                    console.print(
                        f"  [green]✓ {layer_name} passed after {attempt} retries[/green]"
                    )
                return result

            if attempt < self.max_retries:
                failed_gates = [g.gate_name for g in validation_results if not g.passed]
                console.print(
                    f"  [yellow]⚠ {layer_name} quality low (failed: {', '.join(failed_gates)}), "
                    f"retrying ({attempt + 1}/{self.max_retries})...[/yellow]"
                )

        # Final attempt failed, return last result anyway
        console.print(
            f"  [red]⚠ {layer_name} still below quality threshold after {self.max_retries} retries[/red]"
        )
        return result
