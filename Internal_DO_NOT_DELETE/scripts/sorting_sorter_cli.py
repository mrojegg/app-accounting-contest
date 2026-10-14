from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import sorting_config as config
import sorting_review_fields
import sorting_completion_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Сортировка документов по регламенту ПРИМЕР / ОБРАЗЕЦ."
    )
    parser.add_argument("input_dir", type=Path, help="Папка с исходными документами")
    parser.add_argument(
        "--archive-name",
        default="Архив_документов",
        help="Имя папки архива внутри input_dir",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Папка, в которой нужно создать архив. По умолчанию архив создаётся внутри input_dir.",
    )
    parser.add_argument(
        "--mode",
        choices=["copy", "move"],
        default="move",
        help="Режим работы: копировать или переносить документы",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Применить изменения. Без флага выполняется только dry-run.",
    )
    return parser


def emit_json_event(event_type: str, **payload: object) -> None:
    body = {"type": event_type, **payload}
    print(f"[event-json] {json.dumps(body, ensure_ascii=False, sort_keys=True)}")


def emit_summary(archive_root: Path, *, total: int, unresolved: int, manual_review: int, apply_mode: bool) -> None:
    print()
    print(f"Всего документов: {total}")
    print(f"Не распределено: {unresolved}")
    print(f"Ручная проверка: {manual_review}")
    print(f"Режим: {'применение' if apply_mode else 'dry-run'}")
    emit_json_event(
        "summary",
        archive_root=str(archive_root),
        unresolved=unresolved,
        manual_review=manual_review,
        total=total,
        apply_mode=apply_mode,
    )
    print(f"[summary] archive_root={archive_root}")
    print(f"[summary] unresolved={unresolved}")
    print(f"[summary] manual_review={manual_review}")
    print(f"[summary] total={total}")


def main(core: Any, argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    input_dir = args.input_dir.expanduser().resolve()
    archive_parent = args.output_dir.expanduser().resolve() if args.output_dir else input_dir
    archive_root = archive_parent / args.archive_name
    dry_run = not args.apply

    if not input_dir.exists() or not input_dir.is_dir():
        print(f"Папка не найдена: {input_dir}", file=sys.stderr)
        return 2

    rules_issues = config.validate_rules_file()
    if rules_issues:
        rules_file = config.resolve_rules_file()
        print(f"Ошибка валидации правил: {rules_file}", file=sys.stderr)
        for issue in rules_issues:
            print(f"- строка {issue.line_number}: {issue.message}", file=sys.stderr)
        emit_json_event(
            "rules_validation_error",
            rules_file=str(rules_file),
            issues=[{"line_number": issue.line_number, "message": issue.message} for issue in rules_issues],
        )
        return 2

    files = core.collect_files(input_dir, archive_root)
    if not files:
        print("Поддерживаемые документы не найдены.")
        if args.apply:
            core.ensure_structure(archive_root, set(), dry_run=False)
            sorting_completion_report.start_inputs(archive_root, [])
            sorting_completion_report.write_report(archive_root)
        emit_summary(archive_root, total=0, unresolved=0, manual_review=0, apply_mode=args.apply)
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

    optional_roots = {item.category for item in classifications if item.category in core.ROOT_FOLDERS_OPTIONAL}
    core.ensure_structure(archive_root, optional_roots, dry_run)
    if not dry_run:
        sorting_completion_report.start_inputs(archive_root, files)

    unresolved = 0
    manual_review_items = []
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
        final_destination = core.move_or_copy(source, destination, args.mode, dry_run)
        if not dry_run:
            sorting_completion_report.record_destination(archive_root, source, final_destination)
        if result.requires_manual_review:
            manual_review_items.append((final_destination, result))

    core.write_manual_review_report(archive_root, manual_review_items, dry_run)
    if not dry_run:
        sorting_completion_report.write_report(archive_root)
    emit_summary(
        archive_root,
        total=len(files),
        unresolved=unresolved,
        manual_review=len(manual_review_items),
        apply_mode=args.apply,
    )

    if unresolved or manual_review_items:
        print("Часть файлов требует ручной проверки.")

    return 0
