"""core.py provides shared utilities for recut commands.

This module contains common functionality used across multiple recut commands,
including argument parsing and input file handling.
"""

import argparse
import sys
from contextlib import ExitStack
from typing import Generator, List, Optional, TextIO


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
        help="Output file (default: standard output).",
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
        Lines have trailing newlines removed.
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
                    input_stream = stack.enter_context(open(target, "r"))
                    source_name = target
            except IOError as e:
                raise IOError(f"Error opening input file '{target}': {e}") from e

            for line in input_stream:
                # Remove trailing newline characters
                line = line.rstrip("\n\r")
                yield line, source_name
