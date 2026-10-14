#!/usr/bin/env python3
"""Stage a relocatable CPython distribution and pinned runtime dependencies."""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--dependencies", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    python = args.source / "bin/python3"
    version = subprocess.check_output([str(python), "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"], text=True).strip()
    stdlib = args.source / "lib" / f"python{version}"
    if not stdlib.is_dir() or not (args.dependencies / "pymupdf").is_dir():
        raise SystemExit("Нужен переносимый CPython и зависимости из requirements-macos.txt")
    if args.output.exists():
        raise SystemExit(f"Каталог Python уже существует: {args.output}")
    (args.output / "bin").mkdir(parents=True)
    shutil.copy2(python.resolve(), args.output / "bin/python3")
    shutil.copytree(stdlib, args.output / "lib" / f"python{version}", ignore=shutil.ignore_patterns("site-packages", "__pycache__", "*.pyc", "test", "tests", "idlelib", "tkinter", "ensurepip"))
    for library in (args.source / "lib").glob("*.dylib"):
        shutil.copy2(library, args.output / "lib" / library.name)
    shutil.copytree(args.dependencies, args.output / "lib" / f"python{version}" / "site-packages", ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "bin"))
    subprocess.run([str(args.output / "bin/python3"), "-E", "-s", "-c", "import fitz, openpyxl, xlrd, rapidfuzz, ssl; print('Bundled Python verified')"], check=True)


if __name__ == "__main__":
    main()
