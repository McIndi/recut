import io
from pathlib import Path

import pytest

from recut.commands.cut import RETURN_CODES, main


def write_lines(tmp_path: Path, name: str, lines: list[str]) -> Path:
    path = tmp_path / name
    path.write_text("\n".join(lines) + "\n")
    return path


class TestFieldMode:
    """Tests for -f (field extraction) mode."""

    def test_single_field_default_delimiter(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ):
        """Extract single field with default tab delimiter."""
        file_path = write_lines(
            tmp_path,
            "data.txt",
            ["field1\tfield2\tfield3", "alpha\tbeta\tgamma"],
        )

        code = main(["--field", "2", str(file_path)])
        out = capsys.readouterr().out.strip().splitlines()

        assert code == RETURN_CODES["SUCCESS"]
        assert out == ["field2", "beta"]

    def test_single_field_with_custom_delimiter(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ):
        """Extract single field with custom delimiter."""
        file_path = write_lines(
            tmp_path,
            "passwd.txt",
            ["root:x:0:0:root:/root:/bin/bash", "user:x:1000:1000:user:/home/user:/bin/sh"],
        )

        code = main(["--field", "1", "--delimiter", ":", str(file_path)])
        out = capsys.readouterr().out.strip().splitlines()

        assert code == RETURN_CODES["SUCCESS"]
        assert out == ["root", "user"]

    def test_multiple_fields_list(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ):
        """Extract multiple specific fields (list)."""
        file_path = write_lines(
            tmp_path,
            "data.csv",
            ["a,b,c,d", "1,2,3,4", "5,6,7,8"],
        )

        code = main(["--field", "1,3", "--delimiter", ",", str(file_path)])
        out = capsys.readouterr().out.strip().splitlines()

        assert code == RETURN_CODES["SUCCESS"]
        assert out == ["a,c", "1,3", "5,7"]

    def test_field_range(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ):
        """Extract range of fields."""
        file_path = write_lines(
            tmp_path,
            "data.tsv",
            ["a\tb\tc\td\te", "1\t2\t3\t4\t5"],
        )

        code = main(["--field", "2-4", str(file_path)])
        out = capsys.readouterr().out.strip().splitlines()

        assert code == RETURN_CODES["SUCCESS"]
        assert out == ["b\tc\td", "2\t3\t4"]

    def test_field_range_open_ended(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ):
        """Extract from field N to end."""
        file_path = write_lines(
            tmp_path,
            "data.txt",
            ["a\tb\tc\td", "1\t2\t3\t4"],
        )

        code = main(["--field", "2-", str(file_path)])
        out = capsys.readouterr().out.strip().splitlines()

        assert code == RETURN_CODES["SUCCESS"]
        assert out == ["b\tc\td", "2\t3\t4"]

    def test_field_range_from_start(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ):
        """Extract from start to field N."""
        file_path = write_lines(
            tmp_path,
            "data.txt",
            ["a\tb\tc\td", "1\t2\t3\t4"],
        )

        code = main(["--field", "-3", str(file_path)])
        out = capsys.readouterr().out.strip().splitlines()

        assert code == RETURN_CODES["SUCCESS"]
        assert out == ["a\tb\tc", "1\t2\t3"]

    def test_missing_field_returns_empty_string(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ):
        """Line with fewer fields returns empty string for missing fields."""
        file_path = write_lines(
            tmp_path,
            "data.txt",
            ["a\tb\tc", "1\t2"],
        )

        code = main(["--field", "3", str(file_path)])
        out = capsys.readouterr().out.splitlines()

        assert code == RETURN_CODES["SUCCESS"]
        # Both lines are output (first has 'c', second is empty)
        assert len(out) == 2
        assert out[0] == "c"
        assert out[1] == ""

    def test_field_first_only_flag(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ):
        """With -s flag, suppress lines without delimiter."""
        file_path = write_lines(
            tmp_path,
            "data.txt",
            ["a\tb\tc", "no delimiter here", "1\t2\t3"],
        )

        code = main(["--field", "2", "--only-delimited", str(file_path)])
        out = capsys.readouterr().out.strip().splitlines()

        assert code == RETURN_CODES["SUCCESS"]
        assert out == ["b", "2"]


