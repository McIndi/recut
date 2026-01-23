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
from collections import deque
from typing import List, Set

from recut.core import create_file_based_parser, file_input_handler

RETURN_CODES = {
    "SUCCESS": 0,
    "ERROR": 1,
    "INVALID_REGEX": 2,
    "NO_MATCH": 3,
}


def create_parser():
    """Create the argument parser for the grep command."""
    parser = create_file_based_parser(
        description=__doc__,
    )
    
    # Add positional argument for pattern
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
        "-H",
        "--with-filename",
        action="store_true",
        help="Print the filename with each match.",
    )
    parser.add_argument(
        "-n",
        "--line-number",
        action="store_true",
        help="Print the line number with each match.",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress normal output; return exit code only.",
    )
    parser.add_argument(
        "-l",
        "--files-with-matches",
        action="store_true",
        help="Print only the filenames containing matches.",
    )
    
    # Input files
    parser.add_argument(
        "input_files",
        nargs="*",
        default=None,
        help="Input files (default: standard input). Use '-' for stdin.",
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
        r"\b" + parsed_args.pattern + r"\b"
        if parsed_args.word
        else parsed_args.pattern
    )
    try:
        regex = re.compile(pattern, flags)
    except re.error as e:
        log.error("Error compiling regex pattern: %s", e)
        return RETURN_CODES["INVALID_REGEX"]

    # Read input and search for the pattern
    matches = 0
    targets = _expand_inputs(parsed_args.input_files)
    files_with_matches: Set[str] = set()
    line_number = 0
    current_source = None
    
    try:
        for line, source in file_input_handler(targets):
            # Reset line number when we move to a new file
            if source != current_source:
                current_source = source
                line_number = 0
            
            line_number += 1
            if regex.search(line):
                matches += 1
                
                # Track files with matches for -l flag
                if parsed_args.files_with_matches:
                    files_with_matches.add(source)
                
                # Output matching line (unless in quiet or files-with-matches mode)
                if not parsed_args.quiet and not parsed_args.files_with_matches:
                    output = line.strip()
                    
                    # Prepend filename if -H is set
                    if parsed_args.with_filename:
                        output = f"{source}:{output}"
                    
                    # Prepend line number if -n is set
                    if parsed_args.line_number:
                        output = f"{line_number}:{output}"
                    
                    # Handle formatting with both -H and -n
                    if parsed_args.with_filename and parsed_args.line_number:
                        output = f"{source}:{line_number}:{line.strip()}"
                    
                    print(output)
    
    except IOError as e:
        log.error("%s", e)
        return RETURN_CODES["ERROR"]

    # Output filenames if -l flag was set
    if parsed_args.files_with_matches:
        for filename in sorted(files_with_matches):
            print(filename)
        if files_with_matches:
            matches = len(files_with_matches)

    # Return non-zero code if no matches were found (for scripting purposes)
    if matches == 0:
        log.error("No matches found for pattern: %s", parsed_args.pattern)
        return RETURN_CODES["NO_MATCH"]

    # Successful completion
    log.debug("Exiting successfully, found %d matches.", matches)
    return RETURN_CODES["SUCCESS"]


if __name__ == "__main__":
    sys.exit(main())
