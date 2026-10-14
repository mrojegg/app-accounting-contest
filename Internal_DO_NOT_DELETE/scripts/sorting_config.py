from __future__ import annotations

import copy
import os
import re
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_RULES_FILE = Path(__file__).resolve().parent.parent / "project_rules" / "sorting_rules.md"
PUBLIC_RULES_FILE = Path(__file__).resolve().parent.parent / "project_rules" / "sorting_rules_clean.md"


def resolve_rules_file() -> Path:
    override = os.environ.get("SORTING_RULES_FILE", "").strip()
    if override:
        return Path(override).expanduser()
    if DEFAULT_RULES_FILE.exists():
        return DEFAULT_RULES_FILE
    if PUBLIC_RULES_FILE.exists():
        return PUBLIC_RULES_FILE
    return DEFAULT_RULES_FILE

DEFAULT_OFFICES: list[str] = []
DEFAULT_OFFICE_PEOPLE: dict[str, list[str]] = {}
DEFAULT_OFFICE_CONTRACTORS: dict[str, dict[str, list[str]]] = {}
DEFAULT_OFFICE_ENTITIES: dict[str, str] = {}


@dataclass(frozen=True)
class RuntimeConfig:
    offices: list[str]
    office_people: dict[str, list[str]]
    office_contractors: dict[str, dict[str, list[str]]]
    office_contractor_folders: dict[str, dict[str, dict[str, str]]]
    office_entities: dict[str, str]
    office_categories: dict[str, list[str]]
    rule_settings: "RuntimeRuleSettings" = field(default_factory=lambda: RuntimeRuleSettings())


@dataclass(frozen=True)
class RulesValidationIssue:
    line_number: int
    message: str


@dataclass(frozen=True)
class SalaryTableSettings:
    enabled: bool = True
    split_same_date_payments: bool = False
    total_column_title: str = "Общий итог"
    totals_row_title: str = "ИТОГО"


@dataclass(frozen=True)
class FolderCreationSettings:
    create_folders_only_when_documents_exist: bool = True
    do_not_create_empty_folders_in_advance: bool = True
    create_manual_review_folder_only_when_needed: bool = True
    create_special_subfolders_by_routing_rules: bool = True
    protect_existing_files_with_unique_suffix: bool = True


@dataclass(frozen=True)
class RoutingCategorySettings:
    route_by_document_text_first: bool = True
    route_office_before_category_finalization: bool = True
    use_contractors_as_category_signals: bool = True
    unresolved_route_goes_to_manual_review: bool = True


@dataclass(frozen=True)
class ManualReviewSettings:
    send_low_confidence_documents_to_manual_review: bool = True
    send_missing_office_documents_to_manual_review: bool = True
    preserve_readable_names_in_manual_review: bool = True
    create_manual_review_report: bool = True


@dataclass(frozen=True)
class NamingBehaviorSettings:
    use_extracted_text_for_naming: bool = True
    fallback_to_original_name_when_no_text: bool = True
    make_names_windows_safe: bool = True
    keep_unique_suffix_on_conflict: bool = True


@dataclass(frozen=True)
class CommissionSettings:
    detect_by_payment_text: bool = True
    use_office_entity_routing: bool = True
    create_office_excel: bool = True


@dataclass(frozen=True)
class TaxAndInsuranceSettings:
    detect_by_payment_phrases: bool = True
    use_office_entity_routing: bool = True
    create_tax_and_insurance_excel: bool = True


@dataclass(frozen=True)
class InternetProviderSettings:
    prioritize_known_providers: bool = True
    allow_special_provider_subfolders: bool = True
    create_subfolders_by_office_contractors: bool = False
    normalize_broken_provider_text: bool = True


@dataclass(frozen=True)
class RuntimeRuleSettings:
    salary_table: SalaryTableSettings = field(default_factory=SalaryTableSettings)
    folder_creation: FolderCreationSettings = field(default_factory=FolderCreationSettings)
    routing: RoutingCategorySettings = field(default_factory=RoutingCategorySettings)
    manual_review: ManualReviewSettings = field(default_factory=ManualReviewSettings)
    naming: NamingBehaviorSettings = field(default_factory=NamingBehaviorSettings)
    commissions: CommissionSettings = field(default_factory=CommissionSettings)
    taxes: TaxAndInsuranceSettings = field(default_factory=TaxAndInsuranceSettings)
    internet: InternetProviderSettings = field(default_factory=InternetProviderSettings)


