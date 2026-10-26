
"""Optional AI-powered insights for RepoRamp."""

import json
import os
from pathlib import Path

from reporamp.analyzer import DependencyGraph, find_dependency_cycles
from reporamp.parser import ModuleInfo


def build_analysis_context(
    modules: list[ModuleInfo],
    graph: DependencyGraph,
    root: Path | None = None,
) -> dict[str, object]:
    """Build a structured summary from repository analysis results.

    When ``root`` is given, module paths are made relative to it.
    """
    cycles = find_dependency_cycles(graph)

    def display(path: Path) -> str:
        if root is not None:
            try:
                return path.resolve().relative_to(root.resolve()).as_posix()
            except ValueError:
                pass
        return path.as_posix()

    return {
        "module_count": len(modules),
        "module_names": sorted(
            display(module.path) for module in modules
        ),
        "dependency_count": len(graph.edges),
        "dependencies": [
            {"source": edge.source, "target": edge.target}
            for edge in graph.edges
        ],
        "unresolved_import_count": len(graph.unresolved_imports),
        "cycle_count": len(cycles),
        "cycles": [list(cycle) for cycle in cycles],
    }


def generate_architecture_summary(
    context: dict[str, object],
) -> str:
    """Generate a basic architecture summary without an AI provider."""
    module_count = context["module_count"]
    dependency_count = context["dependency_count"]
    unresolved_count = context["unresolved_import_count"]
    cycle_count = context["cycle_count"]

    lines = [
        f"The repository contains {module_count} Python modules "
        f"and {dependency_count} internal dependencies.",
        f"It has {unresolved_count} unresolved imports and "
        f"{cycle_count} dependency cycles.",
    ]

    dependencies = context["dependencies"]

    if dependencies:
        lines.append("Module relationships:")

        for dependency in dependencies:
            lines.append(
                f"- {dependency['source']} depends on "
                f"{dependency['target']}."
            )
    else:
        lines.append("No internal module dependencies were detected.")

    return "\n".join(lines)


AI_MODEL = "claude-opus-5-5"

AI_SYSTEM_PROMPT = (
    "You are a software architect. You receive a JSON summary of a Python "
    "repository's static analysis: module paths, internal import edges, "
    "unresolved import counts and dependency cycles. Write a concise "
    "architecture overview in Markdown (at most about 300 words): the main "
    "components and how they relate, notable structural risks such as cycles "
    "or highly connected modules, and two or three concrete suggestions. "
    "Base every statement on the data provided."
)


class AISummaryUnavailable(Exception):
    """Raised when an AI summary cannot be produced; the message says why."""


def generate_ai_summary(context: dict[str, object]) -> str:
    """Summarize the analysis context with Claude.

    Only the structured ``context`` from ``build_analysis_context`` is sent;
    source code never leaves the machine. Requires ``ANTHROPIC_API_KEY`` and
    the optional ``anthropic`` package (``pip install "reporamp[ai]"``).

    Raises:
        AISummaryUnavailable: If the key or SDK is missing or the request fails.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")

    if not api_key:
        raise AISummaryUnavailable("ANTHROPIC_API_KEY is not set")

    try:
        import anthropic
    except ImportError as exc:
        raise AISummaryUnavailable(
            'the Anthropic SDK is not installed; run pip install "reporamp[ai]"'
        ) from exc

    client = anthropic.Anthropic(api_key=api_key)

    try:
        response = client.messages.create(
            model=AI_MODEL,
            max_tokens=16000,
            output_config={"effort": "low"},
            system=AI_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": json.dumps(context, indent=2, sort_keys=True),
                }
            ],
        )
    except anthropic.APIError as exc:
        raise AISummaryUnavailable(f"the Anthropic API request failed: {exc}") from exc

    if response.stop_reason == "refusal":
        raise AISummaryUnavailable("the model declined to summarize this repository")

    text = "".join(
        block.text for block in response.content if block.type == "text"
    ).strip()

    if not text:
        raise AISummaryUnavailable("the model returned an empty response")

    return text
