"""Pin behavior that README 'Known limitations' documents, so docs stay true."""

import tomllib
from pathlib import Path

from recut.commands.cut import parse_field_spec

ROOT = Path(__file__).resolve().parents[1]


def test_standalone_open_ended_range_is_supported() -> None:
    assert parse_field_spec("3-") == ([3], True)


def test_mixed_open_ended_list_is_documented_limitation() -> None:
    # Returns early: fields 1 and 3 only; the caller then treats 3- as open-ended.
    fields, open_ended = parse_field_spec("1,3-")
    assert fields == [1, 3] and open_ended
    # Later tokens are not validated (documented): '0' is silently ignored.
    assert parse_field_spec("3-,0") == ([3], True)
    readme = (ROOT / "README.md").read_text()
    assert "Mixed open-ended ranges are not supported" in readme


def test_python_classifiers_match_requires_python() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    assert project["requires-python"] == ">=3.10"
    assert "Programming Language :: Python :: 3.9" not in project["classifiers"]
