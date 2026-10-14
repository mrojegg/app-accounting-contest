#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
import unicodedata
from pathlib import Path

import sorting_file_ops
import sorting_windows_delivery
import sorting_manual_review
import sorting_review_fields
import sorting_completion_report
from sorting_text_utils import normalize_piece

import run_sorting_pipeline
import build_salary_tables


def emit_json_event(event_type: str, **payload: object) -> None:
    body = {"type": event_type, **payload}
    print(f"[event-json] {json.dumps(body, ensure_ascii=False, sort_keys=True)}")


def trim(value: str) -> str:
    return unicodedata.normalize("NFC", value).strip()


def rule_key(value: str) -> str:
    return trim(value).casefold()


def rules_file() -> Path:
    override = os.environ.get("SORTING_RULES_FILE")
    if override:
        return Path(override).expanduser().resolve()
    raise SystemExit("Не найден SORTING_RULES_FILE")


def manual_files(archive_root: Path) -> list[Path]:
    manual_root = archive_root / "Требует_ручной_проверки"
    if not manual_root.exists():
        return []
    return sorted(path for path in manual_root.iterdir() if path.is_file() and path.name != "_report.txt" and not path.name.startswith("."))


def remove_stale_report(archive_root: Path) -> None:
    sorting_manual_review.prune_manual_review_report(archive_root)


def destination_for(kind: str, archive_root: Path, office: str, category: str, subfolder: str) -> Path:
    normalized_kind = kind.lower()
    if normalized_kind == "salary":
        base = archive_root / office / "Зарплата"
    elif normalized_kind == "contractor":
        base = archive_root / office / category
    elif normalized_kind == "commission":
        base = archive_root / office / "Комиссии"
    elif normalized_kind == "taxes":
        base = archive_root / office / "Ндфл и Взносы"
    else:
        base = archive_root / office / category
    if subfolder:
        return base / subfolder
    return base


def normalized_entity(value: str) -> str:
    trimmed = trim(value)
    if not trimmed:
        return "ООО ВАША КОМПАНИЯ"
    if re.match(r"^(ООО|ИП|АО|ПАО)\s+", trimmed, flags=re.I):
        return trimmed
    return f"ООО {trimmed}"


def sanitize_filename(name: str) -> str:
    source = Path(name)
    stem = normalize_piece(source.stem, windows_safe=True) or "file"
    ext = normalize_piece(source.suffix.lstrip("."), windows_safe=True)
    return f"{stem}.{ext}" if ext else stem


def sanitize_salary_filename(name: str) -> str:
    source = Path(unicodedata.normalize("NFC", name))
    stem = source.stem.replace("ё", "е").replace("Ё", "Е")
    stem = re.sub(r'[<>:"/\\|?*]+', "_", stem)
    stem = re.sub(r"[^\w\s.-]+", "_", stem, flags=re.UNICODE)
    stem = re.sub(r"\s+", "_", stem)
    stem = re.sub(r"_+", "_", stem).strip("._") or "salary"
    ext = re.sub(r"[^A-Za-z0-9]+", "", source.suffix.lstrip(".")).lower() or "pdf"
    return f"{stem}.{ext}"


def replace_bullet_section(block: str, header: str, lines: list[str]) -> str:
    pattern = rf"(?ms)^{re.escape(header)}:\n(?:[ \t]*\n|[ \t]*-.*\n)*"
    replacement = f"{header}:\n" + "\n".join(lines) + "\n\n"
    if re.search(pattern, block):
        return re.sub(pattern, replacement, block, count=1)
    if not block.endswith("\n"):
        block += "\n"
    return block + "\n" + replacement


