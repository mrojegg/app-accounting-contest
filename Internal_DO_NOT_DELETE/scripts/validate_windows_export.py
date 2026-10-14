#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

from sorting_windows_export import issues_as_json, validate_windows_export


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: validate_windows_export.py <archive_root>", file=sys.stderr)
        return 2
    root = Path(argv[1]).expanduser()
    if not root.exists():
        print(f"not found: {root}", file=sys.stderr)
        return 2
    issues = validate_windows_export(root)
    print(f"Checked: {root}")
    print(f"Issues: {len(issues)}")
    if issues:
        print(issues_as_json(issues))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
