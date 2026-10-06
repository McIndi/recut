# Recut (REimagined Core Utils for Teaching)

This repo contains a reimagining of common posix/linux commands written in Python to:

* Explore how these CLI commands work under the hood
* Explore strengths and weaknesses of Python when implementing these utilities

There will be a Posix In Python blog series based on the work in this repo [here](https://www.mcindi.com/blog).

## Overview

Recut implements classic POSIX utilities in Python to serve as educational resources for understanding CLI command behavior and design patterns. Each implementation prioritizes clarity and learning value over performance.

## Features

- Python implementations of common POSIX commands
- Well-documented source code for learning
- Exploration of Python's strengths and limitations
- Blog articles explaining the implementations

## Installation

Clone the repository:

```bash
git clone https://github.com/McIndi/recut.git
cd recut
```

Install the package (editable install for development):

```bash
pip install -e .

# Or for development tooling and tests
pip install -e ".[dev]"
```

After installation, `greppy` and `cutty` are available on your `PATH`. Behavior described below is what the automated test suite exercises on Linux. CI runs Python 3.12; the package declares `requires-python >= 3.10`, but other versions are not part of the verified test matrix. This is not a claim of full POSIX or GNU compatibility on every platform. Neither command implements `--version` yet (deferred); use `python -m pip show recut` for the installed version.

## Running Tests

The project uses several tools for code quality and testing:

```bash
# Format code with Black
black .

# Check code formatting without changes
black --check .

# Security scanning with Bandit
bandit -r src

# Type checking with mypy
mypy src

# Run tests with pytest
pytest

# Installed-wheel smoke tests (builds a wheel and runs CLIs outside the source tree)
pytest tests/test_installed_wheel.py

# Run common checks together
black --check . && isort --check-only . && flake8 . && bandit -r src && mypy src && pytest
```

## Command reference

### greppy

Search input lines for a regular expression pattern.

**Syntax:** `greppy [OPTIONS] PATTERN [input_files...]`

| Option | Description |
|--------|-------------|
| `-i`, `--ignore-case` | Case-insensitive matching |
| `-w`, `--word` | Match whole words only |
| `-H`, `--with-filename` | Prefix each match with the source file name |
| `-n`, `--line-number` | Prefix each match with the line number |
| `-q`, `--quiet` | Suppress matching lines; exit code still reflects match/no-match |
| `-l`, `--files-with-matches` | Print only file names that contain a match |
| `--output-file` | Reserved and currently ignored: it is accepted but no file is written; output always goes to stdout |
| `--log-level` | Logging level (`DEBUG` … `CRITICAL`, default `INFO`) |

**Input:** If no files are given, standard input is read. Use `-` explicitly for stdin in a file list. Glob patterns in file arguments are expanded.

**Exit codes:**

| Code | Meaning |
|------|---------|
| `0` | At least one match |
| `1` | I/O or other runtime error |
| `2` | Invalid regular expression, or command-line usage error (missing pattern, unknown option) |
| `3` | No matches |

**Examples:**

```bash
greppy error /var/log/app.log
greppy -n warning issues.txt
echo "one two" | greppy -w two
```

### cutty

Extract delimited fields or fixed character positions from each input line.

**Syntax:** `cutty [OPTIONS] [input_files...]`

Either `-f`/`--field` or `-c`/`--characters` is required (mutually exclusive).

| Option | Description |
|--------|-------------|
| `-f`, `--field SPEC` | Comma-separated fields or ranges (1-based), e.g. `1,3,5-7`, or `3-` as the entire spec for an open-ended range (see limitations) |
| `-c`, `--characters SPEC` | Comma-separated character positions or ranges (1-based) |
| `-d`, `--delimiter` | Field delimiter (default: tab) |
| `-s`, `--only-delimited` | In field mode, skip lines that do not contain the delimiter |
| `--output-file` | Reserved and currently ignored: it is accepted but no file is written; output always goes to stdout |
| `--log-level` | Logging level (`DEBUG` … `CRITICAL`, default `INFO`) |

**Input:** If no files are given, standard input is read.

**Exit codes:**

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Invalid arguments, invalid field/character spec, or I/O error |

**Examples:**

```bash
cutty -f 1,3 data.tsv
cutty -d ',' -f 2 records.csv
echo "a:b:c" | cutty -d ':' -f 2
cutty -c 1-5 lines.txt
```

### Pipelines

Installed entrypoints compose in shell pipelines like other line-oriented tools:

```bash
greppy pattern file.txt | cutty -f 2
```

### Known limitations

- **Mixed open-ended ranges are not supported.** Use `N-` only as the whole `-f` spec (for example `-f 3-`). A mixed list such as `-f 1,3-` selects the fields between the listed numbers too (field 2 is included), and tokens after an open-ended range (for example the `0` in `-f 3-,0`) are not validated. `-c` has the same behavior. These are unfixed bugs, not supported syntax.
- A pipeline's exit status is the last command's. To see an upstream greppy status (3 no match, 2 usage/regex, 1 error), use `set -o pipefail`; recut does not claim GNU exit-code parity.
- `greppy` strips leading and trailing whitespace from matching lines. In field mode, `cutty` treats a line without the delimiter as one field (GNU `cut` passes it through).
- `--output-file` is ignored (see the option tables).

## Blog Series

For detailed explanations of how these commands work, visit the [Posix In Python blog series](https://www.mcindi.com/blog).

## Contributing

Contributions are welcome! Please feel free to submit issues, fork the repository, and create pull requests for any improvements.

## License

MIT

## Author

Cliff
