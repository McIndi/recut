import io
import logging
import re
from pathlib import Path

import pytest

from recut.commands.grep import RETURN_CODES, _expand_inputs, main



def write_lines(tmp_path: Path, name: str, lines: list[str]) -> Path:
    path = tmp_path / name
    path.write_text("\n".join(lines) + "\n")
    return path


def test_expand_inputs_defaults_to_stdin():
    assert _expand_inputs(None) == ["-"]


def test_expand_inputs_glob_and_literal(tmp_path: Path):
    file_one = write_lines(tmp_path, "one.txt", ["alpha"])
    file_two = write_lines(tmp_path, "two.txt", ["beta"])

    expanded = _expand_inputs([str(tmp_path / "*.txt"), "-", "literal.txt"])

    assert "-" in expanded
    assert "literal.txt" in expanded
    assert {str(file_one), str(file_two)}.issubset(set(expanded))


def test_main_matches_from_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    file_path = write_lines(tmp_path, "sample.txt", ["alpha", "needle line", "beta"])

    code = main(["needle", str(file_path)])
    out = capsys.readouterr().out.strip().splitlines()

    assert code == RETURN_CODES["SUCCESS"]
    assert out == ["needle line"]


def test_main_ignore_case(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    file_path = write_lines(tmp_path, "case.txt", ["Hello", "HELLO", "hello"])

    code = main(["hello", "-i", str(file_path)])
    out = capsys.readouterr().out.strip().splitlines()

    assert code == RETURN_CODES["SUCCESS"]
    assert out == ["Hello", "HELLO", "hello"]


def test_main_word_only_matches_whole_words(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
):
    file_path = write_lines(
        tmp_path,
        "words.txt",
        ["scatter", "cat", "bobcat", "cat!", "concatenate"],
    )

    code = main(["cat", "-w", str(file_path)])
    out = capsys.readouterr().out.strip().splitlines()

    assert code == RETURN_CODES["SUCCESS"]
    assert out == ["cat", "cat!"]


def test_main_reports_no_match(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
):
    file_path = write_lines(tmp_path, "nomatch.txt", ["alpha", "beta"])

    code = main(["gamma", str(file_path)])
    captured = capsys.readouterr()

    assert code == RETURN_CODES["NO_MATCH"]
    assert captured.out.strip() == ""
    assert "No matches found" in captured.err or any(
        "No matches found" in rec.message for rec in caplog.records
    )


def test_main_returns_error_for_missing_file(
    capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
):
    code = main(["pattern", "missing.txt"])
    captured = capsys.readouterr()

    assert code == RETURN_CODES["ERROR"]
    assert "Error opening input file" in captured.err or any(
        "Error opening input file" in rec.message for rec in caplog.records
    )


def test_main_reads_from_stdin_by_default(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    monkeypatch.setattr("sys.stdin", io.StringIO("foo\nbar\n"))

    code = main(["bar"])
    out = capsys.readouterr().out.strip().splitlines()

    assert code == RETURN_CODES["SUCCESS"]
    assert out == ["bar"]


def test_main_returns_invalid_regex_on_compile_error(
    monkeypatch: pytest.MonkeyPatch,
):
    original_compile = re.compile

    def selective_boom(pattern: str, flags: int = 0):
        if pattern == "anything":
            raise re.error("boom")
        return original_compile(pattern, flags)

    monkeypatch.setattr("recut.commands.grep.re.compile", selective_boom)
    monkeypatch.setattr("sys.stdin", io.StringIO(""))

    code = main(["anything"])

    assert code == RETURN_CODES["INVALID_REGEX"]
