"""core.py provides shared utilities for recut commands.

This module contains common functionality used across multiple recut commands,
including argument parsing, input file handling and console-script setup.
"""

import argparse
import io
import signal
import sys
from contextlib import ExitStack
from typing import Callable, Generator, List, Optional, TextIO

# Input and output are decoded/encoded as UTF-8 with "surrogateescape": bytes
# that are not valid UTF-8 (for example Latin-1 text) become lone surrogates on
# the way in and are written back as the same bytes on the way out, so they
# pass through unchanged instead of raising UnicodeDecodeError.
STREAM_ENCODING = "utf-8"
STREAM_ERRORS = "surrogateescape"


def configure_standard_streams() -> None:
    """Make stdin and stdout pass non-UTF-8 bytes through unchanged.

    Streams that cannot be reconfigured (for example test doubles) are left
    as they are.
    """
    for stream in (sys.stdin, sys.stdout):
        if not isinstance(stream, io.TextIOWrapper):
            continue
        try:
            stream.reconfigure(encoding=STREAM_ENCODING, errors=STREAM_ERRORS)
        except (ValueError, OSError):
            # ValueError: data was already read; keep the current setup.
            pass


def restore_default_sigpipe() -> None:
    """Let a closed output pipe end the process quietly, as grep and cut do.

    Python ignores SIGPIPE at startup, so writing to a pipe whose reader has
    exited (for example ``| head -1``) raises BrokenPipeError and prints an
    "Exception ignored" message at shutdown. Restoring the default action makes
    the process end by SIGPIPE instead: no message, and shell status 141.
    No-op on platforms without SIGPIPE (Windows).
    """
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)


def run_console_script(main: Callable[[], int]) -> int:
    """Prepare process-wide state for a console script, then run ``main``."""
    restore_default_sigpipe()
    configure_standard_streams()
    return main()


def create_file_based_parser(
    description: str,
    prog: Optional[str] = None,
) -> argparse.ArgumentParser:
    """Create an argument parser with standard file-based command arguments.

    This parser includes optional arguments commonly used by file-processing
    commands in recut, such as output file handling and logging configuration.

    Note: Commands that need input_files must add it themselves as a positional
    argument (typically variadic, nargs="*") after any other positional arguments.

    Args:
        description: The description for the argument parser (typically __doc__).
        prog: The program name for the parser (defaults to the script name).

    Returns:
        An ArgumentParser configured with output_file and log_level.
    """
    parser = argparse.ArgumentParser(
        description=description,
        prog=prog,
    )

    parser.add_argument(
        "--output-file",
        type=str,
        default=None,
        help="Reserved; currently ignored. Output always goes to standard output.",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set the logging level.",
    )

    return parser


def file_input_handler(
    input_files: Optional[List[str]],
) -> Generator[tuple[str, str], None, None]:
    """Generator that safely iterates through lines of input files.

    This generator handles opening and closing files, yielding each line along
    with the source filename. It properly handles stdin and file closures
    using ExitStack.

    Args:
        input_files: A list of input file paths, or None/empty for stdin.
                     Use '-' to explicitly specify stdin.

    Yields:
        Tuples of (line, source_filename) for each line in the input files.
        Lines have trailing newlines removed. Files are read as UTF-8 with
        "surrogateescape", so invalid UTF-8 bytes do not raise; standard
        input uses whatever decoding sys.stdin has (see
        configure_standard_streams).
    """
    targets = input_files or ["-"]

    with ExitStack() as stack:
        for target in targets:
            try:
                if target == "-":
                    # Use stdin without closing it
                    input_stream: TextIO = sys.stdin
                    source_name = "<stdin>"
                else:
                    # Open the file and ensure it gets closed
                    input_stream = stack.enter_context(
                        open(
                            target,
                            "r",
                            encoding=STREAM_ENCODING,
                            errors=STREAM_ERRORS,
                        )
                    )
                    source_name = target
            except IOError as e:
                raise IOError(f"Error opening input file '{target}': {e}") from e

            for line in input_stream:
                # Remove trailing newline characters
                line = line.rstrip("\n\r")
                yield line, source_name
