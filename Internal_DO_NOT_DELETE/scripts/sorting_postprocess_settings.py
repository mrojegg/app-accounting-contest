from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


SALARY_CREATE_RULE = "Для любого офиса с папкой `Зарплата` автоматически создается `Зарплата_<офис>.xlsx`."
COMMISSION_EXCEL_RULE = "Для любого офиса с папкой `Комиссии` автоматически создается `Комиссии_<офис>.xlsx`."
TAX_EXCEL_RULE = "Для любого офиса с папкой `Ндфл и Взносы` автоматически создаются `Распределение_налогов_<офис>.xlsx` и `Распределение_взносов_<офис>.xlsx`."


@dataclass
class PostprocessSettings:
    salary_table_enabled: bool = True
    commission_excel_enabled: bool = True
    tax_and_insurance_excel_enabled: bool = True


def rules_file_path() -> Path:
    override = os.environ.get("SORTING_RULES_FILE", "").strip()
    if override:
        return Path(override).expanduser()
    return Path(__file__).resolve().parents[1] / "project_rules" / "sorting_rules.md"


def load_postprocess_settings() -> PostprocessSettings:
    try:
        content = rules_file_path().read_text(encoding="utf-8")
    except Exception:
        return PostprocessSettings()

    return PostprocessSettings(
        salary_table_enabled=SALARY_CREATE_RULE in content,
        commission_excel_enabled=COMMISSION_EXCEL_RULE in content,
        tax_and_insurance_excel_enabled=TAX_EXCEL_RULE in content,
    )
