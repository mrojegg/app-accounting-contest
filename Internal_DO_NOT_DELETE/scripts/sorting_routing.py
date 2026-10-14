from __future__ import annotations

from pathlib import Path
from typing import Callable

import sorting_sorter_runtime as sorter_runtime
from sorting_provider_subfolders import internet_provider_subfolder
from sorting_rules_data import SPECIAL_FOLDER_RULES


def destination_for(
    source: Path,
    archive_root: Path,
    office: str | None,
    category: str | None,
    entity: str | None,
    *,
    file_text: Callable[[Path], str],
    normalize_text: Callable[[str], str],
) -> tuple[Path | None, str]:
    source_text = normalize_text(file_text(source))
    source_name = normalize_text(source.name)
    haystack = f"{source_text} {source_name}"

    def office_for_entity(default_office: str | None = None) -> str | None:
        if office:
            return office
        if not entity:
            return default_office
        matches = [office_id for office_id, office_entity in sorter_runtime.OFFICE_ENTITIES.items() if office_entity == entity]
        if len(matches) == 1:
            return matches[0]
        return default_office

    if category == "Комиссии":
        commission_office = office_for_entity("109" if entity == "ПРИМЕР" else "98" if entity == "ОБРАЗЕЦ" else None)
        if commission_office:
            return archive_root / commission_office / "Комиссии", f"комиссии {entity or ''} относятся к {commission_office}".strip()
        return None, "для комиссии не найдено юрлицо"

    if category == "Взносы":
        insurance_office = office_for_entity("109" if entity == "ПРИМЕР" else "98" if entity == "ОБРАЗЕЦ" else None)
        if insurance_office:
            return archive_root / insurance_office / "Ндфл и Взносы", f"взносы {entity or ''} относятся к {insurance_office}".strip()
        return None, "для взносов не найдено юрлицо"

    if category == "УСН":
        if not entity:
            return None, "для УСН не найдено юрлицо"
        return archive_root / "УСН" / entity, "корневая папка УСН"

    if category == "Налоги":
        tax_office = office_for_entity("109" if entity == "ПРИМЕР" else "98" if entity == "ОБРАЗЕЦ" else None)
        if tax_office:
            return archive_root / tax_office / "Ндфл и Взносы", f"налоги {entity or ''} относятся к {tax_office}".strip()
        return None, "для налогов не найдено юрлицо"

    if office == "109" and any(token in haystack for token in ["ип тестовпоставщик", "тестовпоставщик"]):
        return archive_root / "109" / "ИП Тестовпоставщик", "специальная папка ИП Тестовпоставщик"

    if office == "109" and any(token in haystack for token in ["ип демопоставщик", "демопоставщик"]):
        return archive_root / "109" / "ИП Демопоставщикой", "специальная папка ИП Демопоставщикой"

    if office and category and sorter_runtime.RULE_SETTINGS.internet.allow_special_provider_subfolders:
        for rule in SPECIAL_FOLDER_RULES:
            if rule["office"] != office or rule["category"] != category:
                continue
            if any(token in haystack for token in rule["contains_any"]):
                return archive_root / office / category / rule["subfolder"], rule["reason"]

    if (
        office
        and category
        and sorter_runtime.RULE_SETTINGS.internet.allow_special_provider_subfolders
        and sorter_runtime.RULE_SETTINGS.internet.create_subfolders_by_office_contractors
    ):
        provider_folder = internet_provider_subfolder(
            office=office,
            category=category,
            haystack=haystack,
            office_contractor_folders=sorter_runtime.OFFICE_CONTRACTOR_FOLDERS,
        )
        if provider_folder:
            return archive_root / office / category / provider_folder, f"папка провайдера {provider_folder} из правил офиса"

    if office and category and sorter_runtime.RULE_SETTINGS.internet.create_subfolders_by_office_contractors:
        folder_map = sorter_runtime.OFFICE_CONTRACTOR_FOLDERS.get(office, {}).get(category, {})
        for keyword, folder_name in sorted(folder_map.items(), key=lambda item: len(item[0]), reverse=True):
            if keyword in haystack:
                return archive_root / office / category / folder_name, f"папка контрагента {folder_name} из правил офиса"

    if office and category:
        return archive_root / office / category, "офисная папка"

    return None, "недостаточно данных для папки назначения"
