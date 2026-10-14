from __future__ import annotations

import re
from sorting_text_utils import business_document_text
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

try:
    from rapidfuzz import fuzz
except Exception:
    fuzz = None

from sorting_config import RuntimeRuleSettings
from sorting_models import Classification, DetectionResult
from sorting_budget_payments import is_insurance_payment
from sorting_provider_subfolders import internet_provider_subfolder
from sorting_rules_data import MANUAL_FILE_RULES, SPECIAL_FOLDER_RULES
from sorting_text_utils import declined_person_name_in_text


@dataclass(frozen=True)
class ClassificationRuntime:
    entity_patterns: dict[str, list[str]]
    entity_account_patterns: dict[str, list[str]]
    entity_source_hint_patterns: dict[str, list[str]]
    office_people: dict[str, list[str]]
    office_contractors: dict[str, dict[str, list[str]]]
    office_entities: dict[str, str]
    office_categories: dict[str, list[str]]
    offices: list[str]
    category_patterns: dict[str, list[str]]
    tax_patterns: list[str]
    insurance_accident_patterns: list[str]
    usn_patterns: list[str]
    bank_commission_patterns: list[str]
    rule_settings: RuntimeRuleSettings = field(default_factory=RuntimeRuleSettings)
    office_contractor_folders: dict[str, dict[str, dict[str, str]]] = field(default_factory=dict)


INTERNET_PROVIDER_TOKENS = [
    "билайн",
    "вымпелком",
    "пао вымпелком",
    "искрателеком",
    "ооо искрателеком",
    "вип-телеком",
    "ооо вип-телеком-сервис",
    "vip telecom",
    "vip-telecom",
]


def _looks_mojibake(value: str) -> bool:
    return bool(re.search(r"[Ⱥ-ɿⱥʉʌ]", value))


def _provider_detection_text(raw_text: str, normalized_text: str, *, runtime: ClassificationRuntime) -> str:
    if runtime.rule_settings.internet.normalize_broken_provider_text:
        return normalized_text
    lowered_raw = raw_text.lower()
    if not _looks_mojibake(raw_text):
        return normalized_text
    if any(token in lowered_raw for token in INTERNET_PROVIDER_TOKENS):
        return normalized_text
    stripped = normalized_text
    for token in INTERNET_PROVIDER_TOKENS:
        stripped = stripped.replace(token, " ")
    return re.sub(r"\s+", " ", stripped).strip()


def best_keyword_match(keywords: list[str], text: str, *, min_score: int = 90) -> str | None:
    for keyword in keywords:
        if keyword in text:
            return keyword
    if fuzz is None:
        return None
    best_keyword = None
    best_score = min_score
    for keyword in keywords:
        if len(keyword) < 6:
            continue
        score = fuzz.partial_ratio(keyword, text)
        if score >= best_score:
            best_keyword = keyword
            best_score = score
    return best_keyword


def detect_entity(
    text: str,
    name_text: str,
    path_text: str,
    source_hint_text: str = "",
    *,
    runtime: ClassificationRuntime,
    match_any: Callable[[list[str], str], bool],
) -> str | None:
    combined = f"{text} {name_text} {path_text} {source_hint_text}"
    for entity, patterns in runtime.entity_patterns.items():
        if match_any(patterns, combined):
            return entity
    for entity, patterns in runtime.entity_account_patterns.items():
        if match_any(patterns, combined):
            return entity
    for entity, patterns in runtime.entity_source_hint_patterns.items():
        if match_any(patterns, combined):
            return entity
    return None


