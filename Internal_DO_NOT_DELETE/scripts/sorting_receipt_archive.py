from __future__ import annotations

import re
import shutil
from pathlib import Path

import sorting_file_ops


SOURCE_RECEIPTS_DIR_NAME = "Исходные_чеки"
ARCHIVED_CATEGORIES = ("Зарплата", "Комиссии")


def stored_receipt_dir(archive_root: Path, office: str, category: str) -> Path:
    return archive_root / SOURCE_RECEIPTS_DIR_NAME / office / category


def category_context(category_root: Path) -> tuple[Path, str, str] | None:
    office_root = category_root.parent
    if not office_root.name.isdigit():
        return None
    return office_root.parent, office_root.name, category_root.name


def is_generated_summary(path: Path, category: str) -> bool:
    return bool(
        re.fullmatch(r"(?:Зарплата|Комиссии)_\d+_чеки\.pdf", path.name, re.IGNORECASE)
        or re.fullmatch(rf"{re.escape(category)}_\d+_чеки\.pdf", path.name, re.IGNORECASE)
    )


def receipt_pdf_paths(archive_root: Path, office: str, category: str) -> list[Path]:
    roots = [archive_root / office / category, stored_receipt_dir(archive_root, office, category)]
    paths: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        paths.extend(
            path
            for path in root.glob("*.pdf")
            if path.is_file() and not is_generated_summary(path, category)
        )
    return sorted(paths, key=lambda path: (path.name.casefold(), str(path.parent).casefold()))


def receipt_pdf_paths_for_category_dir(category_root: Path) -> list[Path]:
    context = category_context(category_root)
    if context is None:
        return sorted(
            (
                path
                for path in category_root.glob("*.pdf")
                if path.is_file() and not is_generated_summary(path, category_root.name)
            ),
            key=lambda path: path.name.casefold(),
        )
    archive_root, office, category = context
    return receipt_pdf_paths(archive_root, office, category)


def office_has_receipts(archive_root: Path, office: str, category: str) -> bool:
    return bool(receipt_pdf_paths(archive_root, office, category))


def offices_with_receipts(archive_root: Path, category: str) -> list[str]:
    offices: set[str] = set()
    if archive_root.exists():
        offices.update(path.name for path in archive_root.iterdir() if path.is_dir() and path.name.isdigit())
    stored_root = archive_root / SOURCE_RECEIPTS_DIR_NAME
    if stored_root.exists():
        offices.update(path.name for path in stored_root.iterdir() if path.is_dir() and path.name.isdigit())
    return sorted(
        (office for office in offices if office_has_receipts(archive_root, office, category)),
        key=int,
    )


def completed_outputs_exist(archive_root: Path, office: str, category: str) -> bool:
    category_root = archive_root / office / category
    return (
        (category_root / f"{category}_{office}.xlsx").is_file()
        and (category_root / f"{category}_{office}_чеки.pdf").is_file()
    )


def archive_completed_receipts(
    archive_root: Path,
    completed_groups: set[tuple[str, str]] | None = None,
) -> list[tuple[Path, Path]]:
    moved: list[tuple[Path, Path]] = []
    for category in ARCHIVED_CATEGORIES:
        offices = {
            path.name
            for path in archive_root.iterdir()
            if path.is_dir() and path.name.isdigit()
        }
        for office in sorted(offices, key=int):
            if completed_groups is not None and (office, category) not in completed_groups:
                continue
            if not completed_outputs_exist(archive_root, office, category):
                continue
            source_root = archive_root / office / category
            destination_root = stored_receipt_dir(archive_root, office, category)
            for source in sorted(source_root.glob("*.pdf"), key=lambda path: path.name.casefold()):
                if not source.is_file() or is_generated_summary(source, category):
                    continue
                destination = sorting_file_ops.unique_destination(destination_root / source.name)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source), str(destination))
                moved.append((source, destination))
    return moved
