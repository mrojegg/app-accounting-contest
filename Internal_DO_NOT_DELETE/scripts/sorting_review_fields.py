from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re

from sorting_manual_review import atomic_write

CONFIRMED_NAME = ".confirmed_fields.json"


def fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_fields(label: str, date: str, amount: str) -> dict[str, str]:
    label = label.strip()
    if not label or any(char in label for char in "\r\n\x00"):
        raise ValueError("Укажите сотрудника или получателя платежа.")
    date = datetime.strptime(date.strip().replace(".", "-"), "%d-%m-%Y").strftime("%d-%m-%Y")
    amount = amount.strip().replace(" ", "").replace("\u00a0", "").replace(",", ".")
    if not re.fullmatch(r"\d+(?:\.\d{1,2})?", amount):
        raise ValueError("Сумма должна быть положительным числом, не более двух знаков после запятой.")
    try:
        value = Decimal(amount)
        if not value.is_finite() or value <= 0:
            raise ValueError("Сумма должна быть больше нуля.")
    except InvalidOperation as error:
        raise ValueError("Некорректная сумма.") from error
    return {"label": label, "date": date, "amount": f"{value:.2f}"}


def confirmed_fields(path: Path) -> dict[str, str]:
    for root in path.resolve().parents:
        store = root / CONFIRMED_NAME
        if store.exists():
            # A damaged confirmation store must not silently fall back to OCR.
            data = json.loads(store.read_text(encoding="utf-8"))
            digest = fingerprint(path)
            item = data.get(confirmation_key(root, path))
            if item:
                if item["sha256"] != digest:
                    raise ValueError(f"Подтвержденный документ был изменен: {path.name}")
                return validate_fields(**item["fields"])
            matches = [item["fields"] for item in data.values() if item["sha256"] == digest]
            unique = {json.dumps(item, sort_keys=True) for item in matches}
            if len(unique) > 1:
                raise ValueError(f"После переименования нужно проверить реквизиты: {path.name}")
            return validate_fields(**matches[0]) if matches else {}
    return {}


def confirmation_key(root: Path, path: Path) -> str:
    parts = path.resolve().relative_to(root.resolve()).parts
    if parts and parts[0] == "Исходные_чеки":
        parts = parts[1:]
    return str(Path(*parts))


def save_confirmation(root: Path, path: Path, fields: dict[str, str], destination: Path | None = None) -> None:
    store = root / CONFIRMED_NAME
    data = json.loads(store.read_text(encoding="utf-8")) if store.exists() else {}
    data[confirmation_key(root, destination or path)] = {"sha256": fingerprint(path), "fields": validate_fields(**fields)}
    atomic_write(store, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def suggested_fields(path: Path, core) -> dict[str, str]:
    import sorting_naming
    text = core.file_text(path)
    normalized = core.normalize_text(text)
    token = core.extract_payment_order_amount(normalized) or core.extract_bank_order_amount(normalized)
    date = sorting_naming.extract_payment_execution_date(text) or sorting_naming.extract_first_date(text)
    return {
        "label": core.bank_payment_recipient(normalized),
        "date": date or "",
        "amount": token.replace(" ", "").replace("-", ".", 1) if token else "",
    }


def prepare_review(path: Path, result, archive_root: Path, core):
    fields = suggested_fields(path, core)
    result.review_fields = fields
    financial = result.category in {"Зарплата", "Комиссии", "Налоги", "Взносы", "Ндфл и Взносы"}
    invalid = False
    if financial:
        try:
            validate_fields(fields["label"] or "Платеж", fields["date"], fields["amount"])
        except ValueError:
            invalid = True
    if invalid:
        result.requires_manual_review = True
        result.destination = archive_root / "Требует_ручной_проверки"
        result.reason += "; проверьте дату и сумму платежа"
    return result
