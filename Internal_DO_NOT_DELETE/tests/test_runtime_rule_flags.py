from __future__ import annotations

import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import sort_documents as sd
import sorting_classification as sc
import sorting_config as config
from sorting_models import DetectionResult


def patched_runtime(base: sc.ClassificationRuntime, **kwargs) -> sc.ClassificationRuntime:
    payload = {
        "entity_patterns": base.entity_patterns,
        "entity_account_patterns": base.entity_account_patterns,
        "entity_source_hint_patterns": base.entity_source_hint_patterns,
        "office_people": base.office_people,
        "office_contractors": base.office_contractors,
        "office_contractor_folders": base.office_contractor_folders,
        "office_entities": base.office_entities,
        "office_categories": base.office_categories,
        "offices": base.offices,
        "category_patterns": base.category_patterns,
        "tax_patterns": base.tax_patterns,
        "insurance_accident_patterns": base.insurance_accident_patterns,
        "usn_patterns": base.usn_patterns,
        "bank_commission_patterns": base.bank_commission_patterns,
        "rule_settings": base.rule_settings,
    }
    payload.update(kwargs)
    return sc.ClassificationRuntime(**payload)


class RuntimeRuleFlagsTests(unittest.TestCase):
    def test_unresolved_fallback_toggle_changes_manual_review(self) -> None:
        base = patched_runtime(sd.classification_runtime(), rule_settings=config.RuntimeRuleSettings())
        settings = replace(
            base.rule_settings,
            routing=replace(base.rule_settings.routing, unresolved_route_goes_to_manual_review=False),
            manual_review=replace(
                base.rule_settings.manual_review,
                send_low_confidence_documents_to_manual_review=False,
                send_missing_office_documents_to_manual_review=False,
            ),
        )
        runtime = patched_runtime(base, rule_settings=settings)

        with tempfile.TemporaryDirectory() as tmpdir:
            archive_root = Path(tmpdir) / "archive"
            source = Path(tmpdir) / "unknown.txt"
            source.write_text("", encoding="utf-8")

            result = sd.classification.classify_document(
                source,
                archive_root,
                runtime=runtime,
                file_text=lambda path: "",
                normalize_text=sd.normalize_text,
                match_any=sd.match_any,
                bounded_confidence=sd.bounded_confidence,
                bank_payment_recipient=sd.bank_payment_recipient,
                bank_payment_purpose=sd.bank_payment_purpose,
                safe_filename=sd.safe_filename,
            )

        self.assertFalse(result.requires_manual_review)
        self.assertEqual(result.destination, archive_root / "Прочее")

    def test_contractor_signal_toggle_changes_office_and_category_detection(self) -> None:
        base = patched_runtime(
            sd.classification_runtime(),
            rule_settings=replace(
                config.RuntimeRuleSettings(),
                internet=replace(config.RuntimeRuleSettings().internet, prioritize_known_providers=False),
            ),
        )
        runtime_with = patched_runtime(
            base,
            office_contractors={**base.office_contractors, "98": {"Интернет": ["дилаин"]}},
        )
        runtime_without = patched_runtime(
            runtime_with,
            rule_settings=replace(
                runtime_with.rule_settings,
                routing=replace(runtime_with.rule_settings.routing, use_contractors_as_category_signals=False),
            ),
        )
        text = sd.normalize_text("ООО ОБРАЗЕЦ Дилайн оплата договора")

        with_result = sd.classification.classify_document(
            Path("sample.txt"),
            Path("/tmp/archive"),
            runtime=runtime_with,
            file_text=lambda path: text,
            normalize_text=sd.normalize_text,
            match_any=sd.match_any,
            bounded_confidence=sd.bounded_confidence,
            bank_payment_recipient=sd.bank_payment_recipient,
            bank_payment_purpose=sd.bank_payment_purpose,
            safe_filename=sd.safe_filename,
        )
        without_result = sd.classification.classify_document(
            Path("sample.txt"),
            Path("/tmp/archive"),
            runtime=runtime_without,
            file_text=lambda path: text,
            normalize_text=sd.normalize_text,
            match_any=sd.match_any,
            bounded_confidence=sd.bounded_confidence,
            bank_payment_recipient=sd.bank_payment_recipient,
            bank_payment_purpose=sd.bank_payment_purpose,
            safe_filename=sd.safe_filename,
        )

        self.assertEqual(with_result.office, "98")
        self.assertEqual(with_result.category, "Интернет")
        self.assertIsNone(without_result.office)
        self.assertNotEqual(without_result.category, "Интернет")

    def test_office_before_category_toggle_prioritizes_allowed_office_category(self) -> None:
        base_source = sd.classification_runtime()
        base = patched_runtime(
            base_source,
            office_contractors={**base_source.office_contractors, "98": {"Интернет": ["дилаин"]}},
            office_categories={**base_source.office_categories, "98": ["Интернет"]},
            rule_settings=replace(
                config.RuntimeRuleSettings(),
                internet=replace(config.RuntimeRuleSettings().internet, prioritize_known_providers=False),
            ),
        )
        text = sd.normalize_text("дилаин оказание услуг")

        with_result = sd.classification.detect_category_signal(
            text,
            "",
            runtime=base,
            bank_payment_recipient=sd.bank_payment_recipient,
            bank_payment_purpose=sd.bank_payment_purpose,
            normalize_text=sd.normalize_text,
            match_any=sd.match_any,
            bounded_confidence=sd.bounded_confidence,
            office="98",
        )
        without_runtime = patched_runtime(
            base,
            rule_settings=replace(
                base.rule_settings,
                routing=replace(base.rule_settings.routing, route_office_before_category_finalization=False),
            ),
        )
        without_result = sd.classification.detect_category_signal(
            text,
            "",
            runtime=without_runtime,
            bank_payment_recipient=sd.bank_payment_recipient,
            bank_payment_purpose=sd.bank_payment_purpose,
            normalize_text=sd.normalize_text,
            match_any=sd.match_any,
            bounded_confidence=sd.bounded_confidence,
            office="98",
        )

        self.assertEqual(with_result.value, "Интернет")
        self.assertEqual(without_result.value, "Услуги")

    def test_internet_subfolder_toggle_changes_destination(self) -> None:
        base = patched_runtime(sd.classification_runtime(), rule_settings=config.RuntimeRuleSettings())
        text = sd.normalize_text("ООО ПРИМЕР Искрателеком оплата доступа в интернет")

        with_result = sd.classification.classify_document(
            Path("provider.txt"),
            Path("/tmp/archive"),
            runtime=base,
            file_text=lambda path: text,
            normalize_text=sd.normalize_text,
            match_any=sd.match_any,
            bounded_confidence=sd.bounded_confidence,
            bank_payment_recipient=sd.bank_payment_recipient,
            bank_payment_purpose=sd.bank_payment_purpose,
            safe_filename=sd.safe_filename,
        )
        without_runtime = patched_runtime(
            base,
            rule_settings=replace(
                base.rule_settings,
                internet=replace(base.rule_settings.internet, allow_special_provider_subfolders=False),
            ),
        )
        without_result = sd.classification.classify_document(
            Path("provider.txt"),
            Path("/tmp/archive"),
            runtime=without_runtime,
            file_text=lambda path: text,
            normalize_text=sd.normalize_text,
            match_any=sd.match_any,
            bounded_confidence=sd.bounded_confidence,
            bank_payment_recipient=sd.bank_payment_recipient,
            bank_payment_purpose=sd.bank_payment_purpose,
            safe_filename=sd.safe_filename,
        )

        self.assertEqual(with_result.destination, Path("/tmp/archive") / "109" / "Интернет" / "Искрателеком")
        self.assertEqual(without_result.destination, Path("/tmp/archive") / "109" / "Интернет")

    def test_office_internet_contractors_can_create_provider_subfolders(self) -> None:
        base_settings = config.RuntimeRuleSettings()
        settings = replace(
            base_settings,
            internet=replace(base_settings.internet, create_subfolders_by_office_contractors=True),
        )
        base = patched_runtime(
            sd.classification_runtime(),
            office_contractors={"98": {"Интернет": ["билайн", "ооо вип-телеком-сервис"]}},
            office_contractor_folders={"98": {"Интернет": {"ооо вип-телеком-сервис": "Вип-Телеком-Сервис"}}},
            rule_settings=settings,
        )
        text = sd.normalize_text("ООО ОБРАЗЕЦ ООО ВИП-ТЕЛЕКОМ-СЕРВИС услуги связи")

        result = sd.classification.classify_document(
            Path("provider.txt"),
            Path("/tmp/archive"),
            runtime=base,
            file_text=lambda path: text,
            normalize_text=sd.normalize_text,
            match_any=sd.match_any,
            bounded_confidence=sd.bounded_confidence,
            bank_payment_recipient=sd.bank_payment_recipient,
            bank_payment_purpose=sd.bank_payment_purpose,
            safe_filename=sd.safe_filename,
        )

        self.assertEqual(result.office, "98")
        self.assertEqual(result.category, "Интернет")
        self.assertEqual(result.destination, Path("/tmp/archive") / "98" / "Интернет" / "Вип-Телеком-Сервис")

    def test_office_contractors_can_create_subfolders_for_any_category(self) -> None:
        base_settings = config.RuntimeRuleSettings()
        settings = replace(
            base_settings,
            internet=replace(base_settings.internet, create_subfolders_by_office_contractors=True),
        )
        runtime = patched_runtime(
            sd.classification_runtime(),
            office_contractors={"98": {"Аренда": ["ип рахматулин"]}},
            office_contractor_folders={"98": {"Аренда": {"ип рахматулин": "ИП Рахматулин"}}},
            office_categories={"98": ["Аренда"]},
            rule_settings=settings,
        )
        text = sd.normalize_text("ООО ОБРАЗЕЦ счет ИП Рахматулин аренда помещения")

        result = sd.classification.classify_document(
            Path("rent.txt"),
            Path("/tmp/archive"),
            runtime=runtime,
            file_text=lambda path: text,
            normalize_text=sd.normalize_text,
            match_any=sd.match_any,
            bounded_confidence=sd.bounded_confidence,
            bank_payment_recipient=sd.bank_payment_recipient,
            bank_payment_purpose=sd.bank_payment_purpose,
            safe_filename=sd.safe_filename,
        )

        self.assertEqual(result.destination, Path("/tmp/archive") / "98" / "Аренда" / "ИП Рахматулин")

    def test_missing_office_manual_review_toggle_changes_decision(self) -> None:
        base = patched_runtime(sd.classification_runtime(), rule_settings=config.RuntimeRuleSettings())
        runtime_without = patched_runtime(
            base,
            rule_settings=replace(
                base.rule_settings,
                manual_review=replace(base.rule_settings.manual_review, send_missing_office_documents_to_manual_review=False),
            ),
        )

        def run(runtime: sc.ClassificationRuntime):
            with tempfile.TemporaryDirectory() as tmpdir:
                archive_root = Path(tmpdir) / "archive"
                source = Path(tmpdir) / "doc.pdf"
                source.write_text("stub", encoding="utf-8")
                with mock.patch.object(
                    sc,
                    "detect_entity_signal",
                    return_value=DetectionResult("ПРИМЕР", "юрлицо ПРИМЕР", 80, ["entity"]),
                ), mock.patch.object(
                    sc,
                    "detect_office_signal",
                    return_value=DetectionResult(None, "офис не найден", 0, ["office"]),
                ), mock.patch.object(
                    sc,
                    "detect_category_signal",
                    return_value=DetectionResult("Интернет", "категория Интернет", 80, ["category"]),
                ), mock.patch.object(
                    sc,
                    "destination_for",
                    return_value=(archive_root / "Интернет", "test destination"),
                ):
                    return sd.classification.classify_document(
                        source,
                        archive_root,
                        runtime=runtime,
                        file_text=lambda path: "raw text",
                        normalize_text=sd.normalize_text,
                        match_any=sd.match_any,
                        bounded_confidence=sd.bounded_confidence,
                        bank_payment_recipient=sd.bank_payment_recipient,
                        bank_payment_purpose=sd.bank_payment_purpose,
                        safe_filename=sd.safe_filename,
                    )

        with_result = run(base)
        without_result = run(runtime_without)

        self.assertTrue(with_result.requires_manual_review)
        self.assertFalse(without_result.requires_manual_review)
        self.assertEqual(without_result.destination.name, "Интернет")

    def test_low_confidence_manual_review_toggle_changes_decision(self) -> None:
        base = patched_runtime(sd.classification_runtime(), rule_settings=config.RuntimeRuleSettings())
        runtime_without = patched_runtime(
            base,
            rule_settings=replace(
                base.rule_settings,
                manual_review=replace(base.rule_settings.manual_review, send_low_confidence_documents_to_manual_review=False),
            ),
        )

        def run(runtime: sc.ClassificationRuntime):
            with tempfile.TemporaryDirectory() as tmpdir:
                archive_root = Path(tmpdir) / "archive"
                source = Path(tmpdir) / "doc.pdf"
                source.write_text("stub", encoding="utf-8")
                with mock.patch.object(
                    sc,
                    "detect_entity_signal",
                    return_value=DetectionResult("ОБРАЗЕЦ", "юрлицо ОБРАЗЕЦ", 20, ["entity"]),
                ), mock.patch.object(
                    sc,
                    "detect_office_signal",
                    return_value=DetectionResult("98", "офис 98", 50, ["office"]),
                ), mock.patch.object(
                    sc,
                    "detect_category_signal",
                    return_value=DetectionResult("Прочее", "категория Прочее", 20, ["category"]),
                ), mock.patch.object(
                    sc,
                    "destination_for",
                    return_value=(archive_root / "98" / "Прочее", "test destination"),
                ):
                    return sd.classification.classify_document(
                        source,
                        archive_root,
                        runtime=runtime,
                        file_text=lambda path: "raw text",
                        normalize_text=sd.normalize_text,
                        match_any=sd.match_any,
                        bounded_confidence=sd.bounded_confidence,
                        bank_payment_recipient=sd.bank_payment_recipient,
                        bank_payment_purpose=sd.bank_payment_purpose,
                        safe_filename=sd.safe_filename,
                    )

        with_result = run(base)
        without_result = run(runtime_without)

        self.assertTrue(with_result.requires_manual_review)
        self.assertFalse(without_result.requires_manual_review)
        self.assertEqual(without_result.destination.name, "Прочее")

    def test_route_by_document_text_first_toggle_allows_filename_hints(self) -> None:
        base = patched_runtime(sd.classification_runtime(), rule_settings=config.RuntimeRuleSettings())
        runtime = patched_runtime(
            base,
            rule_settings=replace(
                base.rule_settings,
                routing=replace(base.rule_settings.routing, route_by_document_text_first=False),
            ),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            archive_root = Path(tmpdir) / "archive"
            source = Path(tmpdir) / "счет_чеботарев_5.pdf"
            source.write_text("", encoding="utf-8")
            result = sd.classification.classify_document(
                source,
                archive_root,
                runtime=runtime,
                file_text=lambda path: "",
                normalize_text=sd.normalize_text,
                match_any=sd.match_any,
                bounded_confidence=sd.bounded_confidence,
                bank_payment_recipient=sd.bank_payment_recipient,
                bank_payment_purpose=sd.bank_payment_purpose,
                safe_filename=sd.safe_filename,
            )

        self.assertEqual(result.office, "109")
        self.assertEqual(result.category, "Аренда")

    def test_commission_detection_toggle_disables_bank_commission_text(self) -> None:
        base = patched_runtime(sd.classification_runtime(), rule_settings=config.RuntimeRuleSettings())
        disabled = patched_runtime(
            base,
            rule_settings=replace(
                base.rule_settings,
                commissions=replace(base.rule_settings.commissions, detect_by_payment_text=False),
            ),
        )
        text = sd.normalize_text("комиссия банка за пакет услуг")

        enabled_result = sd.classification.detect_category_signal(
            text,
            "",
            runtime=base,
            bank_payment_recipient=sd.bank_payment_recipient,
            bank_payment_purpose=sd.bank_payment_purpose,
            normalize_text=sd.normalize_text,
            match_any=sd.match_any,
            bounded_confidence=sd.bounded_confidence,
        )
        disabled_result = sd.classification.detect_category_signal(
            text,
            "",
            runtime=disabled,
            bank_payment_recipient=sd.bank_payment_recipient,
            bank_payment_purpose=sd.bank_payment_purpose,
            normalize_text=sd.normalize_text,
            match_any=sd.match_any,
            bounded_confidence=sd.bounded_confidence,
        )

        self.assertEqual(enabled_result.value, "Комиссии")
        self.assertNotEqual(disabled_result.value, "Комиссии")

    def test_tax_detection_toggle_disables_tax_phrases(self) -> None:
        base = patched_runtime(sd.classification_runtime(), rule_settings=config.RuntimeRuleSettings())
        disabled = patched_runtime(
            base,
            rule_settings=replace(
                base.rule_settings,
                taxes=replace(base.rule_settings.taxes, detect_by_payment_phrases=False),
            ),
        )
        text = sd.normalize_text("платежное поручение ндфл единый налоговый платеж")

        enabled_result = sd.classification.detect_category_signal(
            text,
            "",
            runtime=base,
            bank_payment_recipient=sd.bank_payment_recipient,
            bank_payment_purpose=sd.bank_payment_purpose,
            normalize_text=sd.normalize_text,
            match_any=sd.match_any,
            bounded_confidence=sd.bounded_confidence,
        )
        disabled_result = sd.classification.detect_category_signal(
            text,
            "",
            runtime=disabled,
            bank_payment_recipient=sd.bank_payment_recipient,
            bank_payment_purpose=sd.bank_payment_purpose,
            normalize_text=sd.normalize_text,
            match_any=sd.match_any,
            bounded_confidence=sd.bounded_confidence,
        )

        self.assertEqual(enabled_result.value, "Налоги")
        self.assertNotIn(disabled_result.value, {"Налоги", "Взносы", "УСН"})

    def test_entity_routing_toggle_disables_commission_office_by_entity(self) -> None:
        base = patched_runtime(
            sd.classification_runtime(),
            office_entities={"44": "НОВОЕ"},
            office_categories={"44": ["Комиссии"]},
            offices=["44"],
            rule_settings=config.RuntimeRuleSettings(),
        )
        disabled = patched_runtime(
            base,
            rule_settings=replace(
                base.rule_settings,
                commissions=replace(base.rule_settings.commissions, use_office_entity_routing=False),
            ),
        )

        enabled_destination, _ = sd.classification.destination_for(
            Path("commission.txt"),
            Path("/tmp/archive"),
            None,
            "Комиссии",
            "НОВОЕ",
            runtime=base,
            file_text=lambda path: "",
            normalize_text=sd.normalize_text,
        )
        disabled_destination, _ = sd.classification.destination_for(
            Path("commission.txt"),
            Path("/tmp/archive"),
            None,
            "Комиссии",
            "НОВОЕ",
            runtime=disabled,
            file_text=lambda path: "",
            normalize_text=sd.normalize_text,
        )

        self.assertEqual(enabled_destination, Path("/tmp/archive") / "44" / "Комиссии")
        self.assertIsNone(disabled_destination)

    def test_preserve_manual_review_name_toggle_changes_manual_name(self) -> None:
        base = patched_runtime(sd.classification_runtime(), rule_settings=config.RuntimeRuleSettings())
        disabled = patched_runtime(
            base,
            rule_settings=replace(
                base.rule_settings,
                manual_review=replace(base.rule_settings.manual_review, preserve_readable_names_in_manual_review=False),
            ),
        )

        def run(runtime: sc.ClassificationRuntime):
            with tempfile.TemporaryDirectory() as tmpdir:
                archive_root = Path(tmpdir) / "archive"
                source = Path(tmpdir) / "original.pdf"
                source.write_text("stub", encoding="utf-8")
                with mock.patch.object(
                    sc,
                    "detect_entity_signal",
                    return_value=DetectionResult(None, "юрлицо не найдено", 0, ["entity"]),
                ), mock.patch.object(
                    sc,
                    "detect_office_signal",
                    return_value=DetectionResult(None, "офис не найден", 0, ["office"]),
                ), mock.patch.object(
                    sc,
                    "detect_category_signal",
                    return_value=DetectionResult("Прочее", "категория Прочее", 20, ["category"]),
                ):
                    return sd.classification.classify_document(
                        source,
                        archive_root,
                        runtime=runtime,
                        file_text=lambda path: "readable text",
                        normalize_text=sd.normalize_text,
                        match_any=sd.match_any,
                        bounded_confidence=sd.bounded_confidence,
                        bank_payment_recipient=sd.bank_payment_recipient,
                        bank_payment_purpose=sd.bank_payment_purpose,
                        safe_filename=lambda path, office, category, entity: "readable.pdf",
                    )

        self.assertEqual(run(base).new_name, "readable.pdf")
        self.assertEqual(run(disabled).new_name, "original.pdf")

    def test_manual_file_rules_override_classification_by_file_name(self) -> None:
        runtime = patched_runtime(sd.classification_runtime(), rule_settings=config.RuntimeRuleSettings())

        with tempfile.TemporaryDirectory() as tmpdir, mock.patch.dict(
            sc.MANUAL_FILE_RULES,
            {
                "manual.pdf": {
                    "office": "120",
                    "category": "Интернет",
                    "entity": "ТЕСТКО",
                    "new_name": "Manual_Result.pdf",
                    "reason": "ручное тестовое правило",
                }
            },
            clear=True,
        ):
            archive_root = Path(tmpdir) / "archive"
            source = Path(tmpdir) / "manual.pdf"
            source.write_text("без признаков", encoding="utf-8")
            result = sd.classification.classify_document(
                source,
                archive_root,
                runtime=runtime,
                file_text=lambda path: "без признаков",
                normalize_text=sd.normalize_text,
                match_any=sd.match_any,
                bounded_confidence=sd.bounded_confidence,
                bank_payment_recipient=sd.bank_payment_recipient,
                bank_payment_purpose=sd.bank_payment_purpose,
                safe_filename=sd.safe_filename,
            )

        self.assertEqual(result.destination, archive_root / "120" / "Интернет")
        self.assertEqual(result.new_name, "Manual_Result.pdf")
        self.assertEqual(result.office, "120")
        self.assertFalse(result.requires_manual_review)


if __name__ == "__main__":
    unittest.main()
