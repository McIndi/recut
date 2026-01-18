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


def test_main_with_filename_single_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    file_path = write_lines(tmp_path, "sample.txt", ["alpha", "needle line", "beta"])

    code = main(["needle", "-H", str(file_path)])
    out = capsys.readouterr().out.strip().splitlines()

    assert code == RETURN_CODES["SUCCESS"]
    assert len(out) == 1
    assert str(file_path) in out[0]
    assert "needle line" in out[0]


def test_main_with_filename_multiple_files(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    file1 = write_lines(tmp_path, "file1.txt", ["needle", "alpha"])
    file2 = write_lines(tmp_path, "file2.txt", ["beta", "needle"])

    code = main(["needle", "-H", str(file1), str(file2)])
    out = capsys.readouterr().out.strip().splitlines()

    assert code == RETURN_CODES["SUCCESS"]
    assert len(out) == 2
    assert any(str(file1) in line for line in out)
    assert any(str(file2) in line for line in out)


def test_main_line_number(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    file_path = write_lines(tmp_path, "sample.txt", ["alpha", "needle line", "beta"])

    code = main(["needle", "-n", str(file_path)])
    out = capsys.readouterr().out.strip().splitlines()

    assert code == RETURN_CODES["SUCCESS"]
    assert len(out) == 1
    assert out[0].startswith("2:")
    assert "needle line" in out[0]


def test_main_line_number_multiple_matches(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    file_path = write_lines(tmp_path, "sample.txt", ["alpha", "needle", "beta", "needle line"])

    code = main(["needle", "-n", str(file_path)])
    out = capsys.readouterr().out.strip().splitlines()

    assert code == RETURN_CODES["SUCCESS"]
    assert len(out) == 2
    assert out[0].startswith("2:")
    assert out[1].startswith("4:")


def test_main_with_filename_and_line_number(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    file_path = write_lines(tmp_path, "sample.txt", ["alpha", "needle line", "beta"])

    code = main(["needle", "-H", "-n", str(file_path)])
    out = capsys.readouterr().out.strip().splitlines()

    assert code == RETURN_CODES["SUCCESS"]
    assert len(out) == 1
    assert str(file_path) in out[0]
    assert "2:" in out[0]
    assert "needle line" in out[0]


def test_main_quiet_mode_match(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    file_path = write_lines(tmp_path, "sample.txt", ["alpha", "needle line", "beta"])

    code = main(["needle", "-q", str(file_path)])
    out = capsys.readouterr().out

    assert code == RETURN_CODES["SUCCESS"]
    assert out == ""


def test_main_quiet_mode_no_match(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    file_path = write_lines(tmp_path, "sample.txt", ["alpha", "beta", "gamma"])

    code = main(["needle", "-q", str(file_path)])
    out = capsys.readouterr().out

    assert code == RETURN_CODES["NO_MATCH"]
    assert out == ""


def test_main_files_with_matches(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    file1 = write_lines(tmp_path, "file1.txt", ["needle", "alpha"])
    file2 = write_lines(tmp_path, "file2.txt", ["beta", "gamma"])
    file3 = write_lines(tmp_path, "file3.txt", ["needle again"])

    code = main(["needle", "-l", str(file1), str(file2), str(file3)])
    out = capsys.readouterr().out.strip().splitlines()

    assert code == RETURN_CODES["SUCCESS"]
    assert len(out) == 2
    assert str(file1) in out
    assert str(file3) in out
    assert str(file2) not in out


def test_main_files_with_matches_no_matches(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    file1 = write_lines(tmp_path, "file1.txt", ["alpha", "beta"])
    file2 = write_lines(tmp_path, "file2.txt", ["gamma", "delta"])

    code = main(["needle", "-l", str(file1), str(file2)])
    out = capsys.readouterr().out

    assert code == RETURN_CODES["NO_MATCH"]
    assert out.strip() == ""


def test_main_quiet_and_files_with_matches_conflict(tmp_path: Path):
    """Test that -q and -l together behaves reasonably (quiet takes precedence)"""
    file_path = write_lines(tmp_path, "sample.txt", ["needle", "alpha"])

    # Both flags together - quiet should suppress output
    code = main(["needle", "-q", "-l", str(file_path)])
    assert code == RETURN_CODES["SUCCESS"]
