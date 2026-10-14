from __future__ import annotations

import re
import shutil
from pathlib import Path


def ensure_structure(
    archive_root: Path,
    optional_roots: set[str],
    dry_run: bool,
    *,
    offices: list[str] | None = None,
    office_categories: dict[str, list[str]] | None = None,
    create_folders_only_when_documents_exist: bool = True,
    do_not_create_empty_folders_in_advance: bool = True,
    create_manual_review_folder_only_when_needed: bool = True,
) -> None:
    folders = [archive_root]
    folders.extend(archive_root / folder for folder in optional_roots)
    if not create_folders_only_when_documents_exist and not do_not_create_empty_folders_in_advance:
        for office in offices or []:
            folders.append(archive_root / office)
            for category in office_categories.get(office, []) if office_categories else []:
                folders.append(archive_root / office / category)
    if not create_manual_review_folder_only_when_needed:
        folders.append(archive_root / "Требует_ручной_проверки")
    for folder in folders:
        if dry_run:
            print(f"[dry-run] mkdir -p {folder}")
        else:
            folder.mkdir(parents=True, exist_ok=True)


def unique_destination(destination: Path, *, keep_unique_suffix_on_conflict: bool = True) -> Path:
    if not keep_unique_suffix_on_conflict:
        return destination
    if not destination.exists():
        return destination
    candidate = destination
    counter = 2
    while candidate.exists():
        amount_at_end = re.match(r"^(.*)_(\d+(?:-\d{2}|,\d{2}|без_суммы))$", destination.stem)
        if amount_at_end:
            prefix, amount = amount_at_end.groups()
            candidate = destination.with_name(f"{prefix}_{counter}_{amount}{destination.suffix}")
        else:
            candidate = destination.with_name(f"{destination.stem}_{counter}{destination.suffix}")
        counter += 1
    return candidate


def move_or_copy(
    source: Path,
    destination: Path,
    mode: str,
    dry_run: bool,
    *,
    unique_destination_fn,
    generated_source_roots: set[Path],
    keep_unique_suffix_on_conflict: bool = True,
) -> Path:
    # Preserving originals is mandatory even when legacy rules disable suffixes.
    destination = unique_destination_fn(destination, keep_unique_suffix_on_conflict=True)
    effective_mode = "copy" if _is_generated_source(source, generated_source_roots) else mode
    if dry_run:
        print(f"[dry-run] {effective_mode} {source} -> {destination}")
        return destination

    destination.parent.mkdir(parents=True, exist_ok=True)
    if effective_mode == "move":
        shutil.move(str(source), str(destination))
    else:
        shutil.copyfile(source, destination)
    return destination


def _is_generated_source(path: Path, generated_source_roots: set[Path]) -> bool:
    for root in generated_source_roots:
        try:
            path.resolve().relative_to(root.resolve())
            return True
        except Exception:
            continue
    return False


def effective_destination(
    destination: Path,
    archive_root: Path,
    *,
    create_special_subfolders_by_routing_rules: bool = True,
    requires_manual_review: bool = False,
) -> Path:
    if create_special_subfolders_by_routing_rules or requires_manual_review:
        return destination
    try:
        relative = destination.relative_to(archive_root)
    except ValueError:
        return destination
    if len(relative.parts) >= 3 and relative.parts[0].isdigit():
        return archive_root / relative.parts[0] / relative.parts[1]
    return destination
