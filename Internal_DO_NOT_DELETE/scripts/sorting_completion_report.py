from __future__ import annotations

import json
from pathlib import Path

from sorting_manual_review import atomic_write, load_manual_review_metadata
from sorting_review_fields import fingerprint

LEDGER_NAME = ".processing_inputs.json"
REPORT_NAME = "Итог_обработки.json"
TEXT_NAME = "Итог_обработки.txt"


def start_inputs(root: Path, files: list[Path]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    rows = [{"source": str(path), "sha256": fingerprint(path), "size": path.stat().st_size,
             "destination": ""} for path in files]
    atomic_write(root / LEDGER_NAME, json.dumps(rows, ensure_ascii=False, indent=2) + "\n")


def record_destination(root: Path, source: Path, destination: Path) -> None:
    store = root / LEDGER_NAME
    if not store.exists():
        return
    rows = json.loads(store.read_text(encoding="utf-8"))
    for row in rows:
        if row["source"] == str(source):
            row["destination"] = str(destination.relative_to(root))
            break
    atomic_write(store, json.dumps(rows, ensure_ascii=False, indent=2) + "\n")


def write_report(root: Path, *, final: bool = False) -> dict:
    ledger = root / LEDGER_NAME
    if not ledger.exists():
        return {}
    rows = json.loads(ledger.read_text(encoding="utf-8"))
    sizes = {row["size"] for row in rows}
    by_hash: dict[str, list[Path]] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or any(part.startswith(".") for part in path.relative_to(root).parts):
            continue
        if path.name in {REPORT_NAME, TEXT_NAME, "_report.txt"} or path.stat().st_size not in sizes:
            continue
        by_hash.setdefault(fingerprint(path), []).append(path)
    details = load_manual_review_metadata(root / "Требует_ручной_проверки")
    used: set[Path] = set()
    documents = []
    for row in rows:
        expected = root / row["destination"] if row["destination"] else None
        candidates = by_hash.get(row["sha256"], [])
        current = expected if expected in candidates and expected not in used else next((path for path in candidates if path not in used), None)
        if current is None:
            status = "missing" if row["destination"] else "unresolved"
            relative = ""
        else:
            used.add(current)
            relative = str(current.relative_to(root))
            parts = current.relative_to(root).parts
            status = "processed"
            if parts[0] == "Требует_ручной_проверки":
                status = "excluded_duplicate" if len(parts) > 1 and parts[1] == "Исключенные_повторы" else "pending"
        detail = details.get(current.name, {}) if current else {}
        fields = detail.get("review_fields", {})
        unreadable = status == "pending" and bool(fields) and not fields.get("date") and not fields.get("amount")
        documents.append({**row, "current_path": relative, "status": status,
                          "unreadable": unreadable, "reason": detail.get("reason", "")})
    counts = {status: sum(doc["status"] == status for doc in documents)
              for status in ("processed", "excluded_duplicate", "pending", "missing", "unresolved")}
    counts["unreadable"] = sum(doc["unreadable"] for doc in documents)
    report = {"input_count": len(rows), **counts, "complete": final and not any(counts[key] for key in ("pending", "missing", "unresolved")), "documents": documents}
    atomic_write(root / REPORT_NAME, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    lines = ["Итог обработки", f"Входных документов: {len(rows)}", f"Обработано: {counts['processed']}",
             f"Исключенных повторов: {counts['excluded_duplicate']}", f"Ручная проверка: {counts['pending']}",
             f"Из них без прочитанных даты и суммы: {counts['unreadable']}", f"Не распределено: {counts['unresolved']}",
             f"Не найдено в архиве: {counts['missing']}",
             "Статус: " + ("Завершено" if report["complete"] else "Не завершено"), ""]
    lines.extend(f"{doc['status']}: {Path(doc['source']).name} -> {doc['current_path'] or 'нет в архиве'}" for doc in documents)
    atomic_write(root / TEXT_NAME, "\n".join(lines) + "\n")
    print("[event-json] " + json.dumps({"type": "completion_report", "path": str(root / TEXT_NAME),
                                      **{key: value for key, value in report.items() if key != "documents"}}, ensure_ascii=False), flush=True)
    return report
