#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import run_sorting_pipeline
import sorting_completion_report


def emit_json_event(event_type: str, **payload: object) -> None:
    body = {"type": event_type, **payload}
    print(f"[event-json] {json.dumps(body, ensure_ascii=False, sort_keys=True)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Финальная постобработка архива после ручной корректировки.")
    parser.add_argument("--archive-root", type=Path, required=True)
    args = parser.parse_args(argv)

    archive_root = args.archive_root.expanduser().resolve()
    if not archive_root.exists() or not archive_root.is_dir():
        raise SystemExit(f"Не найден архив: {archive_root}")

    if run_sorting_pipeline.should_defer_postprocess(archive_root):
        sorting_completion_report.write_report(archive_root)
        pending = run_sorting_pipeline.pending_manual_review_count(archive_root)
        print(f"Финализация отложена: в ручной проверке осталось {pending} файлов.")
        emit_json_event("manual_review_pending", archive_root=str(archive_root), pending_manual_review=pending)
        return 0

    run_sorting_pipeline.run_deferred_postprocess(archive_root)
    print("[phase] finished")
    emit_json_event("phase", phase="finished")
    print(f"Готово: {archive_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
