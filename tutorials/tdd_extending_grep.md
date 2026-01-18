# Extending grep with Test-Driven Development

This tutorial walks through adding four new features to our `grep` command using **Test-Driven Development (TDD)**. TDD follows the "Red-Green-Refactor" cycle: write tests first, watch them fail, implement features to make them pass, then refactor.

The features we'll add are:
- `-H, --with-filename` — Print the filename with each match
- `-n, --line-number` — Print the line number with each match
- `-q, --quiet` — Suppress output; return exit code only
- `-l, --files-with-matches` — Print only filenames containing matches

If you want to see the final code, check out the [repo](https://github.com/McIndi/recut).

## 0) Setup

Ensure you have:
- The existing `grep.py` from [Building a Tiny `grep` in Python](./building_grep.md)
- A test file `tests/test_grep.py` with the basic test suite
- `pytest` installed via `pip install -e .[dev]`

Run tests to confirm the current state passes:

```bash
python -m pytest tests/test_grep.py -v
```

## 1) Red: Write Tests for `-H` (with-filename)

The **Red** phase is about writing failing tests. Start with the simplest case: a single file match should include the filename in output.

Add to `tests/test_grep.py`:

```python
def test_main_with_filename_single_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    file_path = write_lines(tmp_path, "sample.txt", ["alpha", "needle line", "beta"])

    code = main(["needle", "-H", str(file_path)])
    out = capsys.readouterr().out.strip().splitlines()

    assert code == RETURN_CODES["SUCCESS"]
    assert len(out) == 1
    assert str(file_path) in out[0]
    assert "needle line" in out[0]
```

This test will fail because the `-H` flag doesn't exist yet.

Add a second test for multiple files:

```python
def test_main_with_filename_multiple_files(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    file1 = write_lines(tmp_path, "file1.txt", ["needle", "alpha"])
    file2 = write_lines(tmp_path, "file2.txt", ["beta", "needle"])

    code = main(["needle", "-H", str(file1), str(file2)])
    out = capsys.readouterr().out.strip().splitlines()

    assert code == RETURN_CODES["SUCCESS"]
    assert len(out) == 2
    assert any(str(file1) in line for line in out)
    assert any(str(file2) in line for line in out)
```

Run the tests:

```bash
python -m pytest tests/test_grep.py::test_main_with_filename_single_file -v
```

They'll fail because the argument doesn't exist. **This is the Red phase.**

## 2) Green: Add `-H` to the Parser

Now add the argument to `create_parser()` in `grep.py`:

```python
parser.add_argument(
    "-H",
    "--with-filename",
    action="store_true",
    help="Print the filename with each match.",
)
```

Modify the main function's search loop to check the flag and prepend the filename:

```python
# In the line-matching section:
if regex.search(line):
    matches += 1
    output = line.strip()
    
    if parsed_args.with_filename:
        output = f"{target}:{output}"
    
    print(output)
```

Run the tests again:

```bash
python -m pytest tests/test_grep.py::test_main_with_filename_single_file -v
```

They should now pass. **This is the Green phase.**

## 3) Refactor: Improve Output Formatting

Before moving on, refactor the output logic to handle future flags. Extract it into a cleaner structure that will work with `-n` and other flags:

```python
if regex.search(line):
    matches += 1
    output = line.strip()
    
    # Format output based on flags
    if parsed_args.with_filename:
        output = f"{target}:{output}"
    
    print(output)
```

This is simple now but will scale well when we add `-n`.

## 4) Red: Write Tests for `-n` (line-number)

Add tests for line numbers:

```python
def test_main_line_number(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    file_path = write_lines(tmp_path, "sample.txt", ["alpha", "needle line", "beta"])

    code = main(["needle", "-n", str(file_path)])
    out = capsys.readouterr().out.strip().splitlines()

    assert code == RETURN_CODES["SUCCESS"]
    assert len(out) == 1
    assert out[0].startswith("2:")
    assert "needle line" in out[0]
```

Add a test with multiple matches:

```python
def test_main_line_number_multiple_matches(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    file_path = write_lines(tmp_path, "sample.txt", ["alpha", "needle", "beta", "needle line"])

    code = main(["needle", "-n", str(file_path)])
    out = capsys.readouterr().out.strip().splitlines()

    assert code == RETURN_CODES["SUCCESS"]
    assert len(out) == 2
    assert out[0].startswith("2:")
    assert out[1].startswith("4:")
```

And test `-H` and `-n` together:

```python
def test_main_with_filename_and_line_number(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    file_path = write_lines(tmp_path, "sample.txt", ["alpha", "needle line", "beta"])

    code = main(["needle", "-H", "-n", str(file_path)])
    out = capsys.readouterr().out.strip().splitlines()

    assert code == RETURN_CODES["SUCCESS"]
    assert len(out) == 1
    assert str(file_path) in out[0]
    assert "2:" in out[0]
    assert "needle line" in out[0]
```

**Red phase:** Tests fail because `-n` isn't implemented.

## 5) Green: Implement `-n`

Add the argument:

```python
parser.add_argument(
    "-n",
    "--line-number",
    action="store_true",
    help="Print the line number with each match.",
)
```

Track line numbers in the search loop:

```python
line_number = 0
for line in input_stream:
    line_number += 1
    if regex.search(line):
        matches += 1
        output = line.strip()
        
        if parsed_args.with_filename:
            output = f"{target}:{output}"
        
        if parsed_args.line_number:
            output = f"{line_number}:{output}"
        
        # Handle both flags together
        if parsed_args.with_filename and parsed_args.line_number:
            output = f"{target}:{line_number}:{line.strip()}"
        
        print(output)
```

**Green phase:** Tests pass.

## 6) Red: Write Tests for `-q` (quiet)

Quiet mode suppresses all output:

```python
def test_main_quiet_mode_match(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    file_path = write_lines(tmp_path, "sample.txt", ["alpha", "needle line", "beta"])

    code = main(["needle", "-q", str(file_path)])
    out = capsys.readouterr().out

    assert code == RETURN_CODES["SUCCESS"]
    assert out == ""
```

And test that it still returns the correct exit code when there are no matches:

```python
def test_main_quiet_mode_no_match(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    file_path = write_lines(tmp_path, "sample.txt", ["alpha", "beta", "gamma"])

    code = main(["needle", "-q", str(file_path)])
    out = capsys.readouterr().out

    assert code == RETURN_CODES["NO_MATCH"]
    assert out == ""
```

**Red phase:** Tests fail.

## 7) Green: Implement `-q`

Add the argument:

```python
parser.add_argument(
    "-q",
    "--quiet",
    action="store_true",
    help="Suppress normal output; return exit code only.",
)
```

Modify the output logic:

```python
if regex.search(line):
    matches += 1
    
    if not parsed_args.quiet:
        output = line.strip()
        
        if parsed_args.with_filename:
            output = f"{target}:{output}"
        
        if parsed_args.line_number:
            output = f"{line_number}:{output}"
        
        if parsed_args.with_filename and parsed_args.line_number:
            output = f"{target}:{line_number}:{line.strip()}"
        
        print(output)
```

**Green phase:** Tests pass.

## 8) Red: Write Tests for `-l` (files-with-matches)

The `-l` flag outputs only filenames containing matches:

```python
def test_main_files_with_matches(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    file1 = write_lines(tmp_path, "file1.txt", ["needle", "alpha"])
    file2 = write_lines(tmp_path, "file2.txt", ["beta", "gamma"])
    file3 = write_lines(tmp_path, "file3.txt", ["needle again"])

    code = main(["needle", "-l", str(file1), str(file2), str(file3)])
    out = capsys.readouterr().out.strip().splitlines()

    assert code == RETURN_CODES["SUCCESS"]
    assert len(out) == 2
    assert str(file1) in out
    assert str(file3) in out
    assert str(file2) not in out
```

And test when no files match:

```python
def test_main_files_with_matches_no_matches(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    file1 = write_lines(tmp_path, "file1.txt", ["alpha", "beta"])
    file2 = write_lines(tmp_path, "file2.txt", ["gamma", "delta"])

    code = main(["needle", "-l", str(file1), str(file2)])
    out = capsys.readouterr().out

    assert code == RETURN_CODES["NO_MATCH"]
    assert out.strip() == ""
```

**Red phase:** Tests fail.

## 9) Green: Implement `-l`

Add the argument:

```python
parser.add_argument(
    "-l",
    "--files-with-matches",
    action="store_true",
    help="Print only the filenames containing matches.",
)
```

Modify the search loop to track files with matches:

```python
matches = 0
targets = _expand_inputs(parsed_args.input_files)
files_with_matches: Set[str] = set()

with ExitStack() as stack:
    for target in targets:
        try:
            if target == "-":
                input_stream: TextIO = sys.stdin
            else:
                input_stream = stack.enter_context(open(target, "r"))
        except IOError as e:
            log.error("Error opening input file %s: %s", target, e)
            return RETURN_CODES["ERROR"]

        line_number = 0
        for line in input_stream:
            line_number += 1
            if regex.search(line):
                matches += 1
                
                # Track files with matches for -l flag
                if parsed_args.files_with_matches:
                    files_with_matches.add(target)
                
                # Output matching line (unless in quiet or files-with-matches mode)
                if not parsed_args.quiet and not parsed_args.files_with_matches:
                    output = line.strip()
                    
                    if parsed_args.with_filename:
                        output = f"{target}:{output}"
                    
                    if parsed_args.line_number:
                        output = f"{line_number}:{output}"
                    
                    if parsed_args.with_filename and parsed_args.line_number:
                        output = f"{target}:{line_number}:{line.strip()}"
                    
                    print(output)

# Output filenames if -l flag was set
if parsed_args.files_with_matches:
    for filename in sorted(files_with_matches):
        print(filename)
    if files_with_matches:
        matches = len(files_with_matches)
```

**Green phase:** Tests pass.

## 10) Run Full Test Suite

Now run all tests to ensure everything works together:

```bash
python -m pytest tests/test_grep.py -v
```

All 19 tests (9 original + 10 new) should pass with 99% coverage.

## 11) Manual Testing

Test the new flags manually:

```bash
# Create a sample file
echo -e "alpha\nneedle line\nbeta\nneedle again" > sample.txt

# Test -H
python -m recut.commands.grep needle -H sample.txt
# Output: sample.txt:needle line
#         sample.txt:needle again

# Test -n
python -m recut.commands.grep needle -n sample.txt
# Output: 2:needle line
#         4:needle again

# Test -H -n together
python -m recut.commands.grep needle -H -n sample.txt
# Output: sample.txt:2:needle line
#         sample.txt:4:needle again

# Test -q (quiet)
python -m recut.commands.grep needle -q sample.txt
echo $?  # Prints 0 (success), no output

# Test -l on multiple files
echo "no match here" > file1.txt
echo "needle here" > file2.txt
python -m recut.commands.grep needle -l sample.txt file1.txt file2.txt
# Output: file2.txt
#         sample.txt
```

## Key TDD Insights

1. **Write tests first** — Tests define behavior before implementation, preventing guesswork.
2. **One feature at a time** — Adding `-H`, then `-n`, then `-q`, then `-l` in isolation made each feature simple.
3. **Test interactions** — Combinations like `-H -n` need explicit tests to catch unexpected behaviors.
4. **Refactor fearlessly** — With comprehensive tests, refactoring the output formatting was risk-free.
5. **Coverage guides you** — Tests achieve 99% coverage, meaning almost all code paths are validated.

## Next Steps

Consider adding more flags using the same TDD approach:
- `-v, --invert-match` — Print lines that don't match
- `-c, --count` — Print count of matching lines per file
- `-A NUM, --after-context` — Print NUM lines after each match
- `-B NUM, --before-context` — Print NUM lines before each match

For each, follow the cycle: write tests, watch them fail, implement, refactor.

---

Check out the [repo](https://github.com/McIndi/recut) for the complete source. Stay tuned for the next installment of our Posix In Python series!
