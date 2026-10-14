#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import run_sorting_pipeline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Финализатор архива: запускает postprocess только после полной ручной проверки."
    )
    parser.add_argument("--archive-root", type=Path, required=True, help="Путь к уже созданному архиву")
    args = parser.parse_args(argv)

    archive_root = args.archive_root.expanduser().resolve()
    if not archive_root.exists() or not archive_root.is_dir():
        raise SystemExit(f"Не найден архив: {archive_root}")

    print(f"Архив: {archive_root}")
    print()
    print("[phase] validation")
    run_sorting_pipeline.emit_json_event("phase", phase="validation")

    pending_count = run_sorting_pipeline.pending_manual_review_count(archive_root)
    if pending_count:
        print(f"Найдено файлов в ручной проверке: {pending_count}")
        run_sorting_pipeline.emit_json_event(
            "postprocess_blocked",
            archive_root=str(archive_root),
            pending_manual_review=pending_count,
        )
        return 2

    run_sorting_pipeline.run_deferred_postprocess(archive_root)
    print()
    print("[phase] finished")
    run_sorting_pipeline.emit_json_event("phase", phase="finished")
    print(f"Готово: {archive_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
