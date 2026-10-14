from __future__ import annotations

import re
from datetime import date as calendar_date
from pathlib import Path
from typing import Callable

from sorting_text_utils import declined_person_name_in_text, business_document_text

try:
    from rapidfuzz import fuzz
except Exception:
    fuzz = None

RU_MONTHS = {
    "января": "01",
    "февраля": "02",
    "марта": "03",
    "апреля": "04",
    "мая": "05",
    "июня": "06",
    "июля": "07",
    "августа": "08",
    "сентября": "09",
    "октября": "10",
    "ноября": "11",
    "декабря": "12",
}

KNOWN_FILE_EXTENSIONS = (
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".xlsm", ".xlsb", ".png", ".jpg", ".jpeg",
    ".tif", ".tiff", ".bmp", ".gif", ".heic", ".webp", ".avif", ".jfif", ".jp2", ".j2k",
    ".txt", ".csv", ".tsv", ".json", ".xml", ".html", ".htm", ".eml", ".rtf", ".md",
    ".odt", ".ods", ".odp", ".msg",
)


def split_known_suffix(name: str) -> tuple[str, str]:
    lower_name = name.lower()
    for suffix in KNOWN_FILE_EXTENSIONS:
        if lower_name.endswith(suffix):
            return name[:-len(suffix)], name[-len(suffix):]
    path = Path(name)
    return path.stem, path.suffix


def extract_first_date(text: str) -> str | None:
    match = re.search(r"\b(\d{2}\.\d{2}\.\d{4})\b", text)
    if not match:
        return None
    return match.group(1).replace(".", "-")


def extract_payment_execution_date(text: str) -> str | None:
    normalized = text.lower().replace("ё", "е")
    numeric = r"(\d{1,2})[.]([0-1]?\d)[.](\d{4})"
    words = r"(\d{1,2})\s+(" + "|".join(RU_MONTHS) + r")\s+(\d{4})"
    # PDF text order differs between banks: the stamp date can precede its label.
    patterns = [
        rf"\bисполнено\s*[:\-]?\s*{numeric}\b",
        rf"\bисполнено\s*[:\-]?\s*{words}\b",
        rf"\b{words}\s+исполнено\b",
        rf"\b{numeric}\s+исполнено\b",
        rf"списано\s+со\s+сч\.?\s*плат\.?\s*:?\s*{numeric}\b",
        rf"\b{numeric}\s+списано\s+со\s+сч\.?\s*плат\.?",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, normalized):
            day, month, year = match.groups()
            try:
                value = calendar_date(int(year), int(RU_MONTHS.get(month, month)), int(day))
            except ValueError:
                continue
            return value.strftime("%d-%m-%Y")
    return None


def extract_payment_date(text: str) -> str | None:
    return extract_payment_execution_date(text) or extract_first_date(text)


def extract_date_from_name(name: str) -> str | None:
    match = re.search(r"(\d{2}-\d{2}-\d{4})", name)
    if match:
        return match.group(1)
    match = re.search(r"(\d{2}\.\d{2}\.\d{4})", name)
    if match:
        return match.group(1).replace(".", "-")
    return None


def extract_vtb_filename_metadata(name: str, *, normalize_piece: Callable[[str], str]) -> dict[str, str | None] | None:
    normalized = Path(name).name
    patterns = [
        (r"^VTB_Payment_commission_(\d+)_(\d{2}\.\d{2}\.\d{4})(?:_(\d+))?_additional_filter\.pdf$", "Комиссия_ВТБ"),
        (r"^VTB_Bank_order_(\d+)_(\d{2}\.\d{2}\.\d{4})(?:_(\d+))?_additional_filter\.pdf$", "Банковский_ордер_ВТБ"),
    ]
    for pattern, identifier in patterns:
        match = re.match(pattern, normalized, re.IGNORECASE)
        if not match:
            continue
        number, raw_date, trailing = match.groups()
        amount = None
        if trailing and re.fullmatch(r"\d{1,6}", trailing):
            amount = None
        return {
            "identifier": identifier,
            "number": normalize_piece(number),
            "date": raw_date.replace(".", "-"),
            "amount": amount,
        }
    return None