def unique_preserving_order(lines: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for line in lines:
        key = line.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(line)
    return result


def extract_bullet_lines(block: str, header: str) -> list[str]:
    pattern = rf"(?ms)^{re.escape(header)}:\n((?:[ \t]*\n|[ \t]*-.*\n)*)"
    match = re.search(pattern, block)
    if not match:
        return []
    return [line.strip() for line in match.group(1).splitlines() if line.strip()]


def parse_office_block(block: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current_header = ""
    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("### Офис "):
            continue
        if line.endswith(":") and not line.startswith("- "):
            current_header = line[:-1]
            sections.setdefault(current_header, [])
            continue
        if current_header:
            sections[current_header].append(line)
    return sections


def update_office_section(content: str, office: str, entity: str, kind: str, category: str, label: str) -> str:
    lines = content.splitlines()
    header = f"### Офис {office}"
    start = next((index for index, line in enumerate(lines) if line.strip() == header), None)
    if start is None:
        return content
    end = len(lines)
    for index in range(start + 1, len(lines)):
        stripped = lines[index].strip()
        if stripped.startswith("### Офис ") or stripped.startswith("## "):
            end = index
            break

    block = lines[start:end]

    def section_bounds(section_name: str) -> tuple[int, int] | None:
        section_header = f"{section_name}:"
        section_start = next(
            (index for index, line in enumerate(block) if line.strip() == section_header),
            None,
        )
        if section_start is None:
            return None
        section_end = len(block)
        for index in range(section_start + 1, len(block)):
            stripped = block[index].strip()
            if stripped and not stripped.startswith("- ") and stripped.endswith(":"):
                section_end = index
                break
        return section_start, section_end

    def insertion_index(section_end: int) -> int:
        index = section_end
        while index > 0 and not block[index - 1].strip():
            index -= 1
        return index

    if entity.strip():
        bounds = section_bounds("Юрлицо")
        if bounds:
            section_start, section_end = bounds
            entity_line = f"- `{normalized_entity(entity)}`"
            current_line = next(
                (index for index in range(section_start + 1, section_end) if block[index].strip().startswith("- ")),
                None,
            )
            if current_line is None:
                block.insert(insertion_index(section_end), entity_line)
            elif rule_key(block[current_line]) != rule_key(entity_line):
                block[current_line] = entity_line

    normalized_category = trim(category)
    if normalized_category:
        bounds = section_bounds("Разрешенные категории по умолчанию")
        if bounds:
            section_start, section_end = bounds
            categories = {
                rule_key(block[index].strip().removeprefix("- ").strip().strip("`"))
                for index in range(section_start + 1, section_end)
                if block[index].strip().startswith("- ")
            }
            if normalized_category.casefold() not in categories:
                block.insert(insertion_index(section_end), f"- `{normalized_category}`")

    normalized_label = trim(label)
    if kind == "salary" and normalized_label:
        bounds = section_bounds("Сотрудники")
        if bounds:
            section_start, section_end = bounds
            employees = {
                rule_key(block[index].strip().removeprefix("- "))
                for index in range(section_start + 1, section_end)
                if block[index].strip().startswith("- ")
            }
            if normalized_label.casefold() not in employees:
                block.insert(insertion_index(section_end), f"- {normalized_label}")

    if kind in {"contractor", "commission", "taxes", "other"} and normalized_label and normalized_category:
        bounds = section_bounds("Контрагенты")
        if bounds:
            section_start, section_end = bounds
            matching_legacy_line: int | None = None
            already_known = False
            for index in range(section_start + 1, section_end):
                stripped = block[index].strip()
                match = re.match(r"^-\s*`?([^`:]+)`?\s*:\s*(.+)$", stripped)
                if not match or rule_key(match.group(1)) != normalized_category.casefold():
                    continue
                payload = match.group(2).strip()
                main_name = payload.split("|", 1)[0].strip()
                values = [main_name]
                alias_match = re.search(r"(?:^|\|)\s*алиасы\s*:\s*(.+)$", payload, flags=re.I)
                if alias_match:
                    values.extend(item.strip() for item in alias_match.group(1).split(",") if item.strip())
                elif "|" not in payload:
                    values = [item.strip() for item in payload.split(",") if item.strip()]
                    matching_legacy_line = index
                if any(rule_key(value) == normalized_label.casefold() for value in values):
                    already_known = True
                    break
            if not already_known:
                if matching_legacy_line is not None:
                    block[matching_legacy_line] = f"{block[matching_legacy_line]}, {normalized_label}"
                else:
                    new_rule = (
                        f"- `{normalized_category}`: {normalized_label} | "
                        f"папка: нет | алиасы: {normalized_label}"
                    )
                    block.insert(insertion_index(section_end), new_rule)

    rebuilt_lines = lines[:start] + block + lines[end:]
    if rebuilt_lines == lines:
        return content
    return "\n".join(rebuilt_lines).rstrip() + "\n"


def save_learning(office: str, entity: str, kind: str, category: str, label: str) -> None:
    path = rules_file()
    content = path.read_text(encoding="utf-8")
    updated = update_office_section(content, office, entity, kind, category, label)
    if updated == content:
        return
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as staged:
        staged.write(updated)
        temporary = Path(staged.name)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    run_sorting_pipeline.sort_documents.refresh_runtime_config()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ручное решение по файлу из папки ручной проверки.")
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--file-name", required=True)
    parser.add_argument("--action", choices=["move", "delete", "exclude_duplicate"], required=True)
    parser.add_argument("--kind", choices=["salary", "contractor", "commission", "taxes", "other"], default="other")
    parser.add_argument("--office", default="")
    parser.add_argument("--entity", default="")
    parser.add_argument("--category", default="Прочее")
    parser.add_argument("--label", default="")
    parser.add_argument("--subfolder", default="")
    parser.add_argument("--save-to-rules", action="store_true")
    parser.add_argument("--payment-date", default="")
    parser.add_argument("--payment-amount", default="")
    args = parser.parse_args(argv)

    archive_root = args.archive_root.expanduser().resolve()
    manual_root = archive_root / "Требует_ручной_проверки"
    source = manual_root / args.file_name
    if source.parent.resolve() != manual_root.resolve() or not source.is_file():
        raise SystemExit(f"Не найден файл ручной проверки: {source}")

    office = trim(args.office)
    entity = trim(args.entity)
    category = trim(args.category) or "Прочее"
    label = trim(args.label)
    subfolder = trim(args.subfolder)
    confirmed = None
    if args.action == "move" and (args.payment_date or args.payment_amount):
        try:
            confirmed = sorting_review_fields.validate_fields(label, args.payment_date, args.payment_amount)
        except ValueError as error:
            raise SystemExit(f"Проверьте реквизиты: {error}. Файл оставлен в ручной проверке.") from error

    if args.action == "delete":
        source.unlink()
    elif args.action == "exclude_duplicate":
        target_root = manual_root / "Исключенные_повторы"
        destination = sorting_file_ops.unique_destination(target_root / sanitize_salary_filename(source.name))
        destination.parent.mkdir(parents=True, exist_ok=True)
        source.rename(destination)
        emit_json_event("salary_duplicate_excluded", source=args.file_name, destination=str(destination))
    else:
        if not office:
            raise SystemExit("Для переноса нужен офис.")
        if not office.isdigit() or any(value in {".", ".."} or "/" in value or "\\" in value for value in (category, subfolder)):
            raise SystemExit("Недопустимый путь назначения.")
        target_root = destination_for(args.kind, archive_root, office, category, subfolder)
        safe_name = sanitize_salary_filename(source.name) if args.kind == "salary" else sanitize_filename(source.name)
        if args.kind == "salary":
            if not label:
                raise SystemExit("Для зарплатного чека нужно ФИО сотрудника.")
            parsed = (label, confirmed["date"], build_salary_tables.Decimal(confirmed["amount"])) if confirmed else build_salary_tables.parse_payment_name(source)
            if parsed is None:
                text = run_sorting_pipeline.sort_documents.file_text(source)
                date = build_salary_tables.sorting_naming.extract_payment_execution_date(text) or build_salary_tables.sorting_naming.extract_first_date(text)
                amount = build_salary_tables.amount_from_text(source)
                if not date or amount is None:
                    raise SystemExit("Не удалось прочитать дату или сумму чека. Файл оставлен в ручной проверке.")
            else:
                _, date, amount = parsed
            build_salary_tables.parse_payment_date(date)
            amount_token = f"{amount:.2f}".replace(".", "-")
            safe_name = sanitize_salary_filename(f"{label}_{date}_{amount_token}.pdf")
        elif confirmed:
            safe_name = sanitize_filename(f"{label}_{confirmed['date']}_{confirmed['amount'].replace('.', '-')}{source.suffix}")
        if args.save_to_rules and label:
            save_learning(office, entity, args.kind, category, label)
            emit_json_event("manual_rule_saved", office=office, entity=entity, kind=args.kind, category=category, label=label)
        destination = sorting_file_ops.unique_destination(target_root / safe_name)
        if confirmed:
            sorting_review_fields.save_confirmation(archive_root, source, confirmed, destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        source.rename(destination)
        emit_json_event("manual_file_moved", source=args.file_name, destination=str(destination))

    remove_stale_report(archive_root)
    pending = manual_files(archive_root)
    emit_json_event("manual_review_remaining", archive_root=str(archive_root), remaining=len(pending))

    if not pending:
        windows_zip = run_sorting_pipeline.run_deferred_postprocess(archive_root)
        emit_json_event("manual_finalize_complete", archive_root=str(archive_root))
    else:
        print(f"В ручной проверке осталось {len(pending)} файлов.")
        sorting_completion_report.write_report(archive_root)
        emit_json_event("manual_review_pending", archive_root=str(archive_root), pending_manual_review=len(pending))
        print("[phase] windows-export")
        emit_json_event("phase", phase="windows-export")
        windows_zip = sorting_windows_delivery.create_windows_delivery_zip(archive_root)
        print(f"Windows ZIP: {windows_zip}")
        emit_json_event("windows_export", path=str(windows_zip))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