SALARY_CREATE_RULE = "Для любого офиса с папкой `Зарплата` автоматически создается `Зарплата_<офис>.xlsx`."
SALARY_SPLIT_SAME_DATE_RULE = "Если у сотрудника несколько выплат в одну дату, создаются отдельные колонки `(2)`, `(3)` и далее."
SALARY_ONE_COLUMN_PER_DATE_RULE = "Для каждой фактической даты исполнения зарплатных платежей создается один столбец; суммы выплат сотрудника за эту дату учитываются в одной ячейке."
SALARY_TOTAL_COLUMN_PREFIX = "Итоговый столбец зарплатной таблицы называется "
SALARY_TOTALS_ROW_PREFIX = "Итоговая строка зарплатной таблицы называется "
FOLDER_CREATE_ON_DEMAND_RULE = "Папки офисов и категорий создаются только при первой реальной раскладке документа."
FOLDER_NO_EMPTY_RULE = "Пустые папки заранее не создаются."
FOLDER_MANUAL_REVIEW_ON_DEMAND_RULE = "Папка `Требует_ручной_проверки` создается только когда в нее реально попадает файл или отчет."
FOLDER_SPECIAL_SUBFOLDERS_RULE = "Специальные подпапки создаются только если сработало специальное правило маршрутизации."
FOLDER_UNIQUE_NAME_RULE = "При конфликте имен создается новый файл с безопасным уникальным суффиксом, а существующий файл не перезаписывается."
ROUTING_TEXT_FIRST_RULE = "Если текст документа читается, маршрутизация опирается на него раньше, чем на имя файла."
ROUTING_OFFICE_BEFORE_CATEGORY_RULE = "Сначала приложение старается понять офис, а уже потом окончательно фиксирует категорию и путь."
ROUTING_CONTRACTOR_SIGNAL_RULE = "Контрагент из правил офиса усиливает выбор категории и папки."
ROUTING_MANUAL_REVIEW_FALLBACK_RULE = "Если после всех проверок путь не собран уверенно, файл уходит в `Требует_ручной_проверки`."
MANUAL_LOW_CONFIDENCE_RULE = "Документы с низкой уверенностью распознавания отправляются в `Требует_ручной_проверки`."
MANUAL_MISSING_OFFICE_RULE = "Если тип документа понятен, но офис не определен, файл отправляется в `Требует_ручной_проверки`."
MANUAL_PRESERVE_READABLE_NAME_RULE = "В ручной проверке сохраняется читаемое имя из текста, если его удалось собрать."
MANUAL_CREATE_REPORT_RULE = "Для папки `Требует_ручной_проверки` автоматически создается `_report.txt` с причинами ручной обработки."
NAMING_EXTRACTED_TEXT_RULE = "Имя файла собирается из извлеченного текста документа, если полезные поля найдены."
NAMING_ORIGINAL_FALLBACK_RULE = "Если полезный текст не найден, приложение оставляет безопасный fallback от исходного имени файла."
NAMING_WINDOWS_SAFE_RULE = "Имена файлов автоматически приводятся к безопасному виду для macOS и Windows."
NAMING_UNIQUE_SUFFIX_RULE = "Если итоговое имя уже занято, приложение добавляет уникальный суффикс вместо перезаписи."
COMMISSION_DETECT_TEXT_RULE = "Банковские комиссии определяются по формулировкам платежа и банковским маркерам в тексте."
COMMISSION_ENTITY_ROUTING_RULE = "Комиссии стараются попасть в офис по юрлицу документа, даже если в имени файла это не видно."
COMMISSION_EXCEL_RULE = "Для любого офиса с папкой `Комиссии` автоматически создается `Комиссии_<офис>.xlsx`."
TAX_DETECT_PHRASE_RULE = "Налоги, НДФЛ, ЕНП и страховые взносы определяются по платежным формулировкам документа."
TAX_ENTITY_ROUTING_RULE = "Налоги и взносы стараются попасть в офис по юрлицу документа."
TAX_EXCEL_RULE = "Для любого офиса с папкой `Ндфл и Взносы` автоматически создаются `Распределение_налогов_<офис>.xlsx` и `Распределение_взносов_<офис>.xlsx`."
INTERNET_PROVIDER_PRIORITY_RULE = "Известные провайдеры и телеком-компании приоритетно относятся к категории `Интернет`."
INTERNET_PROVIDER_SUBFOLDER_RULE = "Для отдельных провайдеров могут создаваться специальные подпапки внутри `Интернет`, если это поддержано маршрутизацией."
INTERNET_OFFICE_CONTRACTOR_SUBFOLDER_RULE = "Для контрагентов с включенной настройкой `Создавать папку` приложение создает подпапку внутри категории."
INTERNET_NORMALIZE_BROKEN_TEXT_RULE = "Перед поиском провайдера приложение пытается исправить битый OCR и сломанную кодировку названий."


