"""grep.py implements the 'grep' command for the recut tool.

This command searches for a specified pattern in the input data and outputs lines that match the pattern.

It supports options for case sensitivity and whole word matching.

Usage:
    grep.py [OPTIONS] PATTERN
"""

import argparse
import logging
import sys
import re
from glob import glob
from contextlib import ExitStack
from collections import deque
from typing import List, Set, TextIO

RETURN_CODES = {
    "SUCCESS": 0,
    "ERROR": 1,
    "INVALID_REGEX": 2,
    "NO_MATCH": 3,
}


def create_parser():
    """Create the argument parser for the grep command."""
    parser = argparse.ArgumentParser(
        description="Search for PATTERN in input data and output matching lines.",
    )
    parser.add_argument(
        "pattern",
        type=str,
        help="The pattern to search for in the input data.",
    )
    parser.add_argument(
        "-i",
        "--ignore-case",
        action="store_true",
        help="Perform case-insensitive matching.",
    )
    parser.add_argument(
        "-w",
        "--word",
        action="store_true",
        help="Match whole words only.",
    )
    parser.add_argument(
        "-v",
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set the logging level.",
    )
    parser.add_argument(
        "input_files",
        nargs="*",
        default=None,
        help=(
            "One or more input files or glob patterns (default: standard input). Use '-' for stdin."
        ),
    )
    return parser


def _expand_inputs(inputs: list[str] | None) -> List[str]:
    """Expand glob patterns while preserving '-' and literals when no matches."""
    if not inputs:
        return ["-"]

    expanded: List[str] = []
    for item in inputs:
        if item == "-":
            expanded.append(item)
            continue

        matches = glob(item)
        if matches:
            expanded.extend(matches)
        else:
            expanded.append(item)

    return expanded


def main(args: list[str] | None = None) -> int:
    """Main function to execute the grep command."""
    parser = create_parser()
    if args is None:
        # Get arguments from command line, excluding the script name
        args = sys.argv[1:]

    parsed_args = parser.parse_args(args)
    # Configure logging
    log = logging.getLogger(__name__)
    logging.basicConfig(
        level=parsed_args.log_level,
        stream=sys.stderr,
        format="%(levelname)s: %(message)s",
    )

    # Compile the regex pattern based on the provided arguments
    log.debug("Compiling regex pattern: %s", parsed_args.pattern)
    flags = re.IGNORECASE if parsed_args.ignore_case else 0
    # Add word boundaries (\b in regex) if the --word option is specified
    pattern = (
        r"\b" + re.escape(parsed_args.pattern) + r"\b"
        if parsed_args.word
        else re.escape(parsed_args.pattern)
    )
    try:
        regex = re.compile(pattern, flags)
    except re.error as e:
        log.error("Error compiling regex pattern: %s", e)
        return RETURN_CODES["INVALID_REGEX"]

    # Read input and search for the pattern
    matches = 0
    targets = _expand_inputs(parsed_args.input_files)
    with ExitStack() as stack:
        for target in targets:
            try:
                if target == "-":
                    # Use stdin without closing it
                    input_stream: TextIO = sys.stdin
                else:
                    # Open the specified input file and ensure closure
                    input_stream = stack.enter_context(open(target, "r"))
            except IOError as e:
                log.error("Error opening input file %s: %s", target, e)
                return RETURN_CODES["ERROR"]

            for line in input_stream:
                if regex.search(line):
                    # Output matching line
                    matches += 1
                    print(line.strip())

    # Return non-zero code if no matches were found (for scripting purposes)
    if matches == 0:
        log.error("No matches found for pattern: %s", parsed_args.pattern)
        return RETURN_CODES["NO_MATCH"]

    # Successful completion
    log.debug("Exiting successfully, found %d matches.", matches)
    return RETURN_CODES["SUCCESS"]


if __name__ == "__main__":
    sys.exit(main())
