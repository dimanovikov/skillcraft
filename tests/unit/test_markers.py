"""Unit tests for the HTML-comment marker conventions."""

from __future__ import annotations

from skillcraft.markers import (
    extra_meta_keys,
    managed_marker,
    parse_managed,
    parse_meta,
    strip_managed,
    strip_meta_comments,
)


class TestParseMeta:
    def test_extracts_name_description(self):
        text = '<!-- skillcraft:meta {"name":"x","description":"y"} -->\n# x\n'
        m = parse_meta(text)
        assert m["name"] == "x"
        assert m["description"] == "y"

    def test_extracts_scope(self):
        text = '<!-- skillcraft:scope {"globs":["*.py"]} -->\n'
        assert parse_meta(text)["scope_globs"] == ["*.py"]

    def test_malformed_json_ignored(self):
        assert parse_meta("<!-- skillcraft:meta {bad json} -->\n") == {}

    def test_no_comment(self):
        assert parse_meta("# plain\n") == {}


def test_extra_meta_keys_preserves_unmodelled():
    payload = {"name": "x", "description": "y", "version": "1.0", "author": "me"}
    assert extra_meta_keys(payload) == {"version": "1.0", "author": "me"}


class TestStripMetaComments:
    def test_removes_comment_lines(self):
        text = '<!-- skillcraft:meta {"name":"x"} -->\n# keep\n'
        assert strip_meta_comments(text) == "# keep\n"

    def test_collapses_excess_blanks(self):
        text = '<!-- skillcraft:meta {"name":"x"} -->\n\n\n\n# keep\n'
        # comment line removed, then 3+ newlines collapsed to 2
        assert strip_meta_comments(text) == "\n\n# keep\n"


class TestManaged:
    def test_marker_roundtrip(self):
        m = managed_marker("AGENTS.md")
        assert m == "<!-- skillcraft:managed-source path=AGENTS.md -->"
        assert parse_managed(m) == {"path": "AGENTS.md"}

    def test_legacy_marker_with_sha_still_parses(self):
        # Managed targets written before the sha field was dropped carry a
        # `sha=` fingerprint; parsing must still recover `path`.
        legacy = "<!-- skillcraft:managed-source path=AGENTS.md sha=deadbeef -->"
        info = parse_managed(legacy)
        assert info is not None
        assert info["path"] == "AGENTS.md"

    def test_parse_managed_none_without_marker(self):
        assert parse_managed("# no marker\n") is None

    def test_strip_leaves_handauthored_untouched(self):
        text = "---\nname: x\n---\nbody\n"
        assert strip_managed(text) == text

    def test_strip_removes_marker_and_leading_blanks(self):
        text = managed_marker("AGENTS.md") + "\n\n---\nname: x\n---\nbody\n"
        assert strip_managed(text) == "---\nname: x\n---\nbody\n"

    def test_strip_marker_directly_before_frontmatter(self):
        text = managed_marker("AGENTS.md") + "\n---\nname: x\n---\nbody\n"
        assert strip_managed(text) == "---\nname: x\n---\nbody\n"

    def test_strip_midfile_marker_preserves_rest(self):
        text = "# intro\n\n" + managed_marker("AGENTS.md") + "\n\n# more\n"
        stripped = strip_managed(text)
        assert "# intro" in stripped
        assert "# more" in stripped
        assert "managed-source" not in stripped
