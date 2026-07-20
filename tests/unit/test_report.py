"""Unit tests for the report formatters (plain/json/github/sarif)."""

from __future__ import annotations

import json

from skillcraft.ir import Diagnostic
from skillcraft.lint.report import format_sarif


def _diag(
    rule_id: str = "SC101",
    severity: str = "error",
    message: str = "boom",
    file: str = "a/b.md",
    line: int | None = 3,
    col: int | None = None,
) -> Diagnostic:
    return Diagnostic(rule_id, severity, message, file, line, col)


class TestSarif:
    def test_empty_is_valid_sarif(self):
        doc = json.loads(format_sarif([]))
        assert doc["version"] == "2.1.0"
        run = doc["runs"][0]
        assert run["tool"]["driver"]["name"] == "skillcraft"
        assert run["results"] == []
        assert run["tool"]["driver"]["rules"] == []

    def test_results_structure_and_level_mapping(self):
        diags = [
            _diag("SC101", "error", "e", line=1),
            _diag("SC104", "warning", "w", line=2),
            _diag("SC999", "info", "i", line=3),
        ]
        doc = json.loads(format_sarif(diags))
        results = doc["runs"][0]["results"]
        assert [r["ruleId"] for r in results] == ["SC101", "SC104", "SC999"]
        assert [r["level"] for r in results] == ["error", "warning", "note"]  # info → note
        assert results[0]["message"] == {"text": "e"}

    def test_location_uri_is_posix(self):
        result = json.loads(format_sarif([_diag(file="a/b.md", line=1)]))["runs"][0]["results"][0]
        loc = result["locations"][0]["physicalLocation"]
        assert loc["artifactLocation"]["uri"] == "a/b.md"
        assert loc["region"]["startLine"] == 1

    def test_windows_path_normalized_to_posix(self):
        uri = json.loads(format_sarif([_diag(file=r"src\skillcraft\rules.py", line=10)]))[
            "runs"
        ][0]["results"][0]["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
        assert uri == "src/skillcraft/rules.py"

    def test_no_line_omits_region(self):
        result = json.loads(format_sarif([_diag(line=None)]))["runs"][0]["results"][0]
        phys = result["locations"][0]["physicalLocation"]
        assert "region" not in phys
        assert "uri" in phys["artifactLocation"]

    def test_col_emitted_when_present(self):
        region = json.loads(format_sarif([_diag(line=5, col=12)]))["runs"][0]["results"][0][
            "locations"
        ][0]["physicalLocation"]["region"]
        assert region == {"startLine": 5, "startColumn": 12}

    def test_rules_list_deduped_and_sorted(self):
        diags = [_diag("SC101"), _diag("SC101"), _diag("SC302")]
        rules = json.loads(format_sarif(diags))["runs"][0]["tool"]["driver"]["rules"]
        assert [r["id"] for r in rules] == ["SC101", "SC302"]

    def test_unknown_severity_defaults_to_warning(self):
        result = json.loads(format_sarif([_diag(severity="bogus")]))["runs"][0]["results"][0]
        assert result["level"] == "warning"
