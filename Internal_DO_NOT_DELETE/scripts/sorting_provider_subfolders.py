from __future__ import annotations

import re


PROVIDER_FOLDER_ALIASES = [
    (("билайн", "вымпелком", "beeline"), "Билайн"),
    (("вип-телеком", "vip telecom", "vip-telecom"), "Вип-Телеком-Сервис"),
    (("искрателеком", "искра"), "Искрателеком"),
    (("комитерн корп", "комитен корп"), "Комитерн Корп"),
    (("таттелеком",), "Таттелеком"),
    (("вест-колл", "вест колл", "westcall", "west call"), "Вест-Колл"),
]


def provider_subfolder_name(keyword: str) -> str:
    normalized = keyword.strip().strip("`").replace('"', "").lower()
    for aliases, folder_name in PROVIDER_FOLDER_ALIASES:
        if any(alias in normalized for alias in aliases):
            return folder_name

    normalized = re.sub(r"^(ооо|пао|ао|ип)\s+", "", normalized).strip()
    normalized = re.sub(r'[<>:"/\\|?*]+', " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip(" ._-")
    if not normalized:
        return "Провайдер"
    return " ".join(part[:1].upper() + part[1:] for part in normalized.split())


def internet_provider_subfolder(
    *,
    office: str | None,
    category: str | None,
    haystack: str,
    office_contractor_folders: dict[str, dict[str, dict[str, str]]],
) -> str | None:
    if not office or category != "Интернет":
        return None
    folder_map = office_contractor_folders.get(office, {}).get("Интернет", {})
    for keyword, folder_name in sorted(folder_map.items(), key=lambda item: len(item[0]), reverse=True):
        if keyword in haystack:
            return folder_name or provider_subfolder_name(keyword)
    return None
