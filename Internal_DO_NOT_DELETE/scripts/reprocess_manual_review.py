#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import run_sorting_pipeline
import sorting_sorter_core as core
import sorting_manual_review
import sorting_review_fields
import sorting_completion_report


def emit_json_event(event_type: str, **payload: object) -> None:
    body = {"type": event_type, **payload}
    print(f"[event-json] {json.dumps(body, ensure_ascii=False, sort_keys=True)}")


def emit_summary(archive_root: Path, *, total: int, unresolved: int, manual_review: int) -> None:
    print()
    print(f"Всего документов: {total}")
    print(f"Не распределено: {unresolved}")
    print(f"Ручная проверка: {manual_review}")
    emit_json_event(
        "summary",
        archive_root=str(archive_root),
        unresolved=unresolved,
        manual_review=manual_review,
        total=total,
        apply_mode=True,
    )
    print(f"[summary] archive_root={archive_root}")
    print(f"[summary] unresolved={unresolved}")
    print(f"[summary] manual_review={manual_review}")
    print(f"[summary] total={total}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Дообработка папки ручной проверки с тяжелым OCR.")
    parser.add_argument("--archive-root", type=Path, required=True, help="Путь к уже созданному архиву")
    args = parser.parse_args(argv)

    archive_root = args.archive_root.expanduser().resolve()
    manual_root = archive_root / "Требует_ручной_проверки"

    if not archive_root.exists() or not archive_root.is_dir():
        raise SystemExit(f"Не найден архив: {archive_root}")
    if not manual_root.exists() or not manual_root.is_dir():
        raise SystemExit(f"Не найдена папка ручной проверки: {manual_root}")

    print(f"Архив: {archive_root}")
    print(f"Папка ручной проверки: {manual_root}")
    print()
    print("[phase] validation")
    emit_json_event("phase", phase="validation")

    sorting_manual_review.prune_manual_review_report(archive_root)
    os.environ["SORTING_ALLOW_HEAVY_OCR"] = "1"

    print("[phase] manual-review-reprocess")
    emit_json_event("phase", phase="manual-review-reprocess")
    files = [
        path
        for path in core.collect_files(manual_root, manual_root / "__manual_reprocess_ignore__")
        if not path.is_relative_to(manual_root / "Исключенные_повторы")
    ]
    if not files:
        print("Документы для дообработки не найдены.")
        emit_summary(archive_root, total=0, unresolved=0, manual_review=0)
        run_sorting_pipeline.run_deferred_postprocess(archive_root)
        print("[phase] finished")
        emit_json_event("phase", phase="finished")
        return 0

    print(f"Найдено документов: {len(files)}", flush=True)
    classifications = []
    for index, path in enumerate(files, start=1):
        print(f"[scan {index}/{len(files)}] {path.name}", flush=True)
        result = core.classify(path, archive_root)
        classifications.append(sorting_review_fields.prepare_review(path, result, archive_root, core))

    duplicate_count = core.mark_duplicate_salary_payments(files, classifications, archive_root)
    if duplicate_count:
        print(f"Найдено возможных повторов зарплаты: {duplicate_count}")
        emit_json_event("salary_duplicates", count=duplicate_count)

    unresolved = 0
    manual_review_items: list[tuple[Path, object]] = []
    for source, result in zip(files, classifications):
        if not result.destination:
            unresolved += 1
            print(f"[skip] {source.name}: {result.reason}")
            continue

        target_root = core.effective_destination(
            result.destination,
            archive_root,
            requires_manual_review=result.requires_manual_review,
        )
        destination = target_root / result.new_name
        try:
            destination_label = destination.relative_to(archive_root)
        except ValueError:
            destination_label = destination
        print(
            f"[plan] {source.name} -> {destination_label} | "
            f"офис={result.office or '?'} | категория={result.category or '?'} | "
            f"юрлицо={result.entity or '?'} | confidence={result.confidence}% | {result.reason}"
        )
        final_destination = source
        if source.resolve() != destination.resolve():
            final_destination = core.move_or_copy(source, destination, "move", False)
        if result.requires_manual_review:
            manual_review_items.append((final_destination, result))

    core.write_manual_review_report(archive_root, manual_review_items, False)
    sorting_completion_report.write_report(archive_root)
    emit_summary(
        archive_root,
        total=len(files),
        unresolved=unresolved,
        manual_review=len(manual_review_items),
    )

    if unresolved or manual_review_items:
        print("Часть файлов требует ручной проверки.")
        emit_json_event(
            "postprocess_deferred",
            archive_root=str(archive_root),
            pending_manual_review=len(manual_review_items),
        )
        print("[phase] finished")
        emit_json_event("phase", phase="finished")
        print(f"Готово: {archive_root}")
        return 0
    else:
        run_sorting_pipeline.run_deferred_postprocess(archive_root)

    print()
    print("[phase] finished")
    emit_json_event("phase", phase="finished")
    print(f"Готово: {archive_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
