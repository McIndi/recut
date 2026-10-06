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


# --- 0.1.1: non-UTF-8 input (issue #3) and closed output pipes (issue #4) ---

LATIN1_LINES = b"caf\xe9 hello\nplain hello\nna\xefve other\n"

# Python's own stdin decoding depends on the environment: C and C.UTF-8
# locales use "surrogateescape", while a UTF-8 locale such as en_US.UTF-8 is
# strict. PYTHONIOENCODING=utf-8:strict forces the strict case anywhere.
STDIN_ENVIRONMENTS = pytest.mark.parametrize(
    "stdin_env",
    [
        {"LC_ALL": "C"},
        {"LC_ALL": "C.UTF-8"},
        {"PYTHONIOENCODING": "utf-8:strict"},
        {"LC_ALL": "C", "PYTHONUTF8": "0"},
    ],
    ids=["C", "C.UTF-8", "strict-utf8", "C-ascii"],
)


def run_cli_bytes(
    executable: Path,
    args: list[str],
    *,
    input_bytes: bytes | None = None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[bytes]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.update(extra_env or {})
    return subprocess.run(
        [str(executable), *args],
        input=input_bytes,
        capture_output=True,
        cwd=Path("/tmp"),
        env=env,
        check=False,
    )


def test_greppy_latin1_file_passes_bytes_through(
    installed_cli: dict[str, Path], tmp_path: Path
) -> None:
    data = tmp_path / "latin1.txt"
    data.write_bytes(LATIN1_LINES)

    hit = run_cli_bytes(installed_cli["greppy"], ["hello", str(data)])
    assert hit.returncode == 0
    assert hit.stdout == b"caf\xe9 hello\nplain hello\n"
    assert hit.stderr == b""

    numbered = run_cli_bytes(installed_cli["greppy"], ["-n", "na.ve", str(data)])
    assert numbered.returncode == 0
    assert numbered.stdout == b"3:na\xefve other\n"

    for flag in ("-q", "-l"):
        result = run_cli_bytes(installed_cli["greppy"], [flag, "hello", str(data)])
        assert result.returncode == 0, flag
        assert result.stderr == b"", flag

    miss = run_cli_bytes(installed_cli["greppy"], ["zzz", str(data)])
    assert miss.returncode == 3
    assert miss.stdout == b""
    assert b"Traceback" not in miss.stderr


@STDIN_ENVIRONMENTS
def test_greppy_latin1_stdin_passes_bytes_through(
    installed_cli: dict[str, Path], stdin_env: dict[str, str]
) -> None:
    result = run_cli_bytes(
        installed_cli["greppy"],
        ["hello"],
        input_bytes=LATIN1_LINES,
        extra_env=stdin_env,
    )
    assert result.returncode == 0
    assert result.stdout == b"caf\xe9 hello\nplain hello\n"
    assert result.stderr == b""


def test_cutty_latin1_file_passes_bytes_through(
    installed_cli: dict[str, Path], tmp_path: Path
) -> None:
    data = tmp_path / "latin1.csv"
    data.write_bytes(b"caf\xe9,na\xefve\nplain,x\n")

    fields = run_cli_bytes(installed_cli["cutty"], ["-d", ",", "-f", "2", str(data)])
    assert fields.returncode == 0
    assert fields.stdout == b"na\xefve\nx\n"
    assert fields.stderr == b""

    chars = run_cli_bytes(installed_cli["cutty"], ["-c", "1-4", str(data)])
    assert chars.returncode == 0
    assert chars.stdout == b"caf\xe9\nplai\n"


@STDIN_ENVIRONMENTS
def test_cutty_latin1_stdin_passes_bytes_through(
    installed_cli: dict[str, Path], stdin_env: dict[str, str]
) -> None:
    result = run_cli_bytes(
        installed_cli["cutty"],
        ["-d", " ", "-f", "1"],
        input_bytes=LATIN1_LINES,
        extra_env=stdin_env,
    )
    assert result.returncode == 0
    assert result.stdout == b"caf\xe9\nplain\nna\xefve\n"
    assert result.stderr == b""


@pytest.mark.parametrize(
    ("name", "args", "line_suffix"),
    [("greppy", ["1"], ""), ("cutty", ["-f", "1"], "\tx")],
)
def test_pipe_into_head_exits_quietly_with_sigpipe_status(
    installed_cli: dict[str, Path],
    tmp_path: Path,
    name: str,
    args: list[str],
    line_suffix: str,
) -> None:
    """`tool | head -1` prints one line, nothing on stderr, shell status 141."""
    data = tmp_path / "many.txt"
    # Far more output than a pipe buffer holds, so the tool is still writing
    # when head exits.
    data.write_text("".join(f"{n}{line_suffix}\n" for n in range(1, 200001)))

    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    script = '"$@" | head -1; echo "status=${PIPESTATUS[0]},${PIPESTATUS[1]}"'
    result = subprocess.run(
        ["bash", "-c", script, "bash", str(installed_cli[name]), *args, str(data)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
        check=False,
    )
    assert result.stderr == ""
    assert result.stdout == "1\nstatus=141,0\n"
    assert result.returncode == 0


# --- Arguments and file names use the same codec as the data (review F1) ---

LEGACY_LOCALES = ("en_US.iso885915", "en_US.iso88591", "en_GB.iso885915")


def run_cli_argv_bytes(
    executable: Path, args: list[bytes], *, cwd: Path, env_extra: dict[str, str]
) -> subprocess.CompletedProcess[bytes]:
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env.pop("PYTHONIOENCODING", None)
    env.update(env_extra)
    return subprocess.run(
        [os.fsencode(executable), *args],
        capture_output=True,
        cwd=cwd,
        env=env,
        check=False,
    )


def _legacy_locale_env(installed_cli: dict[str, Path]) -> dict[str, str]:
    """Return env for an installed ISO-8859 locale, or skip with the reason."""
    python = installed_cli["greppy"].parent / "python"
    for name in LEGACY_LOCALES:
        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        env.update({"LC_ALL": name, "PYTHONUTF8": "0"})
        probe = subprocess.run(
            [str(python), "-c", "import sys; print(sys.getfilesystemencoding())"],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        if probe.stdout.strip().startswith("iso8859"):
            return {"LC_ALL": name, "PYTHONUTF8": "0"}
    pytest.skip(
        f"no ISO-8859 locale installed (tried {', '.join(LEGACY_LOCALES)}); "
        "the C/ASCII-locale form of this test still runs"
    )


# Each case: (tool, args, expected stdout). R is a raw non-ASCII byte string
# that appears in the data file, a file name and the arguments.
ARGV_CASES = {
    "cutty-delimiter": (
        "cutty",
        [b"-s", b"-d", b"R", b"-f", b"2", b"d.txt"],
        b"b\ny\n",
    ),
    "greppy-pattern": ("greppy", [b"xR", b"d.txt"], b"xRyRz\n"),
    "greppy-l-filename": ("greppy", [b"-l", b"x", b"fR.txt"], b"fR.txt\n"),
    "greppy-H-filename": ("greppy", [b"-H", b"x", b"fR.txt"], b"fR.txt:x\n"),
}


def _check_argv_case(
    installed_cli: dict[str, Path],
    tmp_path: Path,
    env: dict[str, str],
    raw: bytes,
    case: str,
) -> None:
    tool, args, expected = ARGV_CASES[case]
    (tmp_path / "d.txt").write_bytes(b"aRbRc\nxRyRz\nplain\n".replace(b"R", raw))
    (tmp_path / os.fsdecode(b"fR.txt".replace(b"R", raw))).write_bytes(b"x\n")

    result = run_cli_argv_bytes(
        installed_cli[tool],
        [arg.replace(b"R", raw) for arg in args],
        cwd=tmp_path,
        env_extra=env,
    )
    assert result.stderr == b""
    assert result.returncode == 0
    assert result.stdout == expected.replace(b"R", raw)


@pytest.mark.parametrize("case", list(ARGV_CASES))
def test_legacy_locale_arguments_match_input_bytes(
    installed_cli: dict[str, Path], tmp_path: Path, case: str
) -> None:
    """ISO-8859 locale: raw-byte args and file names behave as in 0.1.0.

    Python decodes argv with ISO-8859-15 here; 0.1.1 at 1efeaa0 forced data
    to UTF-8, so the \\xe9 delimiter and pattern stopped matching and
    printed file names were re-encoded as UTF-8.
    """
    env = _legacy_locale_env(installed_cli)
    _check_argv_case(installed_cli, tmp_path, env, b"\xe9", case)


@pytest.mark.parametrize("case", list(ARGV_CASES))
def test_ascii_locale_arguments_match_input_bytes(
    installed_cli: dict[str, Path], tmp_path: Path, case: str
) -> None:
    """C locale without UTF-8 mode: Python decodes argv as ASCII.

    Runs in any environment, including the CI container. UTF-8 bytes in the
    arguments show a mismatch between the argv and data codecs (the
    delimiter and pattern cases); file names round-trip in either case.
    """
    env = {"LC_ALL": "C", "PYTHONUTF8": "0"}
    _check_argv_case(installed_cli, tmp_path, env, b"\xc3\xa9", case)
