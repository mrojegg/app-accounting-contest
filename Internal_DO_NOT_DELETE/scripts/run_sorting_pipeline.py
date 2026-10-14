#!/usr/bin/env python3
from __future__ import annotations

import argparse
import inspect
import json
import shutil
from pathlib import Path

import build_commission_table
import build_insurance_distribution
import build_insurance_distribution_generic
import build_insurance_distribution_demo_b
import build_salary_tables
import build_tax_distribution
import build_tax_distribution_generic
import build_tax_distribution_demo_b
import sort_documents
import sorting_postprocess_settings
import sorting_receipt_archive
import sorting_windows_delivery
import salary_employee_counts
import sorting_completion_report


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INTERNAL_ROOT = PROJECT_ROOT / "Internal_DO_NOT_DELETE"
RESOLVED_MANUAL_SUBFOLDERS = {"Исключенные_повторы"}


def emit_json_event(event_type: str, **payload: object) -> None:
    body = {"type": event_type, **payload}
    print(f"[event-json] {json.dumps(body, ensure_ascii=False, sort_keys=True)}")


def run_module(module, argv: list[str]) -> None:
    main_fn = module.main
    if len(inspect.signature(main_fn).parameters) == 0:
        import sys

        old_argv = sys.argv[:]
        sys.argv = [f"{module.__name__}.py", *argv]
        try:
            result = main_fn()
        finally:
            sys.argv = old_argv
    else:
        result = main_fn(argv)
    if result not in (None, 0):
        raise RuntimeError(f"Модуль завершился с ошибкой ({result}): {module.__name__} {' '.join(argv)}")


def cleanup_archive(root: Path) -> None:
    for junk_name in (".DS_Store", "Thumbs.db"):
        for path in root.rglob(junk_name):
            if path.is_file():
                path.unlink()

    empty_dirs = sorted((path for path in root.rglob("*") if path.is_dir()), key=lambda item: len(item.parts), reverse=True)
    for path in empty_dirs:
        if any(path.iterdir()):
            continue
        path.rmdir()


def path_has_files(path: Path, pattern: str = "*") -> bool:
    return path.exists() and any(path.glob(pattern))


def build_task(module, *, root: Path, args: list[str], kind: str) -> dict[str, object]:
    return {
        "module": module,
        "root": root,
        "args": args,
        "kind": kind,
    }


