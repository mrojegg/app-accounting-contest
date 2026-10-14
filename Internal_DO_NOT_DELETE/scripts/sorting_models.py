from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Classification:
    destination: Path | None
    office: str | None
    category: str | None
    entity: str | None
    reason: str
    new_name: str
    confidence: int
    requires_manual_review: bool
    trace: list[str]
    salary_duplicate: bool = False
    review_fields: dict[str, str] = field(default_factory=dict)


@dataclass
class DetectionResult:
    value: str | None
    reason: str
    confidence: int
    trace: list[str]
