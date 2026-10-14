#!/usr/bin/env python3
from __future__ import annotations

import sorting_sorter_cli as sorter_cli
import sorting_sorter_core as sorter_core


def __getattr__(name: str):
    return getattr(sorter_core, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(sorter_core)) | {"main"})


def main(argv: list[str] | None = None) -> int:
    return sorter_cli.main(sorter_core, argv)


if __name__ == "__main__":
    raise SystemExit(main())