def build_company_outputs(archive_root: Path) -> None:
    tasks: list[dict[str, object]] = []
    completed_receipt_groups: set[tuple[str, str]] = set()
    settings = sorting_postprocess_settings.load_postprocess_settings()

    demo_a_offices = salary_employee_counts.company_offices("ПРИМЕР", ["76", "93", "94", "102", "109"])
    demo_b_offices = salary_employee_counts.company_offices("ОБРАЗЕЦ", ["84", "98", "99"])
    has_any_salary = bool(sorting_receipt_archive.offices_with_receipts(archive_root, "Зарплата"))
    demo_a_tax_root = archive_root / "109" / "Ндфл и Взносы"
    demo_b_tax_root = archive_root / "98" / "Ндфл и Взносы"
    has_demo_a = any((archive_root / office).exists() for office in demo_a_offices)
    has_demo_b = any((archive_root / office).exists() for office in demo_b_offices)
    dynamic_tax_offices = [
        office.name
        for office in archive_root.iterdir()
        if office.is_dir()
        and office.name.isdigit()
        and office.name not in {*demo_a_offices, *demo_b_offices}
        and (office / "Ндфл и Взносы").exists()
    ]
    dynamic_commission_offices = sorting_receipt_archive.offices_with_receipts(archive_root, "Комиссии")

    if has_any_salary and settings.salary_table_enabled:
        tasks.append(build_task(build_salary_tables, root=archive_root, args=["--root", str(archive_root)], kind="salary"))

    if has_demo_a and settings.tax_and_insurance_excel_enabled:
        tasks.extend([
            build_task(
                build_tax_distribution,
                root=demo_a_tax_root,
                args=["--root", str(demo_a_tax_root), "--output-name", "Распределение_налогов_ПРИМЕР.xlsx"],
                kind="pdf",
            ),
            build_task(
                build_insurance_distribution,
                root=demo_a_tax_root,
                args=["--root", str(demo_a_tax_root), "--output-name", "Распределение_взносов_ПРИМЕР.xlsx"],
                kind="pdf",
            ),
        ])

    if has_demo_b and settings.tax_and_insurance_excel_enabled:
        tasks.extend([
            build_task(
                build_tax_distribution_demo_b,
                root=demo_b_tax_root,
                args=["--root", str(demo_b_tax_root), "--output-name", "Распределение_налогов_ОБРАЗЕЦ.xlsx"],
                kind="pdf",
            ),
            build_task(
                build_insurance_distribution_demo_b,
                root=demo_b_tax_root,
                args=["--root", str(demo_b_tax_root), "--output-name", "Распределение_взносов_ОБРАЗЕЦ.xlsx"],
                kind="pdf",
            ),
        ])

    if settings.commission_excel_enabled:
        for office in dynamic_commission_offices:
            commission_root = archive_root / office / "Комиссии"
            tasks.append(
                build_task(
                    build_commission_table,
                    root=commission_root,
                    args=["--root", str(commission_root), "--output-name", f"Комиссии_{office}.xlsx"],
                    kind="commission",
                )
            )

    if settings.tax_and_insurance_excel_enabled:
        for office in dynamic_tax_offices:
            office_root = archive_root / office / "Ндфл и Взносы"
            tasks.extend([
                build_task(
                    build_tax_distribution_generic,
                    root=office_root,
                    args=["--root", str(office_root), "--office", office],
                    kind="pdf",
                ),
                build_task(
                    build_insurance_distribution_generic,
                    root=office_root,
                    args=["--root", str(office_root), "--office", office],
                    kind="pdf",
                ),
            ])

    for task in tasks:
        target_root = Path(task["root"])
        module = task["module"]
        if not target_root.exists():
            print(f"[postprocess-skip] {module.__name__}: папка не найдена: {target_root}", flush=True)
            emit_json_event("postprocess_skip", module=module.__name__, root=str(target_root), reason="root_missing")
            continue
        if task["kind"] == "salary":
            if not has_any_salary:
                print(f"[postprocess-skip] {module.__name__}: нет папок зарплаты", flush=True)
                emit_json_event("postprocess_skip", module=module.__name__, root=str(target_root), reason="no_salary")
                continue
        elif task["kind"] == "commission":
            if not sorting_receipt_archive.receipt_pdf_paths_for_category_dir(target_root):
                print(f"[postprocess-skip] {module.__name__}: нет исходных PDF комиссий: {target_root}", flush=True)
                emit_json_event("postprocess_skip", module=module.__name__, root=str(target_root), reason="no_commission_pdf")
                continue
        else:
            if not path_has_files(target_root, "*.pdf"):
                print(f"[postprocess-skip] {module.__name__}: нет PDF в папке: {target_root}", flush=True)
                emit_json_event("postprocess_skip", module=module.__name__, root=str(target_root), reason="no_pdf")
                continue
        argv = task["args"]
        print(f"[postprocess] {module.__name__} {' '.join(argv)}", flush=True)
        run_module(module, argv)
        if task["kind"] == "salary":
            completed_receipt_groups.update(
                (office, "Зарплата")
                for office in sorting_receipt_archive.offices_with_receipts(archive_root, "Зарплата")
            )
        elif task["kind"] == "commission":
            completed_receipt_groups.add((target_root.parent.name, "Комиссии"))

    moved_receipts = sorting_receipt_archive.archive_completed_receipts(
        archive_root,
        completed_receipt_groups,
    )
    if moved_receipts:
        print(f"[postprocess] исходные чеки перенесены: {len(moved_receipts)}", flush=True)
        emit_json_event(
            "source_receipts_archived",
            root=str(archive_root / sorting_receipt_archive.SOURCE_RECEIPTS_DIR_NAME),
            count=len(moved_receipts),
        )


