from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import sorting_routing as routing


@dataclass(frozen=True)
class RoutingDependencies:
    file_text: Callable[[Path], str]
    normalize_text: Callable[[str], str]


def destination_for(
    source: Path,
    archive_root: Path,
    office: str | None,
    category: str | None,
    entity: str | None,
    *,
    deps: RoutingDependencies,
) -> tuple[Path | None, str]:
    return routing.destination_for(
        source,
        archive_root,
        office,
        category,
        entity,
        file_text=deps.file_text,
        normalize_text=deps.normalize_text,
    )
