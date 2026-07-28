"""Retry guard: automatically retry low-quality LLM outputs with failure feedback."""

from __future__ import annotations

from typing import Callable, Optional, TypeVar

from rich.console import Console

from structflow.models import GateResult

console = Console()

T = TypeVar("T")


class RetryGuard:
    """Retries LLM calls when output quality is below threshold.

    Enhancements over naive retry:
    - Feeds failure reasons back to the LLM on retry so it can fix specific issues.
    - Raises temperature on each retry for more diverse outputs.
    """

    def __init__(self, max_retries: int = 2, min_pass_rate: float = 0.75):
        self.max_retries = max_retries
        self.min_pass_rate = min_pass_rate

    def should_retry(self, gate_results: list[GateResult]) -> bool:
        """Determine if output quality is too low and should retry."""
        if not gate_results:
            return False
        if any(
            not gate.passed
            and gate.gate_name.startswith("Hard_")
            for gate in gate_results
        ):
            return True
        pass_count = sum(1 for g in gate_results if g.passed)
        pass_rate = pass_count / len(gate_results)
        return pass_rate < self.min_pass_rate

    @staticmethod
    def _build_feedback(failed_gates: list[GateResult]) -> str:
        """Build a feedback string from failed gate results."""
        lines = ["上次输出存在以下问题，请针对性修正："]
        for gate in failed_gates:
            lines.append(f"- 【{gate.gate_name}】{gate.reason}")
        lines.append("")
        lines.append("请特别注意以上问题，确保本次输出通过所有检查。")
        return "\n".join(lines)

    def run_with_retry(
        self,
        func: Callable[..., T],
        validate_func: Callable[[T], list[GateResult]],
        layer_name: str,
    ) -> T:
        """Run a function with retry logic based on validation quality.

        ``func`` may optionally accept a ``retry_feedback`` keyword argument
        and a ``temperature`` keyword argument.  On the first attempt both are
        omitted (using defaults).  On retries the failure reasons are passed
        as ``retry_feedback`` and a slightly higher temperature is used to
        encourage diverse outputs.
        """
        result: T
        last_failed_gates: list[GateResult] = []

        for attempt in range(self.max_retries + 1):
            # Build kwargs for retry attempts
            kwargs: dict = {}
            if attempt > 0 and last_failed_gates:
                kwargs["retry_feedback"] = self._build_feedback(last_failed_gates)
                # Raise temperature slightly but cap at 0.5: the failure
                # feedback drives the fix; high temperature only increases
                # schema drift for structured JSON outputs.
                kwargs["temperature"] = min(0.2 + 0.15 * attempt, 0.5)

            try:
                result = func(**kwargs)
            except TypeError:
                # func doesn't accept retry_feedback / temperature — fall back
                result = func()

            validation_results = validate_func(result)

            if not self.should_retry(validation_results):
                if attempt > 0:
                    console.print(
                        f"  [green]✓ {layer_name} passed after {attempt} retries[/green]"
                    )
                return result

            last_failed_gates = [g for g in validation_results if not g.passed]

            if attempt < self.max_retries:
                failed_names = [g.gate_name for g in last_failed_gates]
                console.print(
                    f"  [yellow]⚠ {layer_name} quality low (failed: {', '.join(failed_names)}), "
                    f"retrying ({attempt + 1}/{self.max_retries}) with feedback...[/yellow]"
                )

        # Final attempt failed, return last result anyway
        console.print(
            f"  [red]⚠ {layer_name} still below quality threshold after {self.max_retries} retries[/red]"
        )
        return result