def detect_entity_signal(
    text: str,
    name_text: str,
    path_text: str,
    source_hint_text: str = "",
    *,
    runtime: ClassificationRuntime,
    match_any: Callable[[list[str], str], bool],
    bounded_confidence: Callable[[int, int], int],
) -> DetectionResult:
    combined = f"{text} {name_text} {path_text} {source_hint_text}"
    candidates: list[tuple[int, str, list[str]]] = []
    for entity in sorted({*runtime.entity_patterns.keys(), *runtime.entity_account_patterns.keys(), *runtime.entity_source_hint_patterns.keys()}):
        score = 0
        trace: list[str] = []
        if match_any(runtime.entity_patterns.get(entity, []), text):
            score += 65
            trace.append(f"юрлицо {entity} найдено в тексте")
        if match_any(runtime.entity_patterns.get(entity, []), name_text):
            score += 25
            trace.append(f"юрлицо {entity} найдено в имени файла")
        if match_any(runtime.entity_account_patterns.get(entity, []), combined):
            score += 80
            trace.append(f"юрлицо {entity} найдено по расчетному счету")
        if match_any(runtime.entity_source_hint_patterns.get(entity, []), combined):
            score += 55
            trace.append(f"юрлицо {entity} найдено по шаблону банковского файла")
        if score:
            candidates.append((score, entity, trace))
    if not candidates:
        return DetectionResult(value=None, reason="юрлицо не найдено", confidence=0, trace=["юрлицо не найдено"])
    candidates.sort(key=lambda item: item[0], reverse=True)
    best_score, best_entity, best_trace = candidates[0]
    if len(candidates) > 1 and candidates[1][0] >= best_score - 10:
        return DetectionResult(value=None, reason="юрлицо определено неоднозначно", confidence=20, trace=best_trace + ["конфликт по юрлицу"])
    return DetectionResult(
        value=best_entity,
        reason=f"юрлицо {best_entity}",
        confidence=bounded_confidence(best_score, 100),
        trace=best_trace,
    )


def infer_entity_from_office(office: str | None, *, runtime: ClassificationRuntime) -> str | None:
    if not office:
        return None
    return runtime.office_entities.get(office)


def detect_office(
    text: str,
    name_text: str,
    entity: str | None,
    *,
    runtime: ClassificationRuntime,
    bank_payment_recipient: Callable[[str], str],
    bank_payment_purpose: Callable[[str], str],
    normalize_text: Callable[[str], str] | None = None,
) -> tuple[str | None, str]:
    result = detect_office_signal(
        text,
        name_text,
        entity,
        runtime=runtime,
        bank_payment_recipient=bank_payment_recipient,
        bank_payment_purpose=bank_payment_purpose,
        normalize_text=normalize_text,
    )
    return result.value, result.reason