def extract_amount_from_name(name: str) -> str | None:
    match = re.search(r"_(\d+(?:-\d{2}|,\d{2}))(?:_(\d+))?(?=\.[^.]+$)", name)
    if not match:
        return None
    amount = match.group(1)
    if re.fullmatch(r"\d+", amount):
        return None
    return amount.replace(",", "-")


def extract_numeric_suffix(name: str) -> str | None:
    match = re.search(r"_(\d+)(?=\.[^.]+$)", name)
    return match.group(1) if match else None


def extract_payment_order_number(text: str, name: str, *, normalize_text: Callable[[str], str], normalize_piece: Callable[[str], str]) -> str | None:
    patterns = [r"платежное поручение\s*[n№]\s*(\d{1,6})\b(?!\.)"]
    normalized = normalize_text(text)
    for pattern in patterns:
        match = re.search(pattern, normalized, re.IGNORECASE)
        if match:
            return normalize_piece(match.group(1))

    vtb_meta = extract_vtb_filename_metadata(name, normalize_piece=normalize_piece)
    if vtb_meta and vtb_meta["number"]:
        return normalize_piece(str(vtb_meta["number"]))

    old_style = re.match(
        r"^Платежное_поручение_(?!Аванс_|Заработная_плата_|Увольнение_|Отпускные_)(.+)_(\d+|без_номера)_(\d{2}-\d{2}-\d{4}|без_даты)_(\d+(?:-\d{2}|,\d{2}))\.pdf$",
        Path(name).name,
        re.IGNORECASE,
    )
    if old_style and old_style.group(2) != "без_номера":
        return old_style.group(2)

    return extract_numeric_suffix(Path(name).name)


def extract_bank_order_number(text: str, name: str, *, normalize_piece: Callable[[str], str]) -> str | None:
    vtb_meta = extract_vtb_filename_metadata(name, normalize_piece=normalize_piece)
    if vtb_meta and vtb_meta["number"]:
        return normalize_piece(str(vtb_meta["number"]))
    return extract_numeric_suffix(Path(name).name)


def extract_invoice_date(text: str, name: str) -> str | None:
    normalized = text.lower().replace("ё", "е")
    patterns = [
        r"счет(?:\s+на\s+оплату)?\s*[n№]?\s*[a-zа-я0-9/-]*\s*от\s*(\d{2}\.\d{2}\.\d{4})",
        r"упд(?:\s*\(статус\s*\d+\))?\s*[n№]?\s*[a-zа-я0-9/-]*\s*от\s*(\d{2}\.\d{2}\.\d{4})",
        r"акт\s*[n№]?\s*[a-zа-я0-9/-]*\s*от\s*(\d{2}\.\d{2}\.\d{4})",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized, re.IGNORECASE)
        if match:
            return match.group(1).replace(".", "-")
    month_words = re.search(
        r"(?:счет(?:\s+на\s+оплату)?|упд(?:\s*\(статус\s*\d+\))?|акт)\s*[n№]?\s*[a-zа-я0-9/-]*\s*от\s*(\d{1,2})\s+([а-я]+)\s+(\d{4})",
        normalized,
        re.IGNORECASE,
    )
    if month_words:
        day, month_name, year = month_words.groups()
        month = RU_MONTHS.get(month_name)
        if month:
            return f"{int(day):02d}-{month}-{year}"
    date = extract_date_from_name(name)
    if date:
        return date
    match = re.search(r"\b(\d{2}\.\d{2}\.\d{4})\b", text)
    if match:
        return match.group(1).replace(".", "-")
    match = re.search(r"(\d{4}-\d{2}-\d{2})", name)
    if match:
        raw = match.group(1)
        return f"{raw[8:10]}-{raw[5:7]}-{raw[0:4]}"
    return None


