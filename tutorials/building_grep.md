# Building a Tiny `grep` in Python

This tutorial walks through creating the current `grep` command in `recut`, starting from an empty file and ending with a tested CLI tool.

To skip ahead and see the code, check out the [repo](https://github.com/McIndi/recut).

## 0) Prereqs
- Python 3.10+
- `pip install -e .[dev]` to get pytest and tooling
- A shell where `python -m pytest` works

## 1) Skeleton and parser
Create `src/recut/commands/grep.py` and start with an argument parser:

```python
import argparse

RETURN_CODES = {"SUCCESS": 0, "ERROR": 1, "INVALID_REGEX": 2, "NO_MATCH": 3}

def create_parser():
    parser = argparse.ArgumentParser(
        description="Search for PATTERN in input data and output matching lines.",
    )
    parser.add_argument("pattern", type=str, help="The pattern to search for.")
    parser.add_argument("input_files", nargs="*", default=None, help="Files or '-' for stdin.")
    parser.add_argument("-i", "--ignore-case", action="store_true", help="Case-insensitive match.")
    parser.add_argument("-w", "--word", action="store_true", help="Match whole words only.")
    parser.add_argument(
        "-v",
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set logging level.",
    )
    return parser
```

## 2) Handle input targets (files, globs, stdin)
Use `glob.glob` to expand patterns but keep literals and the special `-` stdin marker:

```python
from glob import glob
from typing import List

def _expand_inputs(inputs: list[str] | None) -> List[str]:
    if not inputs:
        return ["-"]

    expanded: List[str] = []
    for item in inputs:
        if item == "-":
            expanded.append(item)
            continue

        matches = glob(item)
        expanded.extend(matches or [item])
    return expanded
```

## 3) Build the regex
Compile the pattern as a regex; add word boundaries when `-w` is set and optional `re.IGNORECASE`:

```python
import re

def compile_regex(pattern: str, *, whole_word: bool, ignore_case: bool) -> re.Pattern[str]:
    flags = re.IGNORECASE if ignore_case else 0
    text = rf"\b{pattern}\b" if whole_word else pattern
    return re.compile(text, flags)
```

## 4) Stream lines and search
Use `ExitStack` to open many files safely and support stdin (`-`). Strip trailing newlines before printing matches:

```python
import logging
import sys
from contextlib import ExitStack
from typing import TextIO

def search(pattern: re.Pattern[str], targets: list[str]) -> int:
    matches = 0
    with ExitStack() as stack:
        for target in targets:
            try:
                stream: TextIO = sys.stdin if target == "-" else stack.enter_context(open(target, "r"))
            except IOError as e:
                logging.error("Error opening input file %s: %s", target, e)
                return RETURN_CODES["ERROR"]

            for line in stream:
                if pattern.search(line):
                    matches += 1
                    print(line.strip())
    return matches
```

## 5) Wire up `main`
Put it together: parse args, configure logging, compile the regex, expand inputs, run the search, and map outcomes to return codes.

```python
def main(args: list[str] | None = None) -> int:
    parser = create_parser()
    args = sys.argv[1:] if args is None else args
    parsed = parser.parse_args(args)

    logging.basicConfig(level=parsed.log_level, stream=sys.stderr, format="%(levelname)s: %(message)s")

    try:
        regex = compile_regex(parsed.pattern, whole_word=parsed.word, ignore_case=parsed.ignore_case)
    except re.error as exc:
        logging.error("Error compiling regex pattern: %s", exc)
        return RETURN_CODES["INVALID_REGEX"]

    targets = _expand_inputs(parsed.input_files)
    matches = search(regex, targets)
    if matches == RETURN_CODES["ERROR"]:
        return RETURN_CODES["ERROR"]
    if matches == 0:
        logging.error("No matches found for pattern: %s", parsed.pattern)
        return RETURN_CODES["NO_MATCH"]
    return RETURN_CODES["SUCCESS"]
```


## 6) Add an entry point
Expose the command in `pyproject.toml` so users can run `greppy` after installation:

```toml
[project.scripts]
greppy = "recut.commands.grep:main"
```

## 7) Test it
Create `tests/test_grep.py` and cover stdin, file input, globs, word boundaries, missing files, and the error codes. Run:

```bash
python -m pytest
```

## 8) Try it manually
- `python -m recut.commands.grep hello sample.txt`
- `cat sample.txt | greppy -i hello -`
- `greppy -w cat *.log`

## 9) Extend
Ideas to practice further:
- Add `-n` for line numbers or `-c` for counts
- Support inverted matches (`-v` in POSIX `grep`)
- Add colorized output for terminals

You now have a working, tested `grep` reimplementation and a roadmap for enhancements.

Stay tuned for the next installment of our Posix In Python series where we update grep.py to support a bunch of options that we have come to expect from grep.

Go ahead and check out the [repo](https://github.com/McIndi/recut)
