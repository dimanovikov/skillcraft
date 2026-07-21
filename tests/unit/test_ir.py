"""Unit tests for the intermediate representation helpers."""

from __future__ import annotations

from skillcraft.ir import find_imports, parse_sections, severity_rank, split_frontmatter


class TestSplitFrontmatter:
    def test_extracts_frontmatter(self):
        text = "---\nname: x\ndescription: y\n---\nbody\n"
        fm, body, before = split_frontmatter(text)
        assert fm == "name: x\ndescription: y\n"
        assert before == 4  # opening ---, name, description, closing ---
        assert body == "body\n"

    def test_no_frontmatter(self):
        fm, body, before = split_frontmatter("# just body\n")
        assert fm is None
        assert body == "# just body\n"
        assert before == 0

    def test_no_closing_delimiter_treated_as_body(self):
        text = "---\nname: x\nno closing line\n"
        fm, body, before = split_frontmatter(text)
        assert fm is None
        assert body == text
        assert before == 0

    def test_must_start_at_column_zero(self):
        # a leading space means this is not frontmatter
        fm, _, _ = split_frontmatter(" ---\nname: x\n---\nbody\n")
        assert fm is None

    def test_empty_frontmatter(self):
        fm, body, before = split_frontmatter("---\n---\nbody\n")
        assert fm == ""
        assert body == "body\n"
        assert before == 2  # opening --- + closing ---


class TestParseSections:
    def test_sections_with_levels(self):
        body = "# Title\nintro\n## Sub\nsub body\n"
        secs = parse_sections(body)
        assert len(secs) == 2
        assert secs[0].heading == "# Title"
        assert secs[0].level == 1
        assert secs[0].body == "intro"
        assert secs[1].heading == "## Sub"
        assert secs[1].level == 2
        assert secs[1].body == "sub body"

    def test_no_headings(self):
        assert parse_sections("just text\nmore\n") == []

    def test_first_line_rebases_line_numbers(self):
        # first_line lets converters keep section lines file-relative.
        secs = parse_sections("# H\n", first_line=5)
        assert secs[0].start_line == 5


class TestFindImports:
    def test_resolves_existing(self, tmp_path):
        target = tmp_path / "dep.md"
        target.write_text("x", encoding="utf-8")
        refs = find_imports("see @dep.md\n", tmp_path)
        assert len(refs) == 1
        assert refs[0].path == "dep.md"
        assert refs[0].resolved == target.resolve()
        assert refs[0].line == 1

    def test_unresolved(self, tmp_path):
        refs = find_imports("@nope.md\n", tmp_path)
        assert len(refs) == 1
        assert refs[0].resolved is None

    def test_bare_word_not_an_import(self, tmp_path):
        # @anthropic has no '/' or '.', so it is not treated as a file import
        assert find_imports("ping @anthropic please\n", tmp_path) == []

    def test_multiple_on_one_line(self, tmp_path):
        (tmp_path / "a.md").write_text("x", encoding="utf-8")
        (tmp_path / "b.md").write_text("x", encoding="utf-8")
        refs = find_imports("@a.md and @b.md\n", tmp_path)
        assert {r.path for r in refs} == {"a.md", "b.md"}

    def test_first_line_rebases_line_numbers(self, tmp_path):
        refs = find_imports("see @dep.md\n", tmp_path, first_line=10)
        assert refs[0].line == 10


def test_severity_rank_ordering():
    assert severity_rank("error") > severity_rank("warning")
    assert severity_rank("warning") > severity_rank("info")
    assert severity_rank("info") > severity_rank("bogus")
