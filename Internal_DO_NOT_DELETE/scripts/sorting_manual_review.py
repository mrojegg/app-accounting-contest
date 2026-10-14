from __future__ import annotations

from pathlib import Path
import json
import os
import tempfile
import unicodedata

from sorting_models import Classification

METADATA_NAME = ".manual_review.json"


def atomic_write(path: Path, text: str) -> None:
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(text)
        staged = Path(handle.name)
    try:
        os.replace(staged, path)
    finally:
        staged.unlink(missing_ok=True)


def load_manual_review_metadata(manual_root: Path) -> dict[str, dict]:
    try:
        data = json.loads((manual_root / METADATA_NAME).read_text(encoding="utf-8"))
        if isinstance(data, dict) and all(isinstance(value, dict) for value in data.values()):
            return {unicodedata.normalize("NFC", key): value for key, value in data.items()}
    except (OSError, ValueError):
        pass
    # Older archives only contain the human-readable report.
    report = manual_root / "_report.txt"
    if not report.exists():
        return {}
    details = {}
    for block in report.read_text(encoding="utf-8").split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line and not line.startswith("- "))
        name = fields.get("Файл")
        if not name:
            continue
        reason = fields.get("Причина", "")
        try:
            confidence = int(fields.get("Уверенность", "0%").rstrip("%"))
        except ValueError:
            confidence = 0
        details[unicodedata.normalize("NFC", name)] = {
            "office": fields.get("Офис", "").replace("?", ""),
            "category": fields.get("Категория", "").replace("?", ""),
            "entity": fields.get("Юрлицо", "").replace("?", ""),
            "reason": reason,
            "salary_duplicate": "Возможный повтор зарплаты" in reason,
            "confidence": confidence,
            "trace": [line[2:] for line in block.splitlines() if line.startswith("- ")],
        }
    return details


def prune_manual_review_report(archive_root: Path) -> None:
    manual_root = archive_root / "Требует_ручной_проверки"
    if not manual_root.exists():
        return
    details = load_manual_review_metadata(manual_root)
    items = []
    for path in sorted(manual_root.iterdir()):
        detail = details.get(unicodedata.normalize("NFC", path.name))
        if not path.is_file() or detail is None:
            continue
        items.append((path, Classification(
            destination=manual_root, office=detail.get("office"), category=detail.get("category"),
            entity=detail.get("entity"), reason=detail.get("reason", ""), new_name=path.name,
            confidence=detail.get("confidence", 0), requires_manual_review=True,
            trace=detail.get("trace", []), salary_duplicate=detail.get("salary_duplicate", False),
            review_fields=detail.get("review_fields", {}),
        )))
    write_manual_review_report(archive_root, items, False, enabled=(manual_root / "_report.txt").exists())


def render_manual_review_report(items: list[tuple[Path, Classification]]) -> str:
    report_lines = [
        "Отчет по документам, требующим ручной проверки",
        "",
    ]
    for source, result in items:
        report_lines.append(f"Файл: {source.name}")
        report_lines.append(f"Уверенность: {result.confidence}%")
        report_lines.append(f"Офис: {result.office or '?'}")
        report_lines.append(f"Категория: {result.category or '?'}")
        report_lines.append(f"Юрлицо: {result.entity or '?'}")
        report_lines.append(f"Причина: {result.reason}")
        if result.trace:
            report_lines.append("Сигналы:")
            for item in result.trace[:8]:
                report_lines.append(f"- {item}")
        report_lines.append("")
    return "\n".join(report_lines).strip() + "\n"


def write_manual_review_report(
    archive_root: Path,
    items: list[tuple[Path, Classification]],
    dry_run: bool,
    *,
    enabled: bool = True,
) -> None:
    report_path = archive_root / "Требует_ручной_проверки" / "_report.txt"
    if dry_run:
        print(f"[dry-run] write report {report_path}")
        return
    metadata_path = report_path.with_name(METADATA_NAME)
    if not items:
        report_path.unlink(missing_ok=True)
        metadata_path.unlink(missing_ok=True)
        return
    report_path.parent.mkdir(parents=True, exist_ok=True)
    details = {unicodedata.normalize("NFC", source.name): {
        "office": result.office or "", "category": result.category or "", "entity": result.entity or "",
        "reason": result.reason, "confidence": result.confidence, "trace": result.trace,
        "salary_duplicate": result.salary_duplicate,
        "review_fields": result.review_fields,
    } for source, result in items}
    atomic_write(metadata_path, json.dumps(details, ensure_ascii=False, indent=2) + "\n")
    if enabled:
        atomic_write(report_path, render_manual_review_report(items))
    else:
        report_path.unlink(missing_ok=True)
