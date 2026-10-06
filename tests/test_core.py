"""Unit tests for recut.core stdio, encoding and SIGPIPE helpers (issues #3, #4)."""

import io
import signal
from pathlib import Path

import pytest

from recut import core
from recut.commands import cut, grep

LATIN1 = b"caf\xe9 hello\nplain hello\n"


def binary_stream(data: bytes = b"") -> io.TextIOWrapper:
    """A strict UTF-8 text stream over bytes, like a non-UTF-8-mode sys.stdin."""
    return io.TextIOWrapper(io.BytesIO(data), encoding="utf-8", errors="strict")


def test_file_input_handler_passes_invalid_utf8_through(tmp_path: Path) -> None:
    data = tmp_path / "latin1.txt"
    data.write_bytes(LATIN1)

    lines = [line for line, _ in core.file_input_handler([str(data)])]

    assert lines == ["caf\udce9 hello", "plain hello"]
    encoded = [line.encode("utf-8", "surrogateescape") for line in lines]
    assert encoded == [b"caf\xe9 hello", b"plain hello"]


def test_configure_standard_streams_round_trips_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stdin = binary_stream(LATIN1)
    stdout = binary_stream()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)

    core.configure_standard_streams()
    stdout.write(stdin.read())
    stdout.flush()

    assert stdin.errors == stdout.errors == "surrogateescape"
    assert stdout.buffer.getvalue() == LATIN1  # type: ignore[attr-defined]


def test_configure_standard_streams_ignores_other_streams(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = io.StringIO("x\n")
    monkeypatch.setattr("sys.stdin", fake)
    monkeypatch.setattr("sys.stdout", fake)

    core.configure_standard_streams()  # must not raise

    assert fake.read() == "x\n"


def test_configure_standard_streams_keeps_stream_after_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stdin = binary_stream(b"one\ntwo\n")
    stdin.readline()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", io.StringIO())

    core.configure_standard_streams()  # ValueError from reconfigure is ignored

    assert stdin.readline() == "two\n"


@pytest.mark.skipif(not hasattr(signal, "SIGPIPE"), reason="POSIX only")
def test_restore_default_sigpipe() -> None:
    previous = signal.getsignal(signal.SIGPIPE)
    try:
        signal.signal(signal.SIGPIPE, signal.SIG_IGN)
        core.restore_default_sigpipe()
        assert signal.getsignal(signal.SIGPIPE) == signal.SIG_DFL
    finally:
        signal.signal(signal.SIGPIPE, previous)


def test_run_console_script_prepares_then_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(core, "restore_default_sigpipe", lambda: calls.append("sig"))
    monkeypatch.setattr(
        core, "configure_standard_streams", lambda: calls.append("stdio")
    )

    def fake_main() -> int:
        calls.append("main")
        return 3

    assert core.run_console_script(fake_main) == 3
    assert calls == ["sig", "stdio", "main"]


@pytest.mark.parametrize("module", [grep, cut])
def test_cli_entry_points_delegate_to_main(
    module, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = []
    monkeypatch.setattr(
        module, "run_console_script", lambda main: seen.append(main) or 7
    )

    assert module.cli() == 7
    assert seen == [module.main]


def test_greppy_main_latin1_file_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = tmp_path / "latin1.txt"
    data.write_bytes(LATIN1)
    stdout = io.TextIOWrapper(io.BytesIO(), encoding="utf-8", errors="surrogateescape")
    monkeypatch.setattr("sys.stdout", stdout)

    assert grep.main(["hello", str(data)]) == grep.RETURN_CODES["SUCCESS"]
    stdout.flush()
    assert stdout.buffer.getvalue() == LATIN1  # type: ignore[attr-defined]


def test_cutty_main_latin1_stdin_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    stdin = binary_stream(b"caf\xe9,na\xefve\nplain,x\n")
    stdout = binary_stream()
    monkeypatch.setattr("sys.stdin", stdin)
    monkeypatch.setattr("sys.stdout", stdout)
    core.configure_standard_streams()

    assert cut.main(["-d", ",", "-f", "2"]) == cut.RETURN_CODES["SUCCESS"]
    stdout.flush()
    assert stdout.buffer.getvalue() == b"na\xefve\nx\n"  # type: ignore[attr-defined]


def test_codec_follows_file_system_encoding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Data uses the same codec as argv and file names (review F1)."""
    monkeypatch.setattr("sys.getfilesystemencoding", lambda: "iso8859-15")
    stdout = binary_stream()
    monkeypatch.setattr("sys.stdin", binary_stream(b"x\xe9\n"))
    monkeypatch.setattr("sys.stdout", stdout)
    data = tmp_path / "latin1.txt"
    data.write_bytes(b"caf\xe9\n")

    core.configure_standard_streams()
    lines = [line for line, _ in core.file_input_handler([str(data), "-"])]

    assert core.stream_encoding() == "iso8859-15"
    assert stdout.encoding == "iso8859-15"
    assert lines == ["caf\xe9", "x\xe9"]
