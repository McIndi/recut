# Building `cut` with Test-Driven Development

This tutorial walks through building a `cut` command for `recut`, continuing from the `grep` implementation. `cut` extracts specific columns (fields) or character positions from input text—perfect for data processing pipelines.

We'll use **Test-Driven Development (TDD)** again: write tests first, implement to make them pass, then refactor.

If you want to see the final code, check out the [repo](https://github.com/McIndi/recut).

## 0) Motivation: Why Cut After Grep?

`grep` and `cut` form a natural pair in Unix pipelines:

```bash
# Find lines with "error", then extract the timestamp (field 2)
grep "error" logfile | cut -f2 -d' '
```

`cut` is simpler in scope than grep (no regex), but has more complex option handling and parsing logic. It teaches:
- String splitting and slicing
- Range parsing (e.g., `1-3`, `5-`, `-7`)
- Mode selection (fields vs characters)
- How to gracefully handle malformed input

## 1) Setup

Ensure you have:
- The existing `grep.py` command
- `pytest` and dev dependencies installed
- Familiarity with the TDD cycle from the grep tutorial

## 2) Red: Write Tests First

TDD starts with tests. Create `tests/test_cut.py` with comprehensive tests.

### Test Strategy

Organize tests by mode:
- **Field mode** (`-f`): Extract delimited columns
- **Character mode** (`-c`): Extract character positions
- **Stdin/File handling**: Input source tests
- **Edge cases**: Empty lines, missing fields, invalid args

### Single Field Test

```python
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
```

### Custom Delimiter Test

```python
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
```

### Range Parsing Tests

```python
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
```

Open-ended ranges:

```python
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
```

### Character Mode Tests

```python
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
```

**Red phase:** Run tests; they fail because `cut.py` doesn't exist yet.

```bash
python -m pytest tests/test_cut.py -v
```

## 3) Green: Create `cut.py`

Create `src/recut/commands/cut.py` with the basic structure:

```python
"""cut.py implements the 'cut' command for the recut tool."""

import argparse
import logging
import sys
from contextlib import ExitStack
from typing import List, TextIO

RETURN_CODES = {
    "SUCCESS": 0,
    "ERROR": 1,
    "INVALID_INPUT": 2,
}
```

### Define the Parser

```python
def create_parser():
    """Create the argument parser for the cut command."""
    parser = argparse.ArgumentParser(
        description="Extract columns or characters from input data.",
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
    parser.add_argument(
        "input_files",
        nargs="*",
        default=None,
        help="Input files (default: standard input).",
    )

    return parser
```

### Parse Range Specifications

The key challenge is parsing range specs like `1,3,5-7,10-`:

```python
def parse_field_spec(spec: str) -> tuple[List[int], bool]:
    """Parse field specification into a list of indices and open-ended flag."""
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
                # Open-ended range: return early
                has_open_ended = True
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
```

### Extraction Functions

```python
def extract_fields(line: str, field_indices: List[int], delimiter: str, open_ended: bool) -> str:
    """Extract specified fields from a delimited line."""
    fields = line.split(delimiter)
    
    if open_ended:
        # From first field index onwards
        start_idx = field_indices[0] - 1
        return delimiter.join(fields[start_idx:])
    
    result = []
    for idx in field_indices:
        field_num = idx - 1
        if field_num < len(fields):
            result.append(fields[field_num])
        else:
            result.append("")

    return delimiter.join(result)


def extract_characters(line: str, char_indices: List[int], open_ended: bool) -> str:
    """Extract specified characters from a line."""
    if open_ended:
        start_idx = char_indices[0] - 1
        return line[start_idx:]
    
    result = []
    for idx in char_indices:
        char_num = idx - 1
        if char_num < len(line):
            result.append(line[char_num])

    return "".join(result)
```

### Main Function

```python
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

    log = logging.getLogger(__name__)
    logging.basicConfig(
        level=parsed_args.log_level,
        stream=sys.stderr,
        format="%(levelname)s: %(message)s",
    )

    input_files = parsed_args.input_files or ["-"]

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

    try:
        with ExitStack() as stack:
            for target in input_files:
                try:
                    if target == "-":
                        input_stream: TextIO = sys.stdin
                    else:
                        input_stream = stack.enter_context(open(target, "r"))
                except IOError as e:
                    log.error("Error opening input file %s: %s", target, e)
                    return RETURN_CODES["ERROR"]

                for line in input_stream:
                    line = line.rstrip("\n\r")

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

    except Exception as e:
        log.error("Error processing input: %s", e)
        return RETURN_CODES["ERROR"]

    return RETURN_CODES["SUCCESS"]
```

**Green phase:** Run tests; they all pass.

```bash
python -m pytest tests/test_cut.py -v
```

All 23 tests should pass with 93% coverage.

## 4) Manual Testing

Test the command with real data:

```bash
# Field extraction with default tab delimiter
echo -e "name\tage\tcity\nAlice\t30\tNY\nBob\t25\tLA" | python -m recut.commands.cut --field 1,3
# Output:
# name	city
# Alice	NY
# Bob	LA

# Field extraction with custom delimiter (CSV)
echo "id,name,score,grade" > grades.csv
echo "1,Alice,95,A" >> grades.csv
echo "2,Bob,82,B" >> grades.csv
python -m recut.commands.cut --field 2,4 --delimiter ',' grades.csv
# Output:
# name,grade
# Alice,A
# Bob,B

# Range extraction
echo "one two three four five" | python -m recut.commands.cut --field 2-4 --delimiter ' '
# Output:
# two three four

# Character extraction
echo "Hello World" | python -m recut.commands.cut --characters 1-5
# Output:
# Hello

# Open-ended range
echo "a:b:c:d:e" | python -m recut.commands.cut --field 3- --delimiter ':'
# Output:
# c:d:e

# Only delimited lines
printf "a\tb\tc\nno delimiter\n1\t2\t3\n" | python -m recut.commands.cut --field 2 --only-delimited
# Output:
# b
# 2
```

## 5) Key Implementation Details

### 1-Based Indexing

Both POSIX `cut` and our implementation use 1-based indexing:
- Field 1 is the first field
- Character 1 is the first character

We convert to 0-based for Python list indexing.

### Open-Ended Ranges

Ranges like `2-` mean "from field 2 to the end of the line". We handle this by:
1. Detecting when `end` is `None` in `parse_field_spec`
2. Returning an `open_ended` flag
3. In extraction functions, using slice notation (`fields[start_idx:]`) when `open_ended=True`

### Missing Fields

When a line has fewer fields than requested, we output empty strings to maintain alignment:

```python
for idx in field_indices:
    if field_num < len(fields):
        result.append(fields[field_num])
    else:
        result.append("")  # Missing field becomes empty
```

### Character vs Field Mode

These are mutually exclusive via `argparse.add_mutually_exclusive_group(required=True)`, so users must specify exactly one.

## 6) Next Step: Refactoring

Look for opportunities to improve readability, efficiency, and maintainability without changing behavior.

We will explore refactoring in the next tutorial. Where we will make it much simpler to add new features in the future!

---

Check out the [repo](https://github.com/McIndi/recut) for the complete source.

Stay tuned for the next installment of our Posix In Python series where we will push forward with a big refactoring phase!