def canonical_employee_name(text: str, *, office_people: dict[str, list[str]], normalize_text: Callable[[str], str]) -> str | None:
    for people in office_people.values():
        for person in people:
            if normalize_text(person) in text or declined_person_name_in_text(person, text):
                return person
    return None


def extract_invoice_counterparty(
    text: str,
    name: str,
    *,
    office_contractors: dict[str, dict[str, list[str]]],
    normalize_text: Callable[[str], str],
    normalize_piece: Callable[[str], str],
) -> str | None:
    normalized = normalize_text(business_document_text(text))
    supplier = re.search(
        r'(?:поставщик|исполнитель|продавец)(?:\s*\([^)]*\))?\s*:\s*(?:ооо|ао|пао|ип)\s+["«]?(.+?)["»]?(?=\s*,|\s+инн|\s+кпп|\s+покупатель|\s+заказчик|$)',
        normalized, re.I,
    )
    if supplier:
        return normalize_piece(supplier.group(1).strip(' "«»'))
    for keywords_by_category in office_contractors.values():
        for keywords in keywords_by_category.values():
            for keyword in keywords:
                if keyword in normalized:
                    return normalize_piece(keyword)
            if fuzz is not None:
                for keyword in keywords:
                    if len(keyword) >= 6 and fuzz.partial_ratio(keyword, normalized) >= 90:
                        return normalize_piece(keyword)

    generic_patterns = [
        r'поставщик.*?(?:ооо|ао|пао|ип)\s+"?([а-яa-z0-9 .,-]+?)"?(?:\s*,|\s+инн|\s+кпп|\s+покупатель|\s+основание)',
        r'исполнитель.*?(?:ооо|ао|пао|ип)\s+"?([а-яa-z0-9 .,-]+?)"?(?:\s*,|\s+инн|\s+кпп|\s+заказчик|\s+основание)',
        r'продавец.*?(?:ооо|ао|пао|ип)\s+"?([а-яa-z0-9 .,-]+?)"?(?:\s*,|\s+инн|\s+кпп|\s+покупатель|\s+основание)',
    ]
    for pattern in generic_patterns:
        match = re.search(pattern, normalized, re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        candidate = normalize_piece(match.group(1))
        if candidate in {"пример", "образец"}:
            continue
        if candidate:
            return candidate

    if "список перечисляемой в банк зарплаты" in normalized:
        match = re.search(r"№\s*([a-zа-я0-9-]+)\s*от\s*(\d{2}\.\d{2}\.\d{4})", normalized, re.IGNORECASE)
        if match:
            return normalize_piece(f"список_получателей_{match.group(1)}")

    stem = Path(name).stem
    old_style = re.match(
        r"^Счет_(.+?)_([^_]+)_(\d{4}-\d{2}-\d{2}|\d{2}-\d{2}-\d{4})(?:_(\d+(?:-\d{2}|,\d{2})))?$",
        stem,
        re.IGNORECASE,
    )
    if old_style:
        return normalize_piece(old_style.group(1))
    return None


def extract_invoice_number(text: str, name: str, *, normalize_text: Callable[[str], str], normalize_piece: Callable[[str], str]) -> str | None:
    normalized = normalize_text(text)
    patterns = [
        r"счет(?:\s+на\s+оплату)?\s*[n№]\s*([a-zа-я0-9/-]+)",
        r"счет(?:\s+на\s+оплату)?\s+([a-zа-я0-9/-]+)\s+от\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized, re.IGNORECASE)
        if match:
            return normalize_piece(match.group(1))

    stem = Path(name).stem
    old_style = re.match(
        r"^Счет_(.+?)_([^_]+)_(\d{4}-\d{2}-\d{2}|\d{2}-\d{2}-\d{4})(?:_(\d+(?:-\d{2}|,\d{2})))?$",
        stem,
        re.IGNORECASE,
    )
    if old_style:
        return old_style.group(2)
    return None


def looks_like_bank_export_payment_name(name: str) -> bool:
    stem = Path(name).stem.lower().replace(" ", "_")
    has_bank_fields = "банк_получателя" in stem or "получатель_инн" in stem
    has_account_fields = "сч" in stem or "счет" in stem or re.search(r"\b\d{20}\b", stem) is not None
    return bool(has_bank_fields and has_account_fields)


def extract_known_counterparty_from_rules(
    text: str,
    name: str,
    office: str | None,
    category: str | None,
    *,
    office_contractors: dict[str, dict[str, list[str]]],
    normalize_text: Callable[[str], str],
    normalize_piece: Callable[[str], str],
) -> str | None:
    haystack = normalize_text(f"{business_document_text(text)} {name}")
    keyword_groups: list[list[str]] = []

    def add_office_rules(office_rules: dict[str, list[str]]) -> None:
        if category and category in office_rules:
            keyword_groups.append(office_rules[category])
        for rule_category, keywords in office_rules.items():
            if rule_category != category:
                keyword_groups.append(keywords)

    if office and office in office_contractors:
        add_office_rules(office_contractors[office])
    for office_key, office_rules in office_contractors.items():
        if office_key != office:
            add_office_rules(office_rules)

    seen: set[str] = set()
    for keywords in keyword_groups:
        for keyword in sorted(keywords, key=len, reverse=True):
            if not keyword or keyword in seen:
                continue
            seen.add(keyword)
            if keyword in haystack:
                candidate = normalize_piece(keyword)
                if candidate:
                    return candidate
    return None


def contractor_payment_identifier(
    text: str,
    name: str,
    office: str | None,
    category: str | None,
    fallback: str,
    *,
    office_contractors: dict[str, dict[str, list[str]]],
    bank_payment_recipient: Callable[[str], str],
    bank_name: Callable[[str], str],
    normalize_text: Callable[[str], str],
    normalize_piece: Callable[[str], str],
) -> str:
    counterparty = bank_payment_recipient(text)
    if not counterparty and normalize_text(text).startswith("счет"):
        counterparty = extract_invoice_counterparty(
            text,
            name,
            office_contractors=office_contractors,
            normalize_text=normalize_text,
            normalize_piece=normalize_piece,
        )
    if not counterparty:
        counterparty = extract_known_counterparty_from_rules(
            text,
            name,
            office,
            category,
            office_contractors=office_contractors,
            normalize_text=normalize_text,
            normalize_piece=normalize_piece,
        )
    if not counterparty and text.strip():
        counterparty = bank_name(text)
    return normalize_piece(counterparty or fallback) or "Контрагент"


def normalize_date_token(value: str) -> str:
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return f"{value[8:10]}-{value[5:7]}-{value[0:4]}"
    if re.fullmatch(r"\d{2}-\d{2}-\d{4}", value):
        return value
    return value


def normalize_structured_filename(name: str, *, normalize_piece: Callable[[str], str]) -> str:
    stem, suffix = split_known_suffix(Path(name).name)

    patterns = [
        r"^Платежное_поручение_(.+?)_(\d{2}-\d{2}-\d{4}|без_даты)(?:_(\d+|без_номера))?_(\d+(?:-\d{2}|,\d{2}|без_суммы))$",
        r"^Банковский_ордер_(.+?)_(\d{2}-\d{2}-\d{4}|без_даты)(?:_(\d+|без_номера))?_(\d+(?:-\d{2}|,\d{2}|без_суммы))$",
        r"^Счет_(.+?)_([^_]+)_(\d{4}-\d{2}-\d{2}|\d{2}-\d{2}-\d{4})(?:_(\d+(?:-\d{2}|,\d{2})))?$",
        r"^(.+?)_(\d{2}-\d{2}-\d{4}|без_даты)(?:_([a-zа-я0-9/-]+|без_номера))?_(\d+(?:-\d{2}|,\d{2}|без_суммы))$",
    ]
    for pattern in patterns:
        match = re.match(pattern, stem, re.IGNORECASE)
        if not match:
            continue
        identifier, date, number, amount = match.groups()
        clean_identifier = normalize_piece(identifier) or "Документ"
        parts = [clean_identifier, normalize_date_token(date)]
        if number and number != "без_номера":
            clean_number = normalize_piece(number)
            if clean_number:
                parts.append(clean_number)
        elif number == "без_номера":
            parts.append(number)
        if amount:
            clean_amount = amount.replace(",", "-")
            if clean_amount:
                parts.append(clean_amount)
        candidate = "_".join(parts)
        candidate = _dedupe_filename_chunks(candidate)
        if len(candidate) > 120:
            candidate = "_".join(parts[:2] + parts[-2:])
            candidate = _dedupe_filename_chunks(candidate)
        return f"{candidate}{suffix}"

    fallback = normalize_piece(stem) or "Документ"
    fallback = _dedupe_filename_chunks(fallback)
    if len(fallback) > 120:
        fallback = fallback[:120].strip("._") or "Документ"
        fallback = _dedupe_filename_chunks(fallback)
    return f"{fallback}{suffix}"


def _dedupe_filename_chunks(value: str) -> str:
    cleaned_value = re.sub(r"[.]{2,}", ".", value)
    if cleaned_value.count("без_суммы") > 1:
        cleaned_value = re.sub(r"(_без_номера_без_суммы).*", r"\1", cleaned_value, count=1)
        cut = cleaned_value.find("без_суммы")
        if cut != -1:
            cleaned_value = cleaned_value[:cut + len("без_суммы")]
    repeated_tail = re.search(r"(.+?_без_номера_без_суммы)(?:.+_без_номера_без_суммы.*)$", cleaned_value)
    if repeated_tail:
        cleaned_value = repeated_tail.group(1)
    parts = [part for part in cleaned_value.split("_") if part]
    compact: list[str] = []
    for part in parts:
        if compact and part == compact[-1]:
            continue
        compact.append(part)

    joined = "_".join(compact)
    repeated_phrase = re.match(r"^(.+?)(?:_\1)+$", joined)
    if repeated_phrase:
        joined = repeated_phrase.group(1)
    half = len(compact) // 2
    if half >= 3 and compact[:half] == compact[half:half * 2]:
        joined = "_".join(compact[:half])

    joined = re.sub(r"(_без_суммы(?:\.[^_]+)*){2,}", "_без_суммы", joined)
    joined = re.sub(r"(_без_номера){2,}", "_без_номера", joined)
    joined = re.sub(r"(_без_даты){2,}", "_без_даты", joined)
    joined = re.sub(r"(_без_суммы)\.\d+$", r"\1", joined)
    duplicated_tail = re.match(r"^(.+?_без_номера_без_суммы)(?:_.+)?_\1$", joined)
    if duplicated_tail:
        joined = duplicated_tail.group(1)
    joined = re.sub(r"_+", "_", joined).strip("._")
    return joined or value


def extract_payment_order_amount(
    text: str,
    *,
    strip_full_dates: Callable[[str], str],
    normalize_amount_token: Callable[[str], str],
    extract_amount_from_words: Callable[[str], str | None],
) -> str | None:
    search_area = strip_full_dates(text.split("отметки банка")[0])
    explicit_patterns = [
        r"сумма[^0-9]{0,40}(\d{1,3}(?: \d{3})*[.,-]\d{2}|\d+[.,-]\d{2})",
        r"на сумму[^0-9]{0,40}(\d{1,3}(?: \d{3})*[.,-]\d{2}|\d+[.,-]\d{2})",
    ]
    for pattern in explicit_patterns:
        match = re.search(pattern, search_area, re.IGNORECASE)
        if match:
            amount = normalize_amount_token(match.group(1))
            if amount:
                return amount
    words_amount = extract_amount_from_words(search_area)
    if words_amount:
        return words_amount
    matches = re.findall(r"(?:^| )(\d{1,3}(?: \d{3})*-\d{2}|\d+-\d{2}|\d{1,3}(?: \d{3})*[.,]\d{2}|\d+[.,]\d{2})\b", search_area)
    for candidate in reversed(matches):
        amount = normalize_amount_token(candidate)
        if amount:
            return amount
    return None


def extract_bank_order_amount(
    text: str,
    *,
    strip_full_dates: Callable[[str], str],
    normalize_amount_token: Callable[[str], str],
    extract_amount_from_words: Callable[[str], str | None],
) -> str | None:
    search_space = strip_full_dates(text.replace("\xa0", " "))
    patterns = [
        r"(?:\n|^)\s*сумма\s*\n(?:.*\n){0,6}?(\d{1,3}(?: \d{3})*-\d{2}|\d+-\d{2})",
        r"сумма[^0-9]{0,60}(\d{1,3}(?: \d{3})*-\d{2}|\d+-\d{2})",
    ]
    for pattern in patterns:
        match = re.search(pattern, search_space, re.IGNORECASE)
        if match:
            amount = normalize_amount_token(match.group(1))
            if amount:
                return amount
    words_amount = extract_amount_from_words(search_space)
    if words_amount:
        return words_amount
    matches = re.findall(r"\b(\d{1,3}(?: \d{3})*-\d{2}|\d+-\d{2})\b", search_space)
    for candidate in reversed(matches):
        amount = normalize_amount_token(candidate)
        if amount:
            return amount
    return None


def safe_filename(
    source: Path,
    office: str | None,
    category: str | None,
    entity: str | None,
    *,
    file_text: Callable[[Path], str],
    normalize_text: Callable[[str], str],
    normalize_piece: Callable[[str], str],
    office_people: dict[str, list[str]],
    office_contractors: dict[str, dict[str, list[str]]],
    bank_name: Callable[[str], str],
    bank_payment_recipient: Callable[[str], str],
    is_bank_order: Callable[[str], bool],
    is_payment_order: Callable[[str, str], bool],
    looks_like_salary_payment: Callable[[str, str], bool],
    extract_amount_from_words: Callable[[str], str | None],
    extract_invoice_amount: Callable[[str, str], str | None],
    strip_full_dates: Callable[[str], str],
    normalize_amount_token: Callable[[str], str],
    use_extracted_text_for_naming: bool = True,
    fallback_to_original_name_when_no_text: bool = True,
    make_names_windows_safe: bool = True,
) -> str:
    normalize_piece_runtime = lambda value: normalize_piece(value, windows_safe=make_names_windows_safe)
    normalized_name = normalize_text(source.name)
    try:
        text = normalize_text(file_text(source))
    except Exception:
        text = ""

    if not use_extracted_text_for_naming:
        if fallback_to_original_name_when_no_text:
            return normalize_structured_filename(source.name, normalize_piece=normalize_piece_runtime)
        return normalize_structured_filename(
            f"{normalize_piece_runtime(entity or category or f'офис{office}' if office else 'Документ') or 'Документ'}{source.suffix.lower()}",
            normalize_piece=normalize_piece_runtime,
        )

    vtb_meta = extract_vtb_filename_metadata(source.name, normalize_piece=normalize_piece_runtime)
    if vtb_meta and not text.strip():
        if category == "Комиссии":
            identifier = "Комиссия_ВТБ"
        elif category == "Налоги":
            identifier = "Налог_ВТБ"
        else:
            identifier = vtb_meta["identifier"]
        parts = [normalize_piece_runtime(identifier) or "Документ"]
        if vtb_meta["date"]:
            parts.append(vtb_meta["date"])
        if vtb_meta["number"]:
            parts.append(vtb_meta["number"])
        if vtb_meta["amount"]:
            parts.append(vtb_meta["amount"])
        return f"{'_'.join(parts)}{source.suffix.lower()}"

    stem = normalize_text(source.stem.strip())
    cleaned_stem = re.sub(r"[^\w\s.-]+", "_", stem, flags=re.UNICODE).strip(" ._")
    generic_report = re.fullmatch(r"(img|scan|document|file|image|photo|pdf|report|u)[-_ ]*\d*", cleaned_stem, re.IGNORECASE)
    generic_numeric = re.fullmatch(r"[\d\s._-]+", cleaned_stem)
    has_meaningful_name = bool(cleaned_stem) and not generic_report and not generic_numeric

    fallback_tag = cleaned_stem if has_meaningful_name else None
    fallback_id = next((part for part in [fallback_tag, entity, category, f"офис{office}" if office else None] if part), "Документ")

    identifier = fallback_id
    date = extract_payment_execution_date(text) or extract_date_from_name(source.name) or extract_first_date(text) or extract_invoice_date(text, source.name) or "без_даты"
    number = extract_numeric_suffix(source.name) or "без_номера"
    amount = extract_amount_from_name(source.name) or "без_суммы"
    combined_text = f"{text} {normalized_name}"

    if category == "Комиссии":
        identifier = "Комиссия"
        amount = extract_bank_order_amount(text, strip_full_dates=strip_full_dates, normalize_amount_token=normalize_amount_token, extract_amount_from_words=extract_amount_from_words) or extract_payment_order_amount(text, strip_full_dates=strip_full_dates, normalize_amount_token=normalize_amount_token, extract_amount_from_words=extract_amount_from_words) or amount
        if is_bank_order(text):
            number = extract_bank_order_number(text, source.name, normalize_piece=normalize_piece_runtime) or number
        elif is_payment_order(text, normalized_name):
            number = extract_payment_order_number(text, source.name, normalize_text=normalize_text, normalize_piece=normalize_piece_runtime) or number
    elif category == "Налоги":
        if "ндфл" in combined_text:
            identifier = "НДФЛ"
        elif "енп" in combined_text or "единый налоговый платеж" in combined_text:
            identifier = "ЕНП"
        else:
            identifier = "Налог"
        amount = extract_payment_order_amount(text, strip_full_dates=strip_full_dates, normalize_amount_token=normalize_amount_token, extract_amount_from_words=extract_amount_from_words) or amount
        if is_payment_order(text, normalized_name):
            number = extract_payment_order_number(text, source.name, normalize_text=normalize_text, normalize_piece=normalize_piece_runtime) or number
    elif category == "Взносы":
        identifier = "Взносы"
        amount = extract_payment_order_amount(text, strip_full_dates=strip_full_dates, normalize_amount_token=normalize_amount_token, extract_amount_from_words=extract_amount_from_words) or extract_bank_order_amount(text, strip_full_dates=strip_full_dates, normalize_amount_token=normalize_amount_token, extract_amount_from_words=extract_amount_from_words) or amount
        if is_payment_order(text, normalized_name):
            number = extract_payment_order_number(text, source.name, normalize_text=normalize_text, normalize_piece=normalize_piece_runtime) or number
        elif is_bank_order(text):
            number = extract_bank_order_number(text, source.name, normalize_piece=normalize_piece_runtime) or number
    elif category == "УСН":
        identifier = "УСН"
        amount = extract_payment_order_amount(text, strip_full_dates=strip_full_dates, normalize_amount_token=normalize_amount_token, extract_amount_from_words=extract_amount_from_words) or amount
        if is_payment_order(text, normalized_name):
            number = extract_payment_order_number(text, source.name, normalize_text=normalize_text, normalize_piece=normalize_piece_runtime) or number

    payment_order_like = is_payment_order(text, normalized_name)
    bank_export_name_like = looks_like_bank_export_payment_name(source.name)

    if is_bank_order(text):
        if category == "Комиссии":
            identifier = "Комиссия"
        elif category == "Взносы":
            identifier = "Взносы"
        elif category == "Налоги":
            if "ндфл" in combined_text:
                identifier = "НДФЛ"
            elif "енп" in combined_text or "единый налоговый платеж" in combined_text:
                identifier = "ЕНП"
            else:
                identifier = "Налог"
        elif category == "УСН":
            identifier = "УСН"
        else:
            identifier = normalize_piece_runtime(bank_name(text) or "") or "Банк"
        number = extract_bank_order_number(text, source.name, normalize_piece=normalize_piece_runtime) or number
        amount = extract_bank_order_amount(text, strip_full_dates=strip_full_dates, normalize_amount_token=normalize_amount_token, extract_amount_from_words=extract_amount_from_words) or amount
    elif payment_order_like or bank_export_name_like:
        if looks_like_salary_payment(text, normalized_name):
            date = extract_payment_execution_date(text) or extract_first_date(text) or date
            person = canonical_employee_name(text, office_people=office_people, normalize_text=normalize_text)
            if not person:
                person = bank_payment_recipient(text)
            if person:
                identifier = normalize_piece_runtime(person) or identifier
            amount = extract_payment_order_amount(text, strip_full_dates=strip_full_dates, normalize_amount_token=normalize_amount_token, extract_amount_from_words=extract_amount_from_words) or amount
            parts = [normalize_piece_runtime(identifier) or "Документ", date]
            if amount:
                parts.append(amount.replace(",", "-"))
            base = "_".join(parts)
            return normalize_structured_filename(f"{base}{source.suffix.lower()}", normalize_piece=normalize_piece_runtime)
        if category not in {"Комиссии", "Налоги", "Взносы", "УСН"}:
            fallback_identifier = category or entity or fallback_id
            identifier = contractor_payment_identifier(
                text,
                source.name,
                office,
                category,
                fallback_identifier,
                office_contractors=office_contractors,
                bank_payment_recipient=bank_payment_recipient,
                bank_name=bank_name,
                normalize_text=normalize_text,
                normalize_piece=normalize_piece_runtime,
            )
            amount = extract_payment_order_amount(text, strip_full_dates=strip_full_dates, normalize_amount_token=normalize_amount_token, extract_amount_from_words=extract_amount_from_words) or extract_bank_order_amount(text, strip_full_dates=strip_full_dates, normalize_amount_token=normalize_amount_token, extract_amount_from_words=extract_amount_from_words) or amount
            parts = [normalize_piece_runtime(identifier) or "Контрагент", date]
            if amount:
                parts.append(amount.replace(",", "-"))
            base = "_".join(parts)
            return normalize_structured_filename(f"{base}{source.suffix.lower()}", normalize_piece=normalize_piece_runtime)
        if payment_order_like:
            number = extract_payment_order_number(text, source.name, normalize_text=normalize_text, normalize_piece=normalize_piece_runtime) or number
            amount = extract_payment_order_amount(text, strip_full_dates=strip_full_dates, normalize_amount_token=normalize_amount_token, extract_amount_from_words=extract_amount_from_words) or amount
    elif normalize_text(text).startswith("счет") or normalized_name.startswith("счет"):
        identifier = extract_invoice_counterparty(text, source.name, office_contractors=office_contractors, normalize_text=normalize_text, normalize_piece=normalize_piece_runtime) or identifier
        number = extract_invoice_number(text, source.name, normalize_text=normalize_text, normalize_piece=normalize_piece_runtime) or number
        date = extract_invoice_date(text, source.name) or date
        amount = extract_invoice_amount(text, source.name) or amount

    if not text.strip() and fallback_tag and fallback_to_original_name_when_no_text and date == "без_даты" and number == "без_номера" and amount == "без_суммы":
        return normalize_structured_filename(f"{fallback_tag}{source.suffix.lower()}", normalize_piece=normalize_piece_runtime)
    if fallback_tag and fallback_to_original_name_when_no_text and (normalize_piece_runtime(identifier) or "") == fallback_tag and date == "без_даты" and amount == "без_суммы":
        fallback_number = extract_numeric_suffix(source.name) or "без_номера"
        if number == fallback_number:
            return normalize_structured_filename(f"{fallback_tag}{source.suffix.lower()}", normalize_piece=normalize_piece_runtime)

    parts = [normalize_piece_runtime(identifier) or "Документ", date]
    if number:
        parts.append(normalize_piece_runtime(number))
    if amount:
        parts.append(amount.replace(",", "-"))
    base = "_".join(parts)
    return normalize_structured_filename(f"{base}{source.suffix.lower()}", normalize_piece=normalize_piece_runtime)
