# Fixing Line Number Tracking in a Multi-File grep Implementation

## The Bug

While implementing a `grep` command-line tool in Python, I encountered a subtle but significant bug in line number tracking. The tool needed to search through multiple files and optionally display line numbers with the `-n` flag, similar to GNU grep. However, the line numbers were only accurate for the first file; subsequent files would show incorrect line numbers, offset by the cumulative line count of all previous files.

## The Problem

Here's the original buggy code:

```python
line_number = 0

try:
    for line, source in file_input_handler(targets):
        line_number += 1
        if regex.search(line):
            # ... output the match with line_number
```

The issue is straightforward once you see it: `line_number` is initialized once before processing begins and then increments continuously through all files. 

### Example of the Bug

Suppose we're searching through two files:

**file1.txt** (3 lines):
```
apple
banana
cherry
```

**file2.txt** (3 lines):
```
dog
elephant
fox
```

If we run `grep -n "e" file1.txt file2.txt`, we'd expect:

```
file1.txt:1:apple
file1.txt:3:cherry
file2.txt:2:elephant
file2.txt:3:fox
```

But instead we got:

```
file1.txt:1:apple
file1.txt:3:cherry
file2.txt:5:elephant  ← Wrong! Should be line 2
file2.txt:6:fox       ← Wrong! Should be line 3
```

The line numbers for file2.txt are offset by 3 (the size of file1.txt).

## Why Not Just Use enumerate()?

A common first instinct might be: "Why not just use Python's `enumerate()` function?" After all, it's designed for tracking indices in loops:

```python
for idx, (line, source) in enumerate(file_input_handler(targets), start=1):
    # Use idx as line_number
```

The problem is that `enumerate()` gives us the index within the **entire iteration**, not per file. The `file_input_handler()` generator yields lines from all files sequentially in one continuous stream:

```
(line1_from_file1, "file1.txt")
(line2_from_file1, "file1.txt")
(line3_from_file1, "file1.txt")
(line1_from_file2, "file2.txt")  ← enumerate would say this is index 4!
(line2_from_file2, "file2.txt")  ← enumerate would say this is index 5!
```

So `enumerate()` would produce the exact same bug we started with—it doesn't know when we've moved to a new file.

## The Solution

The fix requires tracking which file we're currently processing and resetting the line counter when we encounter a new file:

```python
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
            # ... output the match with line_number
```

Now each time `source` changes (indicating we've moved to a new file), we:
1. Update `current_source` to track our new location
2. Reset `line_number` to 0
3. Then increment it to 1 for the first line of the new file

## Testing the Fix

To ensure this bug doesn't resurface, we need a test that specifically verifies line numbers reset for each file. Here's the test I wrote:

```python
def test_line_numbers_reset_for_each_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """Test that line numbers reset to 1 for each new file when using -n flag."""
    # Create two files with matches at different positions
    file1 = write_lines(tmp_path, "file1.txt", ["alpha", "needle", "beta", "needle"])
    file2 = write_lines(tmp_path, "file2.txt", ["gamma", "needle", "delta"])
    
    code = main(["needle", "-H", "-n", str(file1), str(file2)])
    out = capsys.readouterr().out.strip().splitlines()
    
    assert code == RETURN_CODES["SUCCESS"]
    assert len(out) == 3
    
    # file1.txt should have matches at lines 2 and 4
    assert f"{file1}:2:needle" in out
    assert f"{file1}:4:needle" in out
    
    # file2.txt should have a match at line 2 (not line 6!)
    # This is the critical assertion - if line numbers don't reset,
    # this would be line 6 (4 lines from file1 + 2 lines into file2)
    assert f"{file2}:2:needle" in out
```

### Why This Test Works

This test is specifically designed to catch the boundary condition:

1. **Multiple files**: We need at least two files to expose the bug
2. **Strategic match positions**: The match in file2 is at line 2, which would incorrectly report as line 6 with the bug (4 lines from file1 + 2 lines into file2)
3. **Both -H and -n flags**: We need `-H` (with-filename) to distinguish outputs and `-n` (line-number) to verify the counters
4. **Explicit assertions**: The comment in the test explicitly documents what would happen if the bug existed

The beauty of this test is that it would **fail** with the buggy code (expecting "file2.txt:2:needle" but getting "file2.txt:6:needle") and **pass** with the fixed code.

### Testing Strategies for Boundary Conditions

When testing tools that process multiple inputs, always consider:

- **Single input**: Does it work for one file? (baseline)
- **Multiple inputs**: Does state reset between inputs?
- **Empty inputs**: What happens with zero-length files?
- **Mixed sources**: stdin and files, if supported
- **Edge positions**: Matches at first/last line of each file

This bug is a perfect example of why unit tests should go beyond the "happy path" and exercise boundary conditions where state transitions occur.

## Key Takeaways

1. **State management matters**: When processing multiple sources in a single loop, you need explicit state tracking to know when boundaries are crossed.

2. **Built-in tools have limitations**: `enumerate()` is excellent for tracking position in a single sequence, but it doesn't understand semantic boundaries like "we're now in a different file."

3. **Context is crucial**: The line number only makes sense within the context of a specific file. When that context changes, the counter must reset.

4. **Test with multiple inputs**: This bug wouldn't have been caught by only testing with a single file or stdin. Multi-file testing revealed the issue immediately.

This type of bug is common in tools that process multiple inputs sequentially—whether files, streams, or data batches. The solution pattern (track current context, reset counters on context change) applies broadly beyond just line counting in grep implementations.
