from __future__ import annotations

import json
from pathlib import Path


MANUAL_FILE_RULES_FILE = Path(__file__).resolve().parent.parent / "project_rules" / "manual_file_rules.json"

DEFAULT_MANUAL_FILE_RULES: dict[str, dict[str, str]] = {}


SPECIAL_FOLDER_RULES = [
    {
        "office": "109",
        "category": "Интернет",
        "contains_any": ["искрателеком"],
        "subfolder": "Искрателеком",
        "reason": "специальная папка провайдера Искрателеком",
    },
    {
        "office": "109",
        "category": "Интернет",
        "contains_any": ["комитерн корп", "комитен корп"],
        "subfolder": "Комитерн Корп",
        "reason": "специальная папка провайдера Комитерн Корп",
    },
]


def load_manual_file_rules(manual_rules_file: Path = MANUAL_FILE_RULES_FILE) -> dict[str, dict[str, str]]:
    try:
        payload = json.loads(manual_rules_file.read_text(encoding="utf-8"))
    except Exception:
        return DEFAULT_MANUAL_FILE_RULES
    if not isinstance(payload, dict):
        return DEFAULT_MANUAL_FILE_RULES
    normalized: dict[str, dict[str, str]] = {}
    for key, value in payload.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        normalized[key.lower()] = {
            "office": str(value.get("office", "")),
            "category": str(value.get("category", "")),
            "entity": str(value.get("entity", "")),
            "new_name": str(value.get("new_name", "")),
            "reason": str(value.get("reason", "")),
        }
    return normalized or DEFAULT_MANUAL_FILE_RULES


MANUAL_FILE_RULES = load_manual_file_rules()