def pending_manual_review_count(archive_root: Path) -> int:
    manual_root = archive_root / "Требует_ручной_проверки"
    if not manual_root.exists() or not manual_root.is_dir():
        return 0
    ignored_names = {"_report.txt", ".DS_Store", "Thumbs.db"}
    count = 0
    for path in manual_root.rglob("*"):
        if not path.is_file() or path.name in ignored_names or path.name.startswith("."):
            continue
        relative = path.relative_to(manual_root)
        if relative.parts and relative.parts[0] in RESOLVED_MANUAL_SUBFOLDERS:
            continue
        count += 1
    return count


def should_defer_postprocess(archive_root: Path) -> bool:
    return pending_manual_review_count(archive_root) > 0


def run_deferred_postprocess(archive_root: Path) -> Path:
    from sorting_manual_review import prune_manual_review_report

    if should_defer_postprocess(archive_root):
        count = pending_manual_review_count(archive_root)
        raise RuntimeError(f"Нельзя запускать postprocess: в ручной проверке осталось файлов: {count}")
    prune_manual_review_report(archive_root)
    print("[phase] postprocess")
    emit_json_event("phase", phase="postprocess")
    build_company_outputs(archive_root)
    print("[phase] cleanup")
    emit_json_event("phase", phase="cleanup")
    cleanup_archive(archive_root)
    print("[phase] windows-export")
    sorting_completion_report.write_report(archive_root, final=True)
    emit_json_event("phase", phase="windows-export")
    windows_zip = sorting_windows_delivery.create_windows_delivery_zip(archive_root)
    print(f"Windows ZIP: {windows_zip}")
    emit_json_event("windows_export", path=str(windows_zip))
    return windows_zip


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Полный пайплайн сортировки документов.")
    parser.add_argument("--source", type=Path, required=True, help="Папка с исходными документами")
    parser.add_argument("--output", type=Path, required=True, help="Папка, в которой будет создан архив")
    parser.add_argument("--archive-name", required=True, help="Имя итоговой папки архива")
    parser.add_argument("--mode", choices=["copy", "move"], default="copy", help="Копировать или переносить файлы")
    args = parser.parse_args(argv)

    source_dir = args.source.expanduser().resolve()
    output_dir = args.output.expanduser().resolve()
    archive_root = output_dir / args.archive_name

    if not source_dir.exists() or not source_dir.is_dir():
        raise SystemExit(f"Не найдена папка с исходными файлами: {source_dir}")
    if not output_dir.exists() or not output_dir.is_dir():
        raise SystemExit(f"Не найдена папка назначения: {output_dir}")
    if archive_root.exists():
        raise SystemExit(f"Папка архива уже существует: {archive_root}")

    print(f"Источник: {source_dir}")
    print(f"Папка назначения: {output_dir}")
    print(f"Итоговый архив: {archive_root}")
    print(f"Режим: {args.mode}")
    print()
    print("[phase] validation")
    emit_json_event("phase", phase="validation")

    sort_args = [
        str(source_dir),
        "--archive-name",
        args.archive_name,
        "--output-dir",
        str(output_dir),
        "--mode",
        args.mode,
        "--apply",
    ]
    print("[phase] sorting")
    emit_json_event("phase", phase="sorting")
    run_module(sort_documents, sort_args)
    print("[phase] cleanup")
    emit_json_event("phase", phase="cleanup")
    cleanup_archive(archive_root)
    pending_count = pending_manual_review_count(archive_root)
    if pending_count:
        print("[phase] postprocess-deferred")
        emit_json_event("phase", phase="postprocess-deferred")
        emit_json_event(
            "postprocess_deferred",
            archive_root=str(archive_root),
            pending_manual_review=pending_count,
        )
        print(f"Postprocess отложен: в ручной проверке осталось файлов: {pending_count}")
        sorting_completion_report.write_report(archive_root)
    else:
        run_deferred_postprocess(archive_root)

    print()
    print("[phase] finished")
    emit_json_event("phase", phase="finished")
    print(f"Готово: {archive_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
