#!/usr/bin/env python3
"""Validate McIndi/recut promotion pull request branch pairs."""

from __future__ import annotations

import re
import sys


def allowed(base: str, head: str, head_repo: str, base_repo: str) -> bool:
    if not head_repo or head_repo != base_repo:
        return False
    if base == "dev":
        return bool(re.fullmatch(r"(feature|fix)/.+", head))
    return {"qa": "dev", "prod": "qa", "main": "prod"}.get(base) == head


def main(argv: list[str]) -> int:
    if len(argv) != 5:
        print("usage: promotion.py BASE HEAD HEAD_REPO BASE_REPO", file=sys.stderr)
        return 2
    base, head, head_repo, base_repo = argv[1:]
    if not allowed(base, head, head_repo, base_repo):
        print(f"Invalid promotion: {head} -> {base}", file=sys.stderr)
        return 1
    print(f"Promotion allowed: {head} -> {base}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