def detect_office_signal(
    text: str,
    name_text: str,
    entity: str | None,
    *,
    runtime: ClassificationRuntime,
    bank_payment_recipient: Callable[[str], str],
    bank_payment_purpose: Callable[[str], str],
    bounded_confidence: Callable[[int, int], int] | None = None,
    normalize_text: Callable[[str], str] | None = None,
) -> DetectionResult:
    bounded_confidence = bounded_confidence or (lambda value, cap=100: max(0, min(cap, value)))
    normalize_text = normalize_text or (lambda value: value)
    text = business_document_text(text)
    recipient = bank_payment_recipient(text)
    purpose = bank_payment_purpose(text)
    combined = f"{text} {name_text} {recipient} {purpose}"
    score_map: dict[str, int] = {}
    trace_map: dict[str, list[str]] = {}
    rejected_entity_conflicts: list[str] = []

    def add(office: str, weight: int, reason: str) -> None:
        office_entity = runtime.office_entities.get(office)
        if entity and office_entity and office_entity != entity:
            rejected_entity_conflicts.append(
                f"сигнал офиса {office} отклонен: юрлицо офиса {office_entity} не совпадает с документом {entity}"
            )
            return
        score_map[office] = score_map.get(office, 0) + weight
        trace_map.setdefault(office, []).append(reason)

    for office in runtime.offices:
        if re.search(rf"\bофис\s*{office}\b", combined, re.IGNORECASE):
            add(office, 90, f"обнаружен номер офиса {office}")

    if "ип тестовпоставщик" in combined or "тестовпоставщик" in combined:
        if entity == "ПРИМЕР":
            add("109", 80, "правило ИП Тестовпоставщик для ПРИМЕР")
        if entity == "ОБРАЗЕЦ":
            add("98", 80, "правило ИП Тестовпоставщик для ОБРАЗЕЦ")

    if runtime.rule_settings.routing.use_contractors_as_category_signals:
        for office, categories in runtime.office_contractors.items():
            for keywords in categories.values():
                matched = best_keyword_match(keywords, combined)
                if matched:
                    add(office, 55 if matched not in combined else 45, f"совпадение по контрагенту офиса {office}: {matched}")

    for office, people in runtime.office_people.items():
        matched_people = [
            person
            for person in people
            if normalize_text(person) in combined or declined_person_name_in_text(person, combined)
        ]
        if matched_people:
            add(office, 70 + min(15, len(matched_people) * 5), f"совпадение по сотруднику офиса {office}: {matched_people[0]}")

    recipient_tokens = {token for token in re.findall(r"[а-яa-zё]{3,}", recipient) if token}
    if recipient_tokens:
        fuzzy_person_matches: list[tuple[int, str, str]] = []
        for office, people in runtime.office_people.items():
            for person in people:
                person_tokens = {token for token in re.findall(r"[а-яa-zё]{3,}", normalize_text(person)) if token}
                overlap = len(recipient_tokens & person_tokens)
                if overlap < 2:
                    continue
                score = overlap * 20
                if recipient_tokens <= person_tokens:
                    score += 15
                fuzzy_person_matches.append((score, office, person))
        fuzzy_person_matches.sort(reverse=True)
        if fuzzy_person_matches:
            best_score, best_office, best_person = fuzzy_person_matches[0]
            next_best = fuzzy_person_matches[1][0] if len(fuzzy_person_matches) > 1 else -999
            if best_score >= 55 and best_score - next_best >= 15:
                add(best_office, best_score, f"похожее совпадение по получателю с сотрудником офиса {best_office}: {best_person}")

    if entity:
        for office in runtime.offices:
            if office in score_map and runtime.office_entities.get(office) == entity:
                add(office, 10, f"офис согласован с юрлицом {entity}")

    if not score_map:
        trace = rejected_entity_conflicts or ["офис не найден"]
        return DetectionResult(value=None, reason="не удалось определить офис", confidence=0, trace=trace)

    ranked = sorted(score_map.items(), key=lambda item: item[1], reverse=True)
    best_office, best_score = ranked[0]
    runner_up = ranked[1][1] if len(ranked) > 1 else -999
    confidence = bounded_confidence(best_score - max(0, runner_up // 4), 100)
    trace = trace_map.get(best_office, [])
    if len(ranked) > 1 and best_score - runner_up < 15:
        return DetectionResult(
            value=best_office,
            reason=f"офис {best_office} определен с низким преимуществом",
            confidence=min(confidence, 45),
            trace=trace + [f"есть близкий альтернативный офис {ranked[1][0]}"],
        )
    return DetectionResult(
        value=best_office,
        reason=f"офис {best_office}",
        confidence=confidence,
        trace=trace,
    )


def looks_like_salary_payment(
    text: str,
    *,
    runtime: ClassificationRuntime,
    normalize_text: Callable[[str], str],
) -> bool:
    salary_markers = [
        normalize_text(marker)
        for marker in ["выплата заработной платы", "выплата зарплаты", "заработная плата", "заработной платы", "зарплата"]
    ]
    salary_purpose = any(marker in text for marker in salary_markers)
    has_pay_order = "платежное поручение" in text
    has_employee = any(
        normalize_text(person) in text or declined_person_name_in_text(person, text)
        for people in runtime.office_people.values()
        for person in people
    )
    return salary_purpose and (has_pay_order or has_employee)


def detect_category(
    text: str,
    name_text: str,
    *,
    runtime: ClassificationRuntime,
    bank_payment_recipient: Callable[[str], str],
    bank_payment_purpose: Callable[[str], str],
    normalize_text: Callable[[str], str],
    match_any: Callable[[list[str], str], bool],
    bounded_confidence: Callable[[int, int], int],
) -> tuple[str | None, str]:
    result = detect_category_signal(
        text,
        name_text,
        runtime=runtime,
        bank_payment_recipient=bank_payment_recipient,
        bank_payment_purpose=bank_payment_purpose,
        normalize_text=normalize_text,
        match_any=match_any,
        bounded_confidence=bounded_confidence,
    )
    return result.value, result.reason


def detect_category_signal(
    text: str,
    name_text: str,
    *,
    runtime: ClassificationRuntime,
    bank_payment_recipient: Callable[[str], str],
    bank_payment_purpose: Callable[[str], str],
    normalize_text: Callable[[str], str],
    match_any: Callable[[list[str], str], bool],
    bounded_confidence: Callable[[int, int], int],
    office: str | None = None,
) -> DetectionResult:
    text = business_document_text(text)
    recipient = bank_payment_recipient(text)
    purpose = bank_payment_purpose(text)
    combined = f"{text} {name_text} {recipient} {purpose}"
    relevant_text = combined
    score_map: dict[str, int] = {}
    trace_map: dict[str, list[str]] = {}

    def add(category: str, weight: int, reason: str) -> None:
        score_map[category] = score_map.get(category, 0) + weight
        trace_map.setdefault(category, []).append(reason)

    internet_service_markers = [
        "интернет",
        "услуги связи",
        "доступа в интернет",
        "доступ к сети интернет",
        "провайдер",
        "телеком",
        "билайн",
        "вымпелком",
        "искрателеком",
        "вип-телеком",
    ]

    if runtime.rule_settings.commissions.detect_by_payment_text and "vtb_payment_commission" in combined:
        add("Комиссии", 95, "комиссия банка втб")
    if runtime.rule_settings.commissions.detect_by_payment_text and ("vtb_bank_order" in combined or "bank_order" in combined):
        add("Комиссии", 70, "банковский ордер втб")
    if runtime.rule_settings.commissions.detect_by_payment_text and match_any(runtime.bank_commission_patterns, combined):
        add("Комиссии", 85, "банковская комиссия")
    if runtime.rule_settings.taxes.detect_by_payment_phrases and match_any(runtime.insurance_accident_patterns, combined):
        add("Взносы", 95, "взносы от несчастных случаев")
    if runtime.rule_settings.taxes.detect_by_payment_phrases and is_insurance_payment(combined):
        add("Взносы", 100, "явное назначение страховых взносов")
    if re.search(r"возмещение\s+расходов.{0,80}коммунальн|оплат[аеуы].{0,30}коммунальн", combined):
        add("Коммунальные", 150, "оплата коммунальных расходов, а не аренды")
    if runtime.rule_settings.taxes.detect_by_payment_phrases and (
        match_any(runtime.usn_patterns, combined) or ("усн" in combined and "ндс не облагается" in combined)
    ):
        add("УСН", 90, "документ УСН")
    if looks_like_salary_payment(text, runtime=runtime, normalize_text=normalize_text):
        add("Зарплата", 95, "подтвержденное платежное поручение по зарплате")
    if runtime.rule_settings.taxes.detect_by_payment_phrases and match_any(runtime.tax_patterns, combined):
        add("Налоги", 80, "налоговый документ")
    for category, patterns in runtime.category_patterns.items():
        if match_any(patterns, combined):
            add(category, 55, f"совпадение по категории {category}")
    contractor_sources = runtime.office_contractors.items()
    if office and runtime.rule_settings.routing.route_office_before_category_finalization:
        contractor_sources = [(office, runtime.office_contractors.get(office, {}))]

    if runtime.rule_settings.routing.use_contractors_as_category_signals:
        for contractor_office, categories in contractor_sources:
            for category, keywords in categories.items():
                contractor_text = relevant_text
                if category == "Интернет":
                    contractor_text = text
                matched = best_keyword_match(keywords, contractor_text)
                if matched:
                    weight = 55 if matched not in contractor_text else 45
                    if office and contractor_office == office and runtime.rule_settings.routing.route_office_before_category_finalization:
                        weight += 20
                    add(category, weight, f"категория {category} выведена по контрагенту: {matched}")
                    if (
                        category == "Интернет"
                        and runtime.rule_settings.internet.prioritize_known_providers
                        and any(marker in relevant_text for marker in internet_service_markers)
                    ):
                        add("Интернет", 25, f"подтверждение интернет-услуг по тексту: {matched}")

    if normalize_text(text).startswith("счет") or normalize_text(name_text).startswith("счет"):
        add("Услуги", 15, "обнаружен счет")

    if office:
        matched_employee = next(
            (
                person
                for person in runtime.office_people.get(office, [])
                if normalize_text(person) in combined or declined_person_name_in_text(person, combined)
            ),
            None,
        )
        payment_context = any(
            marker in combined
            for marker in ["платежное поручение", "получател", "назначение платежа", "сумма", "сч. n 408", "счет n 408"]
        )
        if matched_employee and set(runtime.office_categories.get(office, [])) == {"Зарплата"}:
            add("Зарплата", 80, f"офис {office} принимает только зарплату, найден сотрудник: {matched_employee}")
        elif matched_employee and payment_context:
            add("Зарплата", 70, f"платежный документ по сотруднику офиса {office}: {matched_employee}")

    if not score_map:
        return DetectionResult(value="Прочее", reason="категория по умолчанию", confidence=30, trace=["нет сильных признаков категории"])

    ranked = sorted(score_map.items(), key=lambda item: item[1], reverse=True)
    best_category, best_score = ranked[0]
    if office and runtime.rule_settings.routing.route_office_before_category_finalization:
        allowed_categories = set(runtime.office_categories.get(office, []))
        if allowed_categories and best_category not in allowed_categories:
            for candidate, candidate_score in ranked:
                if candidate in allowed_categories:
                    best_category, best_score = candidate, candidate_score
                    trace_map.setdefault(best_category, []).append(f"категория согласована с разрешенными категориями офиса {office}")
                    break
    runner_up = ranked[1][1] if len(ranked) > 1 else -999
    confidence = bounded_confidence(best_score - max(0, runner_up // 4), 100)
    trace = trace_map.get(best_category, [])
    if len(ranked) > 1 and best_score - runner_up < 12:
        confidence = min(confidence, 45)
        trace = trace + [f"есть близкая альтернативная категория {ranked[1][0]}"]
    return DetectionResult(
        value=best_category,
        reason=f"категория {best_category}",
        confidence=confidence,
        trace=trace,
    )


def destination_for(
    source: Path,
    archive_root: Path,
    office: str | None,
    category: str | None,
    entity: str | None,
    *,
    runtime: ClassificationRuntime,
    file_text: Callable[[Path], str],
    normalize_text: Callable[[str], str],
) -> tuple[Path | None, str]:
    source_text = normalize_text(file_text(source))
    source_name = normalize_text(source.name)

    def office_for_entity(default_office: str | None = None) -> str | None:
        if office:
            return office
        if not entity:
            return default_office
        if category == "Комиссии" and not runtime.rule_settings.commissions.use_office_entity_routing:
            return default_office
        if category in {"Налоги", "Взносы"} and not runtime.rule_settings.taxes.use_office_entity_routing:
            return default_office
        category_aliases = {
            "Налоги": {"Налоги", "Ндфл и Взносы"},
            "Взносы": {"Взносы", "Ндфл и Взносы"},
            "Комиссии": {"Комиссии"},
        }
        matches = [office_id for office_id, office_entity in runtime.office_entities.items() if office_entity == entity]
        allowed_matches = [
            office_id
            for office_id in matches
            if any(
                item in category_aliases.get(category or "", {category or ""})
                for item in runtime.office_categories.get(office_id, [])
            )
        ]
        if len(allowed_matches) == 1:
            return allowed_matches[0]
        if len(matches) == 1:
            return matches[0]
        return default_office

    if category == "Комиссии":
        commission_office = office_for_entity()
        if commission_office:
            return archive_root / commission_office / "Комиссии", f"комиссии {entity or ''} относятся к {commission_office}".strip()
        return None, "для комиссии не найдено юрлицо"

    if category == "Взносы":
        insurance_office = office_for_entity()
        if insurance_office:
            return archive_root / insurance_office / "Ндфл и Взносы", f"взносы {entity or ''} относятся к {insurance_office}".strip()
        return None, "для взносов не найдено юрлицо"

    if category == "УСН":
        if not entity:
            return None, "для УСН не найдено юрлицо"
        return archive_root / "УСН" / entity, "корневая папка УСН"

    if category == "Налоги":
        tax_office = office_for_entity()
        if tax_office:
            return archive_root / tax_office / "Ндфл и Взносы", f"налоги {entity or ''} относятся к {tax_office}".strip()
        return None, "для налогов не найдено юрлицо"

    if office == "109" and any(token in f"{source_text} {source_name}" for token in ["ип тестовпоставщик", "тестовпоставщик"]):
        return archive_root / "109" / "ИП Тестовпоставщик", "специальная папка ИП Тестовпоставщик"

    if office == "109" and any(token in f"{source_text} {source_name}" for token in ["ип демопоставщик", "демопоставщик"]):
        return archive_root / "109" / "ИП Демопоставщикой", "специальная папка ИП Демопоставщикой"

    if office and category and runtime.rule_settings.internet.allow_special_provider_subfolders:
        haystack = f"{source_text} {source_name}"
        for rule in SPECIAL_FOLDER_RULES:
            if rule["office"] != office or rule["category"] != category:
                continue
            if any(token in haystack for token in rule["contains_any"]):
                return archive_root / office / category / rule["subfolder"], rule["reason"]

    if (
        office
        and category
        and runtime.rule_settings.internet.allow_special_provider_subfolders
        and runtime.rule_settings.internet.create_subfolders_by_office_contractors
    ):
        provider_folder = internet_provider_subfolder(
            office=office,
            category=category,
            haystack=f"{source_text} {source_name}",
            office_contractor_folders=runtime.office_contractor_folders,
        )
        if provider_folder:
            return archive_root / office / category / provider_folder, f"папка провайдера {provider_folder} из правил офиса"

    if office and category and runtime.rule_settings.internet.create_subfolders_by_office_contractors:
        folder_map = runtime.office_contractor_folders.get(office, {}).get(category, {})
        haystack = f"{source_text} {source_name}"
        for keyword, folder_name in sorted(folder_map.items(), key=lambda item: len(item[0]), reverse=True):
            if keyword in haystack:
                return archive_root / office / category / folder_name, f"папка контрагента {folder_name} из правил офиса"

    if office and category:
        return archive_root / office / category, "офисная папка"

    return None, "недостаточно данных для папки назначения"


def classify_document(
    path: Path,
    archive_root: Path,
    *,
    runtime: ClassificationRuntime,
    file_text: Callable[[Path], str],
    normalize_text: Callable[[str], str],
    match_any: Callable[[list[str], str], bool],
    bounded_confidence: Callable[[int, int], int],
    bank_payment_recipient: Callable[[str], str],
    bank_payment_purpose: Callable[[str], str],
    safe_filename: Callable[[Path, str | None, str | None, str | None], str],
) -> Classification:
    manual_rule = MANUAL_FILE_RULES.get(path.name.lower())
    raw_extracted = file_text(path)
    extracted = normalize_text(raw_extracted)
    category_text = _provider_detection_text(raw_extracted, extracted, runtime=runtime)
    if runtime.rule_settings.routing.route_by_document_text_first:
        name_text = ""
        path_text = ""
    else:
        name_text = normalize_text(path.name)
        path_text = normalize_text(str(path.parent))
    source_hint_text = normalize_text(f"{path.name} {path.parent.name}")

    if "форма ефс-1" in extracted or "сведения о начисленных страховых взносах" in extracted:
        return Classification(
            destination=archive_root / "Требует_ручной_проверки",
            office=None,
            category="Прочее",
            entity=None,
            reason="форма ЕФС-1 не является платежным документом, файл отправлен в ручную проверку",
            new_name=path.name,
            confidence=15,
            requires_manual_review=True,
            trace=["форма ЕФС-1 не является платежным документом"],
        )

    if manual_rule:
        office = manual_rule.get("office") or None
        category = manual_rule.get("category") or None
        entity = manual_rule.get("entity") or None
        destination, destination_reason = destination_for(
            path,
            archive_root,
            office,
            category,
            entity,
            runtime=runtime,
            file_text=file_text,
            normalize_text=normalize_text,
        )
        if destination is None:
            if office and category:
                destination = archive_root / office / category
                destination_reason = "путь собран из ручного правила"
            else:
                destination = archive_root / "Требует_ручной_проверки"
                destination_reason = "ручное правило неполное, файл отправлен в ручную проверку"
        new_name = manual_rule.get("new_name") or safe_filename(path, office, category, entity)
        rule_reason = manual_rule.get("reason") or "ручное правило файла"
        requires_manual_review = destination.name == "Требует_ручной_проверки"
        return Classification(
            destination=destination,
            office=office,
            category=category,
            entity=entity,
            reason=f"{rule_reason}; {destination_reason}",
            new_name=new_name,
            confidence=100 if not requires_manual_review else 30,
            requires_manual_review=requires_manual_review,
            trace=["применено ручное правило файла", destination_reason],
        )

    entity_result = detect_entity_signal(
        extracted,
        name_text,
        path_text,
        source_hint_text,
        runtime=runtime,
        match_any=match_any,
        bounded_confidence=bounded_confidence,
    )
    entity = entity_result.value
    office_result = detect_office_signal(
        extracted,
        name_text,
        entity,
        runtime=runtime,
        bank_payment_recipient=bank_payment_recipient,
        bank_payment_purpose=bank_payment_purpose,
        bounded_confidence=bounded_confidence,
        normalize_text=normalize_text,
    )
    office = office_result.value
    category_result = detect_category_signal(
        category_text,
        name_text,
        runtime=runtime,
        bank_payment_recipient=bank_payment_recipient,
        bank_payment_purpose=bank_payment_purpose,
        normalize_text=normalize_text,
        match_any=match_any,
        bounded_confidence=bounded_confidence,
        office=office,
    )
    category = category_result.value

    inferred_entity = infer_entity_from_office(office, runtime=runtime)
    if not entity and inferred_entity:
        entity = inferred_entity
        entity_result = DetectionResult(
            value=entity,
            reason=f"юрлицо {entity}",
            confidence=max(entity_result.confidence, 70 if office_result.confidence >= 50 else 55),
            trace=entity_result.trace + [f"юрлицо {entity} выведено по офису {office}"],
        )

    destination, destination_reason = destination_for(
        path,
        archive_root,
        office,
        category,
        entity,
        runtime=runtime,
        file_text=file_text,
        normalize_text=normalize_text,
    )
    new_name = safe_filename(path, office, category, entity)
    confidence_parts = [entity_result.confidence, office_result.confidence, category_result.confidence]
    usable_confidences = [value for value in confidence_parts if value > 0]
    confidence = sum(usable_confidences) // len(usable_confidences) if usable_confidences else 0
    if (
        category == "Зарплата"
        and office
        and any("совпадение по сотруднику офиса" in item for item in office_result.trace)
        and "низким преимуществом" in office_result.reason
    ):
        confidence = max(confidence, 60)
    reason_parts = [entity_result.reason, office_result.reason, category_result.reason, destination_reason]
    trace = entity_result.trace + office_result.trace + category_result.trace + [destination_reason]

    requires_manual_review = False
    office_required_categories = {"Зарплата", "Аренда", "Интернет", "Коммунальные", "Услуги", "Прочее"}
    missing_office_for_required_category = bool(category in office_required_categories and not office)
    if destination is None:
        if runtime.rule_settings.routing.unresolved_route_goes_to_manual_review:
            requires_manual_review = True
        else:
            if office and category:
                destination = archive_root / office / category
            elif office:
                destination = archive_root / office / (category or "Прочее")
            elif category:
                destination = archive_root / category
            else:
                destination = archive_root / "Прочее"
            destination_reason = "путь собран по fallback-маршруту"
            trace.append(destination_reason)
    if not requires_manual_review and missing_office_for_required_category:
        if runtime.rule_settings.manual_review.send_missing_office_documents_to_manual_review:
            requires_manual_review = True
            destination_reason = "для категории требуется офис, файл отправлен в ручную проверку"
            trace.append(destination_reason)
    if not requires_manual_review and confidence < 55:
        if runtime.rule_settings.manual_review.send_low_confidence_documents_to_manual_review:
            requires_manual_review = True
            destination_reason = f"низкая уверенность классификации ({confidence}%)"
            trace.append(destination_reason)

    if requires_manual_review:
        destination = archive_root / "Требует_ручной_проверки"
        if not runtime.rule_settings.manual_review.preserve_readable_names_in_manual_review or not extracted.strip():
            new_name = path.name
        if "ручную проверку" not in destination_reason.lower():
            destination_reason = f"{destination_reason}, файл отправлен в ручную проверку"
    reason_parts[-1] = destination_reason
    reason = "; ".join(part for part in reason_parts if part)
    return Classification(
        destination=destination,
        office=office,
        category=category,
        entity=entity,
        reason=reason,
        new_name=new_name,
        confidence=confidence,
        requires_manual_review=requires_manual_review,
        trace=trace,
    )