def _collect_section_bullets(block: str, header: str) -> list[str]:
    items: list[str] = []
    current_header: str | None = None

    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if re.match(r"^[^#\-\s][^:]*:\s*$", line):
            current_header = line[:-1]
            continue
        if current_header != header:
            continue
        if line.startswith("- "):
            items.append(line[2:].strip())
    return items


def validate_rules_content(content: str) -> list[RulesValidationIssue]:
    issues: list[RulesValidationIssue] = []
    if not content.strip():
        return [RulesValidationIssue(1, "Файл правил пуст.")]

    seen_offices: set[str] = set()
    current_office: str | None = None
    current_header: str | None = None

    for line_number, raw_line in enumerate(content.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("## "):
            current_office = None
            current_header = None
            continue

        office_match = re.match(r"^### Офис (\d+)\s*$", line)
        if office_match:
            office = office_match.group(1)
            if office in seen_offices:
                issues.append(RulesValidationIssue(line_number, f"Офис {office} объявлен повторно."))
            seen_offices.add(office)
            current_office = office
            current_header = None
            continue

        if line.startswith("### Офис ") and not office_match:
            issues.append(RulesValidationIssue(line_number, "Некорректный заголовок офиса. Ожидается формат `### Офис <номер>`."))
            continue

        section_match = re.match(r"^([^#\-\s][^:]*):\s*$", line)
        if section_match:
            current_header = section_match.group(1)
            continue

        if current_header == "Контрагенты" and line.startswith("- "):
            payload = line[2:].strip()
            if ":" not in payload:
                issues.append(
                    RulesValidationIssue(
                        line_number,
                        f"Некорректная строка контрагента для офиса {current_office or '?'}. Ожидается формат `- Категория: значения`.",
                    )
                )

    if not seen_offices:
        issues.append(RulesValidationIssue(1, "В файле правил не найдено ни одного блока `### Офис <номер>`."))

    return issues


def validate_rules_file(rules_file: Path | None = None) -> list[RulesValidationIssue]:
    rules_file = rules_file or resolve_rules_file()
    try:
        content = rules_file.read_text(encoding="utf-8")
    except Exception as exc:
        return [RulesValidationIssue(1, f"Не удалось прочитать файл правил: {exc}")]
    return validate_rules_content(content)


def parse_office_sections_from_rules(
    content: str,
    *,
    normalize_text,
) -> tuple[dict[str, list[str]], dict[str, dict[str, list[str]]], dict[str, str], dict[str, list[str]]]:
    people_map: dict[str, list[str]] = {}
    contractors_map: dict[str, dict[str, list[str]]] = {}
    entities_map: dict[str, str] = {}
    categories_map: dict[str, list[str]] = {}

    office_blocks = re.finditer(r"^### Офис (\d+)\n(.*?)(?=^### Офис \d+|^## |\Z)", content, re.M | re.S)
    for match in office_blocks:
        office = match.group(1)
        block = match.group(2)

        employees = _collect_section_bullets(block, "Сотрудники")
        if employees:
            people_map[office] = employees

        entities = _collect_section_bullets(block, "Юрлицо")
        if entities:
            raw_entity = entities[0].replace("`", "").replace("«", "").replace("»", "").replace('"', "").strip()
            entity = normalize_text(raw_entity).upper()
            entity = re.sub(r"^(ООО|ИП|АО|ПАО)\s+", "", entity).strip()
            if entity:
                entities_map[office] = entity

        categories = _collect_section_bullets(block, "Разрешенные категории по умолчанию")
        if categories:
            categories_map[office] = [item.strip().strip("`") for item in categories if item.strip().strip("`")]

        contractor_lines = _collect_section_bullets(block, "Контрагенты")
        if contractor_lines:
            office_contractors: dict[str, list[str]] = {}
            for line in contractor_lines:
                category_match = re.match(r"`?([^`:]+)`?\s*:\s*(.+)$", line)
                if not category_match:
                    continue
                category = category_match.group(1).strip()
                values, _ = _parse_contractor_line_payload(category_match.group(2), normalize_text=normalize_text)
                if values:
                    bucket = office_contractors.setdefault(category, [])
                    bucket.extend(normalize_text(value) for value in values)
            if office_contractors:
                contractors_map[office] = office_contractors

    return people_map, contractors_map, entities_map, categories_map


def _parse_contractor_line_payload(
    payload: str,
    *,
    normalize_text,
) -> tuple[list[str], dict[str, str]]:
    parts = [part.strip() for part in payload.split("|") if part.strip()]
    if len(parts) <= 1:
        values = [item.strip() for item in payload.split(",") if item.strip()]
        return values, {}

    folder_name = parts[0].strip().strip("`").strip()
    aliases: list[str] = []
    create_folder = False
    for part in parts[1:]:
        lowered = normalize_text(part)
        if lowered.startswith("папка:"):
            raw_value = lowered.split(":", 1)[1].strip()
            create_folder = raw_value in {"да", "true", "1", "yes"}
        elif lowered.startswith("алиасы:"):
            raw_aliases = part.split(":", 1)[1] if ":" in part else ""
            aliases.extend(item.strip() for item in raw_aliases.split(",") if item.strip())

    if not aliases and folder_name:
        aliases = [folder_name]

    folder_map: dict[str, str] = {}
    if create_folder and folder_name:
        for alias in [folder_name, *aliases]:
            normalized_alias = normalize_text(alias)
            if normalized_alias:
                folder_map[normalized_alias] = folder_name
    return aliases, folder_map


def parse_office_contractor_folder_rules(
    content: str,
    *,
    normalize_text,
) -> dict[str, dict[str, dict[str, str]]]:
    folder_rules: dict[str, dict[str, dict[str, str]]] = {}
    office_blocks = re.finditer(r"^### Офис (\d+)\n(.*?)(?=^### Офис \d+|^## |\Z)", content, re.M | re.S)
    for match in office_blocks:
        office = match.group(1)
        block = match.group(2)
        for line in _collect_section_bullets(block, "Контрагенты"):
            category_match = re.match(r"`?([^`:]+)`?\s*:\s*(.+)$", line)
            if not category_match:
                continue
            category = category_match.group(1).strip()
            _, folder_map = _parse_contractor_line_payload(category_match.group(2), normalize_text=normalize_text)
            if folder_map:
                folder_rules.setdefault(office, {}).setdefault(category, {}).update(folder_map)
    return folder_rules


def load_runtime_rule_settings_from_content(content: str) -> RuntimeRuleSettings:
    managed_rule_markers = [
        SALARY_CREATE_RULE,
        SALARY_SPLIT_SAME_DATE_RULE,
        SALARY_ONE_COLUMN_PER_DATE_RULE,
        SALARY_TOTAL_COLUMN_PREFIX,
        SALARY_TOTALS_ROW_PREFIX,
        FOLDER_CREATE_ON_DEMAND_RULE,
        FOLDER_NO_EMPTY_RULE,
        FOLDER_MANUAL_REVIEW_ON_DEMAND_RULE,
        FOLDER_SPECIAL_SUBFOLDERS_RULE,
        FOLDER_UNIQUE_NAME_RULE,
        ROUTING_TEXT_FIRST_RULE,
        ROUTING_OFFICE_BEFORE_CATEGORY_RULE,
        ROUTING_CONTRACTOR_SIGNAL_RULE,
        ROUTING_MANUAL_REVIEW_FALLBACK_RULE,
        MANUAL_LOW_CONFIDENCE_RULE,
        MANUAL_MISSING_OFFICE_RULE,
        MANUAL_PRESERVE_READABLE_NAME_RULE,
        MANUAL_CREATE_REPORT_RULE,
        NAMING_EXTRACTED_TEXT_RULE,
        NAMING_ORIGINAL_FALLBACK_RULE,
        NAMING_WINDOWS_SAFE_RULE,
        NAMING_UNIQUE_SUFFIX_RULE,
        COMMISSION_DETECT_TEXT_RULE,
        COMMISSION_ENTITY_ROUTING_RULE,
        COMMISSION_EXCEL_RULE,
        TAX_DETECT_PHRASE_RULE,
        TAX_ENTITY_ROUTING_RULE,
        TAX_EXCEL_RULE,
        INTERNET_PROVIDER_PRIORITY_RULE,
        INTERNET_PROVIDER_SUBFOLDER_RULE,
        INTERNET_OFFICE_CONTRACTOR_SUBFOLDER_RULE,
        INTERNET_NORMALIZE_BROKEN_TEXT_RULE,
    ]
    if not any(marker in content for marker in managed_rule_markers):
        return RuntimeRuleSettings()

    salary_table = SalaryTableSettings(
        enabled=SALARY_CREATE_RULE in content,
        split_same_date_payments=(
            SALARY_SPLIT_SAME_DATE_RULE in content
            and SALARY_ONE_COLUMN_PER_DATE_RULE not in content
        ),
    )
    total_column_match = re.search(rf"{re.escape(SALARY_TOTAL_COLUMN_PREFIX)}`([^`]+)`", content)
    if total_column_match:
        salary_table = SalaryTableSettings(
            enabled=salary_table.enabled,
            split_same_date_payments=salary_table.split_same_date_payments,
            total_column_title=total_column_match.group(1).strip(),
            totals_row_title=salary_table.totals_row_title,
        )
    totals_row_match = re.search(rf"{re.escape(SALARY_TOTALS_ROW_PREFIX)}`([^`]+)`", content)
    if totals_row_match:
        salary_table = SalaryTableSettings(
            enabled=salary_table.enabled,
            split_same_date_payments=salary_table.split_same_date_payments,
            total_column_title=salary_table.total_column_title,
            totals_row_title=totals_row_match.group(1).strip(),
        )

    return RuntimeRuleSettings(
        salary_table=salary_table,
        folder_creation=FolderCreationSettings(
            create_folders_only_when_documents_exist=FOLDER_CREATE_ON_DEMAND_RULE in content,
            do_not_create_empty_folders_in_advance=FOLDER_NO_EMPTY_RULE in content,
            create_manual_review_folder_only_when_needed=FOLDER_MANUAL_REVIEW_ON_DEMAND_RULE in content,
            create_special_subfolders_by_routing_rules=FOLDER_SPECIAL_SUBFOLDERS_RULE in content,
            protect_existing_files_with_unique_suffix=FOLDER_UNIQUE_NAME_RULE in content,
        ),
        routing=RoutingCategorySettings(
            route_by_document_text_first=ROUTING_TEXT_FIRST_RULE in content,
            route_office_before_category_finalization=ROUTING_OFFICE_BEFORE_CATEGORY_RULE in content,
            use_contractors_as_category_signals=ROUTING_CONTRACTOR_SIGNAL_RULE in content,
            unresolved_route_goes_to_manual_review=ROUTING_MANUAL_REVIEW_FALLBACK_RULE in content,
        ),
        manual_review=ManualReviewSettings(
            send_low_confidence_documents_to_manual_review=MANUAL_LOW_CONFIDENCE_RULE in content,
            send_missing_office_documents_to_manual_review=MANUAL_MISSING_OFFICE_RULE in content,
            preserve_readable_names_in_manual_review=MANUAL_PRESERVE_READABLE_NAME_RULE in content,
            create_manual_review_report=MANUAL_CREATE_REPORT_RULE in content,
        ),
        naming=NamingBehaviorSettings(
            use_extracted_text_for_naming=NAMING_EXTRACTED_TEXT_RULE in content,
            fallback_to_original_name_when_no_text=NAMING_ORIGINAL_FALLBACK_RULE in content,
            make_names_windows_safe=NAMING_WINDOWS_SAFE_RULE in content,
            keep_unique_suffix_on_conflict=NAMING_UNIQUE_SUFFIX_RULE in content,
        ),
        commissions=CommissionSettings(
            detect_by_payment_text=COMMISSION_DETECT_TEXT_RULE in content,
            use_office_entity_routing=COMMISSION_ENTITY_ROUTING_RULE in content,
            create_office_excel=COMMISSION_EXCEL_RULE in content,
        ),
        taxes=TaxAndInsuranceSettings(
            detect_by_payment_phrases=TAX_DETECT_PHRASE_RULE in content,
            use_office_entity_routing=TAX_ENTITY_ROUTING_RULE in content,
            create_tax_and_insurance_excel=TAX_EXCEL_RULE in content,
        ),
        internet=InternetProviderSettings(
            prioritize_known_providers=INTERNET_PROVIDER_PRIORITY_RULE in content,
            allow_special_provider_subfolders=INTERNET_PROVIDER_SUBFOLDER_RULE in content,
            create_subfolders_by_office_contractors=INTERNET_OFFICE_CONTRACTOR_SUBFOLDER_RULE in content,
            normalize_broken_provider_text=INTERNET_NORMALIZE_BROKEN_TEXT_RULE in content,
        ),
    )


def load_runtime_rule_settings(rules_file: Path | None = None) -> RuntimeRuleSettings:
    rules_file = rules_file or resolve_rules_file()
    try:
        content = rules_file.read_text(encoding="utf-8")
    except Exception:
        return RuntimeRuleSettings()
    return load_runtime_rule_settings_from_content(content)


def should_merge_legacy_defaults(rules_file: Path) -> bool:
    try:
        return rules_file.resolve() == DEFAULT_RULES_FILE.resolve()
    except Exception:
        return False


def load_runtime_config(
    *,
    normalize_text,
    rules_file: Path | None = None,
) -> RuntimeConfig:
    rules_file = rules_file or resolve_rules_file()
    merge_legacy_defaults = should_merge_legacy_defaults(rules_file)
    office_people = copy.deepcopy(DEFAULT_OFFICE_PEOPLE) if merge_legacy_defaults else {}
    office_contractors = copy.deepcopy(DEFAULT_OFFICE_CONTRACTORS) if merge_legacy_defaults else {}
    office_contractor_folders: dict[str, dict[str, dict[str, str]]] = {}
    office_entities = copy.deepcopy(DEFAULT_OFFICE_ENTITIES) if merge_legacy_defaults else {}
    office_categories = {} if not merge_legacy_defaults else {}
    offices = list(DEFAULT_OFFICES) if merge_legacy_defaults else []

    try:
        content = rules_file.read_text(encoding="utf-8")
    except Exception:
        return RuntimeConfig(
            offices=offices,
            office_people=office_people,
            office_contractors=office_contractors,
            office_contractor_folders=office_contractor_folders,
            office_entities=office_entities,
            office_categories=office_categories,
            rule_settings=RuntimeRuleSettings(),
        )

    parsed_people, parsed_contractors, parsed_entities, parsed_categories = parse_office_sections_from_rules(
        content,
        normalize_text=normalize_text,
    )
    office_contractor_folders = parse_office_contractor_folder_rules(content, normalize_text=normalize_text)

    for office, people in parsed_people.items():
        office_people[office] = list(dict.fromkeys([*office_people.get(office, []), *people]))
    for office, categories in parsed_contractors.items():
        office_bucket = office_contractors.setdefault(office, {})
        for category, values in categories.items():
            office_bucket[category] = list(dict.fromkeys([*office_bucket.get(category, []), *values]))
    for office, entity in parsed_entities.items():
        office_entities[office] = entity
    for office, categories in parsed_categories.items():
        office_categories[office] = list(dict.fromkeys(categories))

    parsed_offices = sorted(
        {*office_people.keys(), *office_contractors.keys(), *office_entities.keys(), *office_categories.keys()},
        key=lambda item: int(item) if item.isdigit() else item,
    )
    if parsed_offices:
        offices = parsed_offices

    return RuntimeConfig(
        offices=offices,
        office_people=office_people,
        office_contractors=office_contractors,
        office_contractor_folders=office_contractor_folders,
        office_entities=office_entities,
        office_categories=office_categories,
        rule_settings=load_runtime_rule_settings_from_content(content),
    )
