"""Expose RepoRamp analysis as MCP tools over stdio.

Requires the optional ``mcp`` package: ``pip install "reporamp[mcp]"``.
Each tool analyzes the repository at ``path`` using its [tool.reporamp]
settings and returns JSON-serializable data.
"""

import json
from pathlib import Path

from reporamp.analyzer import find_dependency_cycles
from reporamp.pipeline import Analysis, run_configured_analysis
from reporamp.quality import parse_rule_selection, select_findings
from reporamp.report import render_json


def _analyze(path: str) -> tuple[Path, Analysis]:
    root = Path(path).expanduser().resolve()

    if not root.is_dir():
        raise ValueError(f"Repository directory not found: {path}")

    return root, run_configured_analysis(root)


def analyze_repo(path: str) -> dict:
    """Analyze a Python repository and return the full RepoRamp JSON report."""
    root, analysis = _analyze(path)

    return json.loads(
        render_json(
            analysis.modules,
            analysis.graph,
            root,
            analysis.findings,
            analysis.parse_errors,
        )
    )


def get_cycles(path: str) -> list[list[str]]:
    """Return the internal dependency cycles of a Python repository."""
    _, analysis = _analyze(path)

    return [list(cycle) for cycle in find_dependency_cycles(analysis.graph)]


def who_imports(path: str, module: str) -> list[str]:
    """Return the internal modules that import ``module`` (a dotted name)."""
    _, analysis = _analyze(path)

    if module not in analysis.graph.modules:
        raise ValueError(f"Unknown module: {module}")

    return sorted(
        {edge.source for edge in analysis.graph.edges if edge.target == module}
    )


def get_findings(path: str, rule_id: str | None = None) -> list[dict]:
    """Return code-quality findings, optionally only those for ``rule_id``."""
    _, analysis = _analyze(path)
    findings = analysis.findings

    if rule_id:
        findings = select_findings(findings, parse_rule_selection(rule_id))

    return [
        {
            "rule_id": finding.rule_id,
            "severity": finding.severity,
            "message": finding.message,
            "module": finding.module,
            "suggestion": finding.suggestion,
        }
        for finding in findings
    ]


TOOLS = (analyze_repo, get_cycles, who_imports, get_findings)


def create_server():
    """Build the MCP server with RepoRamp's tools registered."""
    from mcp.server.mcpserver import MCPServer

    server = MCPServer(
        "reporamp",
        instructions=(
            "Static structural analysis of Python repositories: dependency "
            "graph, cycles, importers of a module and code-quality findings."
        ),
    )

    for tool in TOOLS:
        server.tool()(tool)

    return server