class TestCharMode:
    """Tests for -c (character extraction) mode."""

    def test_single_character(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ):
        """Extract single character position."""
        file_path = write_lines(
            tmp_path,
            "data.txt",
            ["hello", "world"],
        )

        code = main(["--characters", "2", str(file_path)])
        out = capsys.readouterr().out.strip().splitlines()

        assert code == RETURN_CODES["SUCCESS"]
        assert out == ["e", "o"]

    def test_multiple_characters_list(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ):
        """Extract multiple specific character positions."""
        file_path = write_lines(
            tmp_path,
            "data.txt",
            ["hello", "world"],
        )

        code = main(["--characters", "1,3,5", str(file_path)])
        out = capsys.readouterr().out.strip().splitlines()

        assert code == RETURN_CODES["SUCCESS"]
        assert out == ["hlo", "wrd"]

    def test_character_range(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ):
        """Extract range of character positions."""
        file_path = write_lines(
            tmp_path,
            "data.txt",
            ["hello world", "foo bar baz"],
        )

        code = main(["--characters", "1-5", str(file_path)])
        out = capsys.readouterr().out.strip().splitlines()

        assert code == RETURN_CODES["SUCCESS"]
        assert out == ["hello", "foo b"]

    def test_character_range_open_ended(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ):
        """Extract from character N to end."""
        file_path = write_lines(
            tmp_path,
            "data.txt",
            ["hello", "world"],
        )

        code = main(["--characters", "2-", str(file_path)])
        out = capsys.readouterr().out.strip().splitlines()

        assert code == RETURN_CODES["SUCCESS"]
        assert out == ["ello", "orld"]

    def test_character_range_from_start(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ):
        """Extract from start to character N."""
        file_path = write_lines(
            tmp_path,
            "data.txt",
            ["hello", "world"],
        )

        code = main(["--characters", "-3", str(file_path)])
        out = capsys.readouterr().out.strip().splitlines()

        assert code == RETURN_CODES["SUCCESS"]
        assert out == ["hel", "wor"]

    def test_character_out_of_bounds(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ):
        """Character position beyond line length returns shorter line."""
        file_path = write_lines(
            tmp_path,
            "data.txt",
            ["hi", "world"],
        )

        code = main(["--characters", "1-10", str(file_path)])
        out = capsys.readouterr().out.strip().splitlines()

        assert code == RETURN_CODES["SUCCESS"]
        assert out == ["hi", "world"]


class TestStdinAndFiles:
    """Tests for input handling."""

    def test_stdin_by_default(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ):
        """Read from stdin when no file specified."""
        monkeypatch.setattr("sys.stdin", io.StringIO("a\tb\tc\n1\t2\t3\n"))

        code = main(["--field", "2"])
        out = capsys.readouterr().out.strip().splitlines()

        assert code == RETURN_CODES["SUCCESS"]
        assert out == ["b", "2"]

    def test_multiple_files(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ):
        """Process multiple input files."""
        file1 = write_lines(tmp_path, "file1.txt", ["a\tb\tc", "1\t2\t3"])
        file2 = write_lines(tmp_path, "file2.txt", ["x\ty\tz", "7\t8\t9"])

        code = main(["--field", "2", str(file1), str(file2)])
        out = capsys.readouterr().out.strip().splitlines()

        assert code == RETURN_CODES["SUCCESS"]
        assert out == ["b", "2", "y", "8"]

    def test_missing_file_returns_error(
        self, capsys: pytest.CaptureFixture[str], caplog: pytest.LogCaptureFixture
    ):
        """Missing file returns error code."""
        code = main(["--field", "1", "nonexistent.txt"])

        assert code == RETURN_CODES["ERROR"]


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_no_mode_specified(self):
        """Error when neither -f nor -c specified."""
        code = main(["nonexistent.txt"])

        assert code == RETURN_CODES["ERROR"]

    def test_empty_file(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ):
        """Empty file returns success with no output."""
        file_path = write_lines(tmp_path, "empty.txt", [])

        code = main(["--field", "1", str(file_path)])
        out = capsys.readouterr().out

        assert code == RETURN_CODES["SUCCESS"]
        # write_lines adds a trailing newline, so even empty list becomes '\n'
        assert out.strip() == ""

    def test_field_zero_is_error(self):
        """Field numbering starts at 1; 0 is invalid."""
        code = main(["--field", "0", "dummy.txt"])

        assert code == RETURN_CODES["ERROR"]

    def test_character_zero_is_error(self):
        """Character numbering starts at 1; 0 is invalid."""
        code = main(["--characters", "0", "dummy.txt"])

        assert code == RETURN_CODES["ERROR"]

    def test_both_field_and_character_modes_error(self):
        """Cannot specify both -f and -c."""
        code = main(["--field", "1", "--characters", "1", "dummy.txt"])

        assert code == RETURN_CODES["ERROR"]

    def test_line_with_only_delimiter(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ):
        """Line that is only delimiter(s)."""
        file_path = write_lines(
            tmp_path,
            "data.txt",
            ["a\tb\tc", "\t\t", "1\t2\t3"],
        )

        code = main(["--field", "2", str(file_path)])
        out = capsys.readouterr().out.strip().splitlines()

        assert code == RETURN_CODES["SUCCESS"]
        assert out == ["b", "", "2"]
