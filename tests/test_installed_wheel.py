"""Installed-wheel smoke tests for greppy and cutty (no src on PYTHONPATH)."""

import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def installed_cli(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """Build a wheel from the project tree and install into an isolated venv."""
    work = tmp_path_factory.mktemp("wheel-smoke")
    dist = work / "dist"
    dist.mkdir()
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(dist)],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    wheels = list(dist.glob("recut-*.whl"))
    assert len(wheels) == 1
    wheel = wheels[0]

    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
    assert any(n.startswith("recut/commands/") for n in names), names

    venv_dir = work / "venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
    pip = venv_dir / "bin" / "pip"
    subprocess.run(
        [str(pip), "install", "--no-deps", str(wheel)],
        check=True,
        capture_output=True,
        text=True,
    )
    bindir = venv_dir / "bin"
    return {
        "greppy": bindir / "greppy",
        "cutty": bindir / "cutty",
        "wheel": wheel,
    }


def run_cli(
    executable: Path,
    args: list[str],
    *,
    input_text: str | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    return subprocess.run(
        [str(executable), *args],
        input=input_text,
        text=True,
        capture_output=True,
        cwd=cwd or Path("/tmp"),
        env=env,
        check=False,
    )


def test_wheel_contains_commands_package(installed_cli: dict[str, Path]) -> None:
    with zipfile.ZipFile(installed_cli["wheel"]) as archive:
        assert "recut/commands/grep.py" in archive.namelist()
        assert "recut/commands/cut.py" in archive.namelist()


def test_greppy_help(installed_cli: dict[str, Path]) -> None:
    result = run_cli(installed_cli["greppy"], ["--help"])
    assert result.returncode == 0
    assert "pattern" in result.stdout.lower()


def test_cutty_help(installed_cli: dict[str, Path]) -> None:
    result = run_cli(installed_cli["cutty"], ["--help"])
    assert result.returncode == 0
    assert "--field" in result.stdout or "-f" in result.stdout


def test_greppy_file_match_and_no_match_exit_codes(
    installed_cli: dict[str, Path], tmp_path: Path
) -> None:
    data = tmp_path / "lines.txt"
    data.write_text("alpha\nneedle here\nbeta\n")

    hit = run_cli(installed_cli["greppy"], ["needle", str(data)])
    assert hit.returncode == 0
    assert "needle here" in hit.stdout

    miss = run_cli(installed_cli["greppy"], ["zzz", str(data)])
    assert miss.returncode == 3
    assert miss.stdout.strip() == ""


def test_greppy_invalid_regex_exit_code(installed_cli: dict[str, Path]) -> None:
    result = run_cli(installed_cli["greppy"], ["[unclosed"])
    assert result.returncode == 2


def test_greppy_stdin_and_line_number(installed_cli: dict[str, Path]) -> None:
    result = run_cli(installed_cli["greppy"], ["-n", "two"], input_text="one\ntwo\n")
    assert result.returncode == 0
    assert "2:two" in result.stdout


def test_cutty_field_from_file(installed_cli: dict[str, Path], tmp_path: Path) -> None:
    data = tmp_path / "tsv.txt"
    data.write_text("a\tb\tc\n1\t2\t3\n")

    result = run_cli(installed_cli["cutty"], ["-f", "2", str(data)])
    assert result.returncode == 0
    assert result.stdout.strip().splitlines() == ["b", "2"]


def test_cutty_stdin_field(installed_cli: dict[str, Path]) -> None:
    result = run_cli(
        installed_cli["cutty"], ["-f", "1", "-d", ","], input_text="x,y,z\n"
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "x"


def test_greppy_pipe_to_cutty_subprocess(
    installed_cli: dict[str, Path], tmp_path: Path
) -> None:
    """Regression: greppy stdout can feed cutty in a shell-style pipeline."""
    data = tmp_path / "records.txt"
    data.write_text("keep\tcol2\nskip\tcol2\n")

    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    grep = subprocess.Popen(
        [str(installed_cli["greppy"]), "keep", str(data)],
        stdout=subprocess.PIPE,
        text=True,
        cwd=tmp_path,
        env=env,
    )
    cut = subprocess.run(
        [str(installed_cli["cutty"]), "-f", "2"],
        stdin=grep.stdout,
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
        check=False,
    )
    assert grep.wait() == 0
    assert cut.returncode == 0
    assert cut.stdout.strip() == "col2"


def test_greppy_usage_error_exit_code(installed_cli: dict[str, Path]) -> None:
    missing_pattern = run_cli(installed_cli["greppy"], [])
    assert missing_pattern.returncode == 2
    assert "usage:" in missing_pattern.stderr

    unknown_option = run_cli(installed_cli["greppy"], ["--bogus", "x"])
    assert unknown_option.returncode == 2


def test_missing_input_file_exit_code(installed_cli: dict[str, Path]) -> None:
    for name, args in (("greppy", ["x"]), ("cutty", ["-f", "1"])):
        result = run_cli(installed_cli[name], [*args, "/nonexistent/recut-input"])
        assert result.returncode == 1, name
        assert "ERROR" in result.stderr


def test_cutty_invalid_arguments_exit_code(installed_cli: dict[str, Path]) -> None:
    for args in ([], ["-f", "0"], ["-f", "1", "-c", "1"]):
        result = run_cli(installed_cli["cutty"], args, input_text="a\n")
        assert result.returncode == 1, args


def test_output_file_help_does_not_claim_it_works(
    installed_cli: dict[str, Path], tmp_path: Path
) -> None:
    for name in ("greppy", "cutty"):
        help_text = " ".join(run_cli(installed_cli[name], ["--help"]).stdout.split())
        assert "currently ignored" in help_text, name

    target = tmp_path / "out.txt"
    result = run_cli(
        installed_cli["cutty"],
        ["-f", "1", "--output-file", str(target)],
        input_text="b\n",
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "b"
    assert not target.exists()
