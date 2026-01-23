"""cut.py implements the 'cut' command for the recut tool.

This command extracts columns or characters from input data based on field or character positions.

It supports field-based extraction with custom delimiters and character-based extraction.

Usage:
    cut.py [OPTIONS] [FILES...]
"""

import argparse
import logging
import sys
from typing import List

from recut.core import create_file_based_parser, file_input_handler

RETURN_CODES = {
    "SUCCESS": 0,
    "ERROR": 1,
    "INVALID_INPUT": 2,
}


def create_parser():
    """Create the argument parser for the cut command."""
    parser = create_file_based_parser(
        description=__doc__,
    )

    # Mode selection (mutually exclusive)
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "-f",
        "--field",
        type=str,
        help="Extract these fields (comma-separated or ranges like 1,3,5-7)",
    )
    mode_group.add_argument(
        "-c",
        "--characters",
        type=str,
        help="Extract these character positions (comma-separated or ranges like 1,3,5-7)",
    )

    # Delimiter and options
    parser.add_argument(
        "-d",
        "--delimiter",
        type=str,
        default="\t",
        help="Field delimiter (default: tab)",
    )
    parser.add_argument(
        "-s",
        "--only-delimited",
        action="store_true",
        help="Suppress lines without the delimiter (field mode only).",
    )
    
    # Input files
    parser.add_argument(
        "input_files",
        nargs="*",
        default=None,
        help="Input files (default: standard input). Use '-' for stdin.",
    )

    return parser


def parse_field_spec(spec: str) -> tuple[List[int], bool]:
    """Parse field specification like '1,3,5-7,10-' into a list of field indices (1-based).
    
    Returns: (field_indices, has_open_ended_range)
    """
    fields = set()
    parts = spec.split(",")
    has_open_ended = False

    for part in parts:
        part = part.strip()
        if "-" in part:
            range_parts = part.split("-")
            if len(range_parts) != 2:
                raise ValueError(f"Invalid range: {part}")

            start_str, end_str = range_parts
            start = int(start_str) if start_str else 1
            end = int(end_str) if end_str else None

            if start <= 0:
                raise ValueError(f"Field numbers must be >= 1")

            if end is None:
                # Open-ended range: 5- means from 5 onwards
                has_open_ended = True
                # Return early with sentinel value
                return (sorted(fields | {start}), True)
            elif start > end:
                raise ValueError(f"Invalid range: {part}")
            else:
                fields.update(range(start, end + 1))
        else:
            field_num = int(part)
            if field_num <= 0:
                raise ValueError(f"Field numbers must be >= 1")
            fields.add(field_num)

    return (sorted(fields), has_open_ended)


def extract_fields(line: str, field_indices: List[int], delimiter: str, open_ended: bool) -> str:
    """Extract specified fields from a delimited line."""
    fields = line.split(delimiter)
    
    if open_ended:
        # Get from the first field number onwards
        start_idx = field_indices[0] - 1
        return delimiter.join(fields[start_idx:])
    
    result = []
    for idx in field_indices:
        field_num = idx - 1  # Convert 1-based to 0-based
        if field_num < len(fields):
            result.append(fields[field_num])
        else:
            result.append("")

    return delimiter.join(result)


def extract_characters(line: str, char_indices: List[int], open_ended: bool) -> str:
    """Extract specified characters from a line."""
    if open_ended:
        # Get from the first character onwards
        start_idx = char_indices[0] - 1
        return line[start_idx:]
    
    result = []
    for idx in char_indices:
        char_num = idx - 1  # Convert 1-based to 0-based
        if char_num < len(line):
            result.append(line[char_num])

    return "".join(result)


def main(args: list[str] | None = None) -> int:
    """Main function to execute the cut command."""
    parser = create_parser()
    if args is None:
        args = sys.argv[1:]

    try:
        parsed_args = parser.parse_args(args)
    except SystemExit as e:
        # Catch argparse exits and convert to error code
        if e.code != 0:
            return RETURN_CODES["ERROR"]
        return RETURN_CODES["SUCCESS"]

    # Configure logging
    log = logging.getLogger(__name__)
    logging.basicConfig(
        level=parsed_args.log_level,
        stream=sys.stderr,
        format="%(levelname)s: %(message)s",
    )

    # Parse field or character specification
    try:
        if parsed_args.field:
            indices, open_ended = parse_field_spec(parsed_args.field)
            mode = "field"
        else:
            indices, open_ended = parse_field_spec(parsed_args.characters)
            mode = "char"
    except ValueError as e:
        log.error("Invalid specification: %s", e)
        return RETURN_CODES["ERROR"]

    # Process input
    try:
        for line, source in file_input_handler(parsed_args.input_files):
            # Skip lines without delimiter in field mode with -s flag
            if mode == "field" and parsed_args.only_delimited:
                if parsed_args.delimiter not in line:
                    continue

            # Extract and output
            if mode == "field":
                output = extract_fields(line, indices, parsed_args.delimiter, open_ended)
            else:  # mode == "char"
                output = extract_characters(line, indices, open_ended)

            print(output)

    except IOError as e:
        log.error("%s", e)
        return RETURN_CODES["ERROR"]
    except Exception as e:
        log.error("Error processing input: %s", e)
        return RETURN_CODES["ERROR"]

    log.debug("Exiting successfully.")
    return RETURN_CODES["SUCCESS"]


if __name__ == "__main__":
    sys.exit(main())
