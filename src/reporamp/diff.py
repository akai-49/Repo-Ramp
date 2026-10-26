"""Compare two RepoRamp JSON reports."""

import json
from pathlib import Path

SUPPORTED_SCHEMA_VERSIONS = (1, 2)


def load_report(path: Path) -> dict:
    """Load a RepoRamp JSON report and check its schema version."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    version = payload.get("schema_version") if isinstance(payload, dict) else None

    if version not in SUPPORTED_SCHEMA_VERSIONS:
        raise ValueError(f"{path}: unsupported RepoRamp schema_version {version!r}")

    return payload


def _changes(base: set, head: set) -> dict[str, list]:
    return {"added": sorted(head - base), "removed": sorted(base - head)}


def diff_reports(base: dict, head: dict) -> dict[str, dict[str, list]]:
    """Return sorted added/removed modules, dependencies, cycles and findings.

    Findings are matched by rule ID, module and message.
    """

    def modules(report: dict) -> set[str]:
        return {module["path"] for module in report.get("modules", [])}

    def dependencies(report: dict) -> set[tuple[str, str]]:
        return {
            (edge["source"], edge["target"]) for edge in report.get("dependencies", [])
        }

    def cycles(report: dict) -> set[tuple[str, ...]]:
        return {tuple(cycle) for cycle in report.get("dependency_cycles", [])}

    def findings(report: dict) -> set[tuple[str, str, str]]:
        return {
            (item["rule_id"], item["module"], item["message"])
            for item in report.get("quality_findings", [])
        }

    return {
        "modules": _changes(modules(base), modules(head)),
        "dependencies": _changes(dependencies(base), dependencies(head)),
        "cycles": _changes(cycles(base), cycles(head)),
        "findings": _changes(findings(base), findings(head)),
    }


def has_new_problems(diff: dict[str, dict[str, list]]) -> bool:
    """Return True if the head report adds cycles or findings."""
    return bool(diff["cycles"]["added"] or diff["findings"]["added"])


SECTION_TITLES = {
    "modules": ("Added modules", "Removed modules"),
    "dependencies": ("Added dependencies", "Removed dependencies"),
    "cycles": ("New cycles", "Resolved cycles"),
    "findings": ("New findings", "Resolved findings"),
}


def _describe(section: str, item: object) -> str:
    if section == "dependencies":
        return f"`{item[0]}` → `{item[1]}`"
    if section == "cycles":
        return " → ".join((*item, item[0]))
    if section == "findings":
        return f"[{item[0]}] `{item[1]}`: {item[2]}"
    return f"`{item}`"


def render_diff(diff: dict[str, dict[str, list]]) -> str:
    """Render a diff as Markdown."""
    lines = ["# RepoRamp Report Diff", ""]

    for section, titles in SECTION_TITLES.items():
        for key, title in zip(("added", "removed"), titles, strict=True):
            items = diff[section][key]
            lines.extend([f"## {title} ({len(items)})", ""])
            lines.extend(f"- {_describe(section, item)}" for item in items)
            if not items:
                lines.append("- None")
            lines.append("")

    return "\n".join(lines)
