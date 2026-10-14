from __future__ import annotations

import re
import unicodedata


def business_document_text(text: str) -> str:
    return re.split(r"документ\s+(?:подписан\s+и\s+)?передан\s+через\s+оператора\s+эдо", text, maxsplit=1, flags=re.I)[0]


RU_NUMBERS = {
    "ноль": 0, "нуль": 0,
    "один": 1, "одна": 1, "одно": 1,
    "два": 2, "две": 2,
    "три": 3, "четыре": 4, "пять": 5, "шесть": 6, "семь": 7, "восемь": 8, "девять": 9,
    "десять": 10, "одиннадцать": 11, "двенадцать": 12, "тринадцать": 13, "четырнадцать": 14,
    "пятнадцать": 15, "шестнадцать": 16, "семнадцать": 17, "восемнадцать": 18, "девятнадцать": 19,
    "двадцать": 20, "тридцать": 30, "сорок": 40, "пятьдесят": 50, "шестьдесят": 60,
    "семьдесят": 70, "восемьдесят": 80, "девяносто": 90,
    "сто": 100, "двести": 200, "триста": 300, "четыреста": 400, "пятьсот": 500,
    "шестьсот": 600, "семьсот": 700, "восемьсот": 800, "девятьсот": 900,
}

WINDOWS_RESERVED_NAMES = {
    "con", "prn", "aux", "nul",
    "com1", "com2", "com3", "com4", "com5", "com6", "com7", "com8", "com9",
    "lpt1", "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9",
}


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower().replace("ё", "е")
    value = value.replace("\xa0", " ")
    replacements = {
        "ooo": "ооо",
        "oоо": "ооо",
        "оoo": "ооо",
        "nº": "№",
        "no.": "№",
        "no ": "№ ",
        "р/с": "рс",
        "к/с": "кс",
        "инн/кпп": "инн кпп",
        "билаин": "билайн",
        "чеботврев": "чеботарев",
        "ɉⱥɉ ȼɵɦɩɟɥʉɨɦ": "пао вымпелком",
        "ȼɵɦɩɟɥʉɨɦ": "вымпелком",
        "ɉɉɉ ʉɍȼɂʉɉɋ": "ооо образец",
        "ʌɢɱɧɵɣ ɤɚɛɢɧɟɬ": "личный кабинет",
        "e ehholqh ux": "beeline ru",
        "sur ehholqh ux": "pro beeline ru",
        "e evxssruw#ehholqh ux": "e support@beeline ru",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    value = re.sub(r"[|¦]+", " ", value)
    value = re.sub(r"[`´‘’“”]", '"', value)
    value = re.sub(r"(?<=\d)[oо](?=\d)", "0", value)
    value = re.sub(r"(?<=\d)[,](?=\d{2}\b)", ".", value)
    value = re.sub(r"(?<=\d)[-](?=\d{2}\b)", ".", value)
    value = re.sub(r"\b([а-яa-z]{2,})0([а-яa-z]{2,})\b", r"\1о\2", value)
    value = re.sub(r"\b([а-яa-z])1([а-яa-z])\b", r"\1l\2", value)
    value = re.sub(r"[^\S\r\n]+", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value


PERSON_TOKEN_ENDINGS = (
    "иями", "ями", "ами", "ого", "его", "ому", "ему", "ыми", "ими",
    "ой", "ей", "ою", "ею", "ая", "яя", "ую", "юю", "ые", "ие",
    "ых", "их", "ым", "им", "ов", "ев", "ии", "еи",
    "а", "я", "ы", "и", "у", "ю", "е", "о",
)


def person_token_stem(value: str) -> str:
    token = normalize_text(value).replace("й", "и").strip("ьъ")
    for ending in PERSON_TOKEN_ENDINGS:
        if len(token) > len(ending) + 2 and token.endswith(ending):
            token = token[:-len(ending)].strip("ьъ")
            break
    return token


def person_token_matches(expected: str, actual: str) -> bool:
    expected_stem = person_token_stem(expected)
    actual_stem = person_token_stem(actual)
    if len(expected_stem) < 3 or len(actual_stem) < 3:
        return expected_stem == actual_stem
    return (
        expected_stem == actual_stem
        or expected_stem.startswith(actual_stem)
        or actual_stem.startswith(expected_stem)
    )


def declined_person_name_in_text(person: str, text: str) -> bool:
    person_tokens = re.findall(r"[а-яa-zё]{3,}", normalize_text(person))
    text_tokens = re.findall(r"[а-яa-zё]{3,}", normalize_text(text))
    if not person_tokens or not text_tokens:
        return False
    max_gap = 8
    for start in range(len(text_tokens)):
        if not person_token_matches(person_tokens[0], text_tokens[start]):
            continue
        position = start
        matched = True
        for expected in person_tokens[1:]:
            found = False
            for next_position in range(position + 1, min(len(text_tokens), position + max_gap + 1)):
                if person_token_matches(expected, text_tokens[next_position]):
                    position = next_position
                    found = True
                    break
            if not found:
                matched = False
                break
        if matched:
            return True
    return False


def bounded_confidence(value: int, cap: int = 100) -> int:
    return max(0, min(cap, value))


def normalize_amount_token(value: str) -> str:
    digits = value.replace("\xa0", " ").strip()
    digits = re.sub(r"\s+", "", digits)
    digits = digits.replace("-", ".")
    digits = digits.replace(",", ".")
    match = re.fullmatch(r"(\d+)\.(\d{2})", digits)
    if not match:
        return ""
    return f"{match.group(1)}-{match.group(2)}"


def strip_full_dates(text: str) -> str:
    return re.sub(r"\b\d{2}[.\-]\d{2}[.\-]\d{4}\b", " ", text)


def parse_russian_number_words(value: str) -> int | None:
    tokens = [token for token in re.split(r"[\s-]+", normalize_text(value)) if token]
    if not tokens:
        return None
    total = 0
    current = 0
    matched = False
    for token in tokens:
        if token.startswith("тысяч"):
            current = max(current, 1)
            total += current * 1000
            current = 0
            matched = True
            continue
        number = RU_NUMBERS.get(token)
        if number is None:
            continue
        current += number
        matched = True
    if not matched:
        return None
    return total + current


def extract_amount_from_words(text: str) -> str | None:
    normalized = normalize_text(text).replace("0о", "00").replace("oо", "00").replace("оo", "00")
    patterns = [
        r"сумма\s+прописью\s+([а-яё\s-]+?)\s+руб(?:ль|ля|лей)\s+([а-яё0-9\s-]+?)\s+коп",
        r"([а-яё\s-]+?)\s+руб(?:ль|ля|лей)\s+([а-яё0-9\s-]+?)\s+коп",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized, re.IGNORECASE)
        if not match:
            continue
        rub_raw = match.group(1).strip()
        kop_raw = match.group(2).strip()
        rub = parse_russian_number_words(rub_raw)
        if rub is None:
            continue
        kop_digits = re.sub(r"\D", "", kop_raw)
        if kop_digits:
            kop = int(kop_digits[:2].ljust(2, "0"))
        else:
            parsed_kop = parse_russian_number_words(kop_raw)
            if parsed_kop is None:
                continue
            kop = parsed_kop
        return f"{rub}-{kop:02d}"
    return None


def normalize_piece(value: str, *, windows_safe: bool = True) -> str:
    value = normalize_text(value).strip().replace('"', "")
    if windows_safe:
        value = re.sub(r'[<>:"/\\\\|?*]+', "_", value)
    else:
        value = re.sub(r'[:/\\\\]+', "_", value)
    value = re.sub(r"[^\w\s.-]+", "_", value, flags=re.UNICODE)
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"_+", "_", value).strip("._")
    if not value:
        return ""

    letters = sum(ch.isalpha() for ch in value)
    digits = sum(ch.isdigit() for ch in value)
    if letters < 3 and digits > 10:
        return ""
    if re.fullmatch(r"[0-9A-Fa-f_]+", value) and len(value) > 24:
        return ""

    # Drop identifiers that are mostly OCR garbage or repeated numeric blobs.
    hexish_tokens = len(re.findall(r"\b[0-9A-Fa-f]{4,}\b", value))
    if hexish_tokens > 4:
        return ""
    if re.search(r"(?:_\d{4,}){4,}", value):
        return ""

    # Keep filename parts short enough for macOS/Windows path safety.
    if len(value) > 72:
        words = [part for part in value.split('_') if part]
        compact = []
        for word in words:
            compact.append(word[:20])
            if len('_'.join(compact)) >= 72:
                break
        value = '_'.join(compact).strip('._')
    if len(value) > 72:
        value = value[:72].strip('._')
    if windows_safe and value.lower() in WINDOWS_RESERVED_NAMES:
        value = f"file_{value}"
    if windows_safe:
        value = value.rstrip(" .")
    return value
