import XCTest
@testable import SortingFilesNativeApp

final class RulesEditingTests: XCTestCase {
    func testGeneralRulesPersistAfterReload() throws {
        let original = """
        # Правила сортировки
        Старый текст

        ## 11. Офисы
        ### Офис 76
        Сотрудники:
        - Иван Иванов
        """

        let updated = RulesEditing.replaceGeneralSection(
            in: original,
            newSection: """
            # Правила сортировки
            Новый общий текст
            """
        )

        XCTAssertEqual(
            RulesEditing.extractGeneralSection(from: updated),
            "# Правила сортировки\nНовый общий текст"
        )
        XCTAssertTrue(updated.contains("### Офис 76"))
    }

    func testOfficeRulesPersistAfterReload() throws {
        let original = """
        # Правила сортировки

        ## 11. Офисы
        ### Офис 76
        Сотрудники:
        - Иван Иванов

        ### Офис 98
        Сотрудники:
        - Петр Демофамилияагб
        """

        let newOfficeSection = """
        ### Офис 76
        Сотрудники:
        - Новый Сотрудник
        """

        let updated = RulesEditing.replaceOfficeSection(in: original, office: "76", newSection: newOfficeSection)

        XCTAssertEqual(
            RulesEditing.extractOfficeSection(from: updated, office: "76"),
            newOfficeSection
        )
        XCTAssertTrue(updated.contains("### Офис 98"))
    }

    func testAddOfficeMakesItReadableThroughOfficeEditorLogic() throws {
        let original = """
        # Правила сортировки

        ## 11. Офисы
        ### Офис 76
        Сотрудники:
        - Иван Иванов

        ## 13. Общие специальные правила
        """

        let updated = RulesEditing.addOffice(in: original, office: "120")
        let offices = RulesEditing.loadOfficeList(from: updated)
        let officeSection = RulesEditing.extractOfficeSection(from: updated, office: "120")

        XCTAssertTrue(offices.contains("120"))
        XCTAssertTrue(officeSection.contains("### Офис 120"))
        XCTAssertTrue(officeSection.contains("Разрешенные категории по умолчанию"))
    }

    func testRemoveOfficeDropsOnlySelectedOffice() throws {
        let original = """
        # Правила сортировки

        ## 11. Офисы
        ### Офис 76
        Сотрудники:
        - Иван Иванов

        ### Офис 98
        Сотрудники:
        - Петр Демофамилияагб

        ## 13. Общие специальные правила
        - Правило
        """

        let updated = RulesEditing.removeOffice(in: original, office: "76")

        XCTAssertFalse(updated.contains("### Офис 76"))
        XCTAssertFalse(updated.contains("Иван Иванов"))
        XCTAssertTrue(updated.contains("### Офис 98"))
        XCTAssertTrue(updated.contains("Петр Демофамилияагб"))
        XCTAssertTrue(updated.contains("## 13. Общие специальные правила"))
    }

    func testEnsureEditableRulesFileDoesNotOverwriteExistingUserRules() throws {
        let fileManager = FileManager.default
        let tempRoot = fileManager.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        let appSupport = tempRoot.appendingPathComponent("AppSupport", isDirectory: true)
        let rulesFile = appSupport.appendingPathComponent("sorting_rules.md")
        let bundled = tempRoot.appendingPathComponent("default_sorting_rules.md")
        let legacy = tempRoot.appendingPathComponent("legacy_rules.md")

        defer { try? fileManager.removeItem(at: tempRoot) }

        try fileManager.createDirectory(at: tempRoot, withIntermediateDirectories: true)
        try "bundled".write(to: bundled, atomically: true, encoding: .utf8)
        try "legacy".write(to: legacy, atomically: true, encoding: .utf8)

        try AppPaths.ensureEditableRulesFile(
            fileManager: fileManager,
            rulesFile: rulesFile,
            bundledDefaultRulesFile: bundled,
            legacyRulesFile: legacy
        )
        XCTAssertEqual(try String(contentsOf: rulesFile, encoding: .utf8), "bundled")

        try "user changed rules".write(to: rulesFile, atomically: true, encoding: .utf8)

        try AppPaths.ensureEditableRulesFile(
            fileManager: fileManager,
            rulesFile: rulesFile,
            bundledDefaultRulesFile: bundled,
            legacyRulesFile: legacy
        )
        XCTAssertEqual(try String(contentsOf: rulesFile, encoding: .utf8), "user changed rules")
    }

    func testStructuredOfficeFormRoundTrip() throws {
        let content = """
        # Правила сортировки

        ## 11. Офисы
        ### Офис 120
        Юрлицо:
        - `ООО НОВОЕ`

        Разрешенные категории по умолчанию:
        - `Зарплата`
        - `Интернет`

        Сотрудники:
        - Иван Иванов
        - Петр Демофамилияагб

        Контрагенты:
        - `Интернет`: Провайдер 1, Провайдер 2
        """

        let form = RulesEditing.parseOfficeForm(from: content, office: "120")

        XCTAssertEqual(form.entity, "ООО НОВОЕ")
        XCTAssertEqual(form.allowedCategories, ["Зарплата", "Интернет"])
        XCTAssertEqual(form.employees, ["Иван Иванов", "Петр Демофамилияагб"])
        XCTAssertEqual(form.contractorRules["Интернет"]?.map(\.name) ?? [], ["Провайдер 1", "Провайдер 2"])

        let rebuilt = RulesEditing.buildOfficeSection(from: form)
        XCTAssertTrue(rebuilt.contains("### Офис 120"))
        XCTAssertTrue(rebuilt.contains("- `ООО НОВОЕ`"))
        XCTAssertTrue(rebuilt.contains("- `Интернет`: Провайдер 1 | папка: нет | алиасы: Провайдер 1"))
        XCTAssertTrue(rebuilt.contains("- `Интернет`: Провайдер 2 | папка: нет | алиасы: Провайдер 2"))
    }

    func testOfficeSectionMatchingRequiresExactNumber() throws {
        let content = """
        # Правила сортировки

        ## 11. Офисы
        ### Офис 760
        Сотрудники:
        - Чужой Сотрудник

        ### Офис 76
        Сотрудники:
        - Нужный Сотрудник
        """

        XCTAssertTrue(RulesEditing.extractOfficeSection(from: content, office: "76").contains("Нужный Сотрудник"))
        XCTAssertFalse(RulesEditing.extractOfficeSection(from: content, office: "76").contains("Чужой Сотрудник"))
    }

    func testReplaceAndRemoveOfficeRequireExactNumber() throws {
        let content = """
        # Правила сортировки

        ## 11. Офисы
        ### Офис 760
        Сотрудники:
        - Чужой Сотрудник

        ### Офис 76
        Сотрудники:
        - Нужный Сотрудник
        """
        let replacement = """
        ### Офис 76
        Сотрудники:
        - Новый Сотрудник
        """

        let replaced = RulesEditing.replaceOfficeSection(in: content, office: "76", newSection: replacement)
        XCTAssertTrue(replaced.contains("### Офис 760"))
        XCTAssertTrue(replaced.contains("Чужой Сотрудник"))
        XCTAssertTrue(replaced.contains("Новый Сотрудник"))
        XCTAssertFalse(RulesEditing.extractOfficeSection(from: replaced, office: "76").contains("Нужный Сотрудник"))

        let removed = RulesEditing.removeOffice(in: replaced, office: "76")
        XCTAssertTrue(removed.contains("### Офис 760"))
        XCTAssertFalse(removed.contains("### Офис 76\n"))
    }

    func testAddOfficeRejectsNonNumericOfficeNumber() throws {
        let content = """
        # Правила сортировки

        ## 11. Офисы
        ### Офис 76
        Сотрудники:
        - Иван Иванов

        ## 13. Общие специальные правила
        """

        XCTAssertEqual(RulesEditing.addOffice(in: content, office: "abc"), content)
        XCTAssertEqual(RulesEditing.addOffice(in: content, office: "76A"), content)
        XCTAssertEqual(RulesEditing.addOffice(in: content, office: "10-2"), content)
        XCTAssertTrue(RulesEditing.addOffice(in: content, office: "109").contains("### Офис 109"))
    }

    func testOfficeEntityLegalPrefixRoundTripPreservesIpAoPao() throws {
        for entity in ["ООО РОМАШКА", "ИП Иванов", "АО Компания", "ПАО Банк"] {
            let content = """
            # Правила сортировки

            ## 11. Офисы
            ### Офис 120
            Юрлицо:
            - `\(entity)`

            Разрешенные категории по умолчанию:
            - `Зарплата`

            Сотрудники:
            - Иван Иванов
            """
            let form = RulesEditing.parseOfficeForm(from: content, office: "120")
            let rebuilt = RulesEditing.buildOfficeSection(from: form)

            XCTAssertEqual(form.entity, entity)
            XCTAssertTrue(rebuilt.contains("- `\(entity)`"))
        }
    }

    func testSalaryContractorIsDroppedFromOfficeFormAndOutput() throws {
        let content = """
        # Правила сортировки

        ## 11. Офисы
        ### Офис 120
        Юрлицо:
        - `ООО НОВОЕ`

        Разрешенные категории по умолчанию:
        - `Зарплата`

        Сотрудники:
        - Иван Иванов

        Контрагенты:
        - `Зарплата`: Технический контрагент
        - `Интернет`: Провайдер 1
        """

        let form = RulesEditing.parseOfficeForm(from: content, office: "120")

        XCTAssertNil(form.contractorRules["Зарплата"])
        XCTAssertEqual(form.contractorRules["Интернет"]?.map(\.name) ?? [], ["Провайдер 1"])

        let rebuilt = RulesEditing.buildOfficeSection(from: form)
        XCTAssertFalse(rebuilt.contains("- `Зарплата`:"))
        XCTAssertTrue(rebuilt.contains("- `Интернет`: Провайдер 1 | папка: нет | алиасы: Провайдер 1"))
    }

    func testRemovedArchiveCategoryIsDroppedFromOfficeForm() throws {
        let form = OfficeRuleForm(
            office: "120",
            entity: "НОВОЕ",
            allowedCategories: ["Зарплата", "Новая папка", "Интернет"],
            employees: ["Иван Иванов"],
            contractorRules: [
                "Новая папка": [ContractorRuleForm(name: "Контрагент X", createFolder: true, aliases: ["Контрагент X"])],
                "Интернет": [ContractorRuleForm(name: "Провайдер 1", createFolder: false, aliases: ["Провайдер 1"])],
            ]
        )

        let normalized = RulesEditing.normalizeOfficeForm(
            form,
            allowedCategories: ["Зарплата", "Интернет"]
        )

        XCTAssertEqual(normalized.allowedCategories, ["Зарплата", "Интернет"])
        XCTAssertNil(normalized.contractorRules["Новая папка"])
        XCTAssertEqual(normalized.contractorRules["Интернет"]?.map(\.name) ?? [], ["Провайдер 1"])
    }

    func testOfficeFormKeepsAtLeastOneCategory() throws {
        let form = OfficeRuleForm(
            office: "120",
            entity: "НОВОЕ",
            allowedCategories: [],
            employees: [],
            contractorRules: [:]
        )

        let normalized = RulesEditing.normalizeOfficeForm(
            form,
            allowedCategories: ["Зарплата", "Интернет"]
        )

        XCTAssertEqual(normalized.allowedCategories, ["Зарплата"])
    }

    func testGeneralSpecialRulesRoundTrip() throws {
        let content = """
        # Правила сортировки

        ## 11. Офисы
        ### Офис 100
        Сотрудники:
        - Иван Иванов

        ## 13. Общие специальные правила

        - Первое правило
        - Второе правило
        """

        let parsed = RulesEditing.parseGeneralRules(from: content)
        XCTAssertEqual(parsed.specialRules, ["Первое правило", "Второе правило"])

        let updated = RulesEditing.replaceGeneralSpecialRules(
            in: content,
            rules: ["Новое правило", "Еще одно правило"]
        )

        XCTAssertTrue(updated.contains("## 13. Общие специальные правила"))
        XCTAssertTrue(updated.contains("- Новое правило"))
        XCTAssertTrue(updated.contains("- Еще одно правило"))
    }

    func testGeneralRulesFormRoundTrip() throws {
        let content = """
        # Регламент сортировки документов

        ## 1. Назначение файла

        Первая строка.
        Вторая строка.

        ## 2. Общие принципы

        - Принцип 1

        ## 3. Базовая структура архива

        Внутри офисов могут создаваться папки:

        - `Зарплата`
        - `Интернет`

        ## 4. Порядок определения папки

        1. Шаг 1
        2. Шаг 2

        ## 5. Таблицы

        - Таблица 1

        ## 6. Именование файлов

        Используется формат:

        `<id>_<date>`

        ## 7. Обработка плохо читаемых файлов

        - Правило 7

        ## 8. Дополнительные обработчики документов

        - OCR

        ## 11. Офисы
        ### Офис 120
        Сотрудники:
        - Иван Иванов

        ## 13. Общие специальные правила

        - Спец 1
        """

        let form = RulesEditing.parseGeneralRules(from: content)
        XCTAssertEqual(form.purposeLines, ["Первая строка.", "Вторая строка."])
        XCTAssertEqual(form.principles, ["Принцип 1"])
        XCTAssertEqual(form.archiveFolders, ["`Зарплата`", "`Интернет`"].map { $0.trimmingCharacters(in: CharacterSet(charactersIn: "`")) })
        XCTAssertEqual(form.folderOrder, ["Шаг 1", "Шаг 2"])
        XCTAssertEqual(form.tableRules, ["Таблица 1"])
        XCTAssertEqual(form.namingFormat, "<id>_<date>")
        XCTAssertEqual(form.lowQualityRules, ["Правило 7"])
        XCTAssertEqual(form.extraHandlers, ["OCR"])
        XCTAssertEqual(form.specialRules, ["Спец 1"])

        let rebuilt = RulesEditing.buildGeneralSection(from: form)
        XCTAssertTrue(rebuilt.contains("## 1. Назначение файла"))
        XCTAssertTrue(rebuilt.contains("Первая строка."))
        XCTAssertTrue(rebuilt.contains("- Принцип 1"))
        XCTAssertTrue(rebuilt.contains("`<id>_<date>`"))
        XCTAssertTrue(rebuilt.contains("- Спец 1"))
    }

    func testSalaryTableSettingsParsingAndMerge() throws {
        let rules = [
            "Для любого офиса с папкой `Зарплата` автоматически создается `Зарплата_<офис>.xlsx`.",
            "Для зарплатной таблицы используется правило: одна строка = один сотрудник.",
            "Для зарплатной таблицы используется правило: отдельная колонка на каждую дату выплаты.",
            "Если у сотрудника несколько выплат в одну дату, создаются отдельные колонки `(2)`, `(3)` и далее.",
            "Итоговый столбец зарплатной таблицы называется `Сумма по сотруднику`.",
            "Итоговая строка зарплатной таблицы называется `Сумма по офису`.",
            "Для любого офиса с папкой `Комиссии` автоматически создается `Комиссии_<офис>.xlsx`.",
        ]

        let settings = RulesEditing.parseSalaryTableSettings(from: rules)
        XCTAssertTrue(settings.isEnabled)
        XCTAssertTrue(settings.splitSameDatePaymentsIntoSeparateColumns)
        XCTAssertEqual(settings.totalColumnTitle, "Сумма по сотруднику")
        XCTAssertEqual(settings.totalsRowTitle, "Сумма по офису")

        let remaining = RulesEditing.nonSalaryTableRules(from: rules)
        XCTAssertEqual(remaining, [])

        let merged = RulesEditing.mergeTableRules(nonSalaryRules: remaining, salarySettings: settings)
        XCTAssertTrue(merged.contains("Итоговый столбец зарплатной таблицы называется `Сумма по сотруднику`."))
        XCTAssertTrue(merged.contains("Итоговая строка зарплатной таблицы называется `Сумма по офису`."))
        XCTAssertTrue(merged.contains("Для любого офиса с папкой `Комиссии` автоматически создается `Комиссии_<офис>.xlsx`."))
    }

    func testFolderCreationSettingsParsingAndMerge() throws {
        let rules = [
            "Папки офисов и категорий создаются только при первой реальной раскладке документа.",
            "Пустые папки заранее не создаются.",
            "Папка `Требует_ручной_проверки` создается только когда в нее реально попадает файл или отчет.",
            "Специальные подпапки создаются только если сработало специальное правило маршрутизации.",
            "При конфликте имен создается новый файл с безопасным уникальным суффиксом, а существующий файл не перезаписывается.",
            "Эти правила являются рабочей базой офисов приложения.",
        ]

        let settings = RulesEditing.parseFolderCreationSettings(from: rules)
        XCTAssertTrue(settings.createFoldersOnlyWhenDocumentsExist)
        XCTAssertTrue(settings.doNotCreateEmptyFoldersInAdvance)
        XCTAssertTrue(settings.createManualReviewFolderOnlyWhenNeeded)
        XCTAssertTrue(settings.createSpecialSubfoldersByRoutingRules)
        XCTAssertTrue(settings.protectExistingFilesWithUniqueSuffix)

        let remaining = RulesEditing.nonFolderCreationSpecialRules(from: rules)
        XCTAssertEqual(remaining, ["Эти правила являются рабочей базой офисов приложения."])

        let merged = RulesEditing.mergeSpecialRules(
            nonFolderRules: remaining,
            folderSettings: settings,
            routingSettings: RulesEditing.defaultRoutingCategorySettings(),
            manualReviewSettings: RulesEditing.defaultManualReviewSettings(),
            namingSettings: RulesEditing.defaultNamingBehaviorSettings(),
            commissionSettings: RulesEditing.defaultCommissionSettings(),
            taxSettings: RulesEditing.defaultTaxAndInsuranceSettings(),
            internetSettings: RulesEditing.defaultInternetProviderSettings()
        )
        XCTAssertTrue(merged.contains("Папки офисов и категорий создаются только при первой реальной раскладке документа."))
        XCTAssertTrue(merged.contains("При конфликте имен создается новый файл с безопасным уникальным суффиксом, а существующий файл не перезаписывается."))
    }

    func testHumanReadableSpecialRuleSettingsParsing() throws {
        let rules = [
            "Если текст документа читается, маршрутизация опирается на него раньше, чем на имя файла.",
            "Сначала приложение старается понять офис, а уже потом окончательно фиксирует категорию и путь.",
            "Контрагент из правил офиса усиливает выбор категории и папки.",
            "Если после всех проверок путь не собран уверенно, файл уходит в `Требует_ручной_проверки`.",
            "Документы с низкой уверенностью распознавания отправляются в `Требует_ручной_проверки`.",
            "Если тип документа понятен, но офис не определен, файл отправляется в `Требует_ручной_проверки`.",
            "В ручной проверке сохраняется читаемое имя из текста, если его удалось собрать.",
            "Для папки `Требует_ручной_проверки` автоматически создается `_report.txt` с причинами ручной обработки.",
            "Имя файла собирается из извлеченного текста документа, если полезные поля найдены.",
            "Если полезный текст не найден, приложение оставляет безопасный fallback от исходного имени файла.",
            "Имена файлов автоматически приводятся к безопасному виду для macOS и Windows.",
            "Если итоговое имя уже занято, приложение добавляет уникальный суффикс вместо перезаписи.",
            "Банковские комиссии определяются по формулировкам платежа и банковским маркерам в тексте.",
            "Комиссии стараются попасть в офис по юрлицу документа, даже если в имени файла это не видно.",
            "Налоги, НДФЛ, ЕНП и страховые взносы определяются по платежным формулировкам документа.",
            "Налоги и взносы стараются попасть в офис по юрлицу документа.",
            "Известные провайдеры и телеком-компании приоритетно относятся к категории `Интернет`.",
            "Для отдельных провайдеров могут создаваться специальные подпапки внутри `Интернет`, если это поддержано маршрутизацией.",
            "Для контрагентов с включенной настройкой `Создавать папку` приложение создает подпапку внутри категории.",
            "Перед поиском провайдера приложение пытается исправить битый OCR и сломанную кодировку названий.",
        ]

        let routing = RulesEditing.parseRoutingCategorySettings(from: rules)
        let manual = RulesEditing.parseManualReviewSettings(from: rules)
        let naming = RulesEditing.parseNamingBehaviorSettings(from: rules)
        let commissions = RulesEditing.parseCommissionSettings(from: rules, tableRules: [])
        let taxes = RulesEditing.parseTaxAndInsuranceSettings(from: rules, tableRules: [])
        let internet = RulesEditing.parseInternetProviderSettings(from: rules)

        XCTAssertTrue(routing.routeByDocumentTextFirst)
        XCTAssertTrue(routing.routeOfficeBeforeCategoryFinalization)
        XCTAssertTrue(routing.useContractorsAsCategorySignals)
        XCTAssertTrue(routing.unresolvedRouteGoesToManualReview)
        XCTAssertTrue(manual.sendLowConfidenceDocumentsToManualReview)
        XCTAssertTrue(manual.sendMissingOfficeDocumentsToManualReview)
        XCTAssertTrue(manual.preserveReadableNamesInManualReview)
        XCTAssertTrue(manual.createManualReviewReport)
        XCTAssertTrue(naming.useExtractedTextForNaming)
        XCTAssertTrue(naming.fallbackToOriginalNameWhenNoText)
        XCTAssertTrue(naming.makeNamesWindowsSafe)
        XCTAssertTrue(naming.keepUniqueSuffixOnConflict)
        XCTAssertTrue(commissions.detectByPaymentText)
        XCTAssertTrue(commissions.useOfficeEntityRouting)
        XCTAssertTrue(taxes.detectByPaymentPhrases)
        XCTAssertTrue(taxes.useOfficeEntityRouting)
        XCTAssertTrue(internet.prioritizeKnownProviders)
        XCTAssertTrue(internet.allowSpecialProviderSubfolders)
        XCTAssertTrue(internet.createSubfoldersByOfficeContractors)
        XCTAssertTrue(internet.normalizeBrokenProviderText)
    }

    func testRequiredOperationalRulesAreRestoredWithoutChangingOfficeData() throws {
        let disabledSalary = SalaryTableSettings(
            isEnabled: false,
            splitSameDatePaymentsIntoSeparateColumns: false,
            totalColumnTitle: "Итог сотрудника",
            totalsRowTitle: "Итог офиса"
        )
        let disabledManualReview = ManualReviewSettings(
            sendLowConfidenceDocumentsToManualReview: false,
            sendMissingOfficeDocumentsToManualReview: false,
            preserveReadableNamesInManualReview: false,
            createManualReviewReport: false
        )
        let disabledSpecialRules = RulesEditing.mergeSpecialRules(
            nonFolderRules: ["Пользовательское правило"],
            folderSettings: FolderCreationSettings(
                createFoldersOnlyWhenDocumentsExist: false,
                doNotCreateEmptyFoldersInAdvance: false,
                createManualReviewFolderOnlyWhenNeeded: false,
                createSpecialSubfoldersByRoutingRules: false,
                protectExistingFilesWithUniqueSuffix: false
            ),
            routingSettings: RoutingCategorySettings(
                routeByDocumentTextFirst: false,
                routeOfficeBeforeCategoryFinalization: false,
                useContractorsAsCategorySignals: false,
                unresolvedRouteGoesToManualReview: false
            ),
            manualReviewSettings: disabledManualReview,
            namingSettings: NamingBehaviorSettings(
                useExtractedTextForNaming: false,
                fallbackToOriginalNameWhenNoText: false,
                makeNamesWindowsSafe: false,
                keepUniqueSuffixOnConflict: false
            ),
            commissionSettings: CommissionSettings(
                detectByPaymentText: false,
                useOfficeEntityRouting: false,
                createOfficeExcel: false
            ),
            taxSettings: TaxAndInsuranceSettings(
                detectByPaymentPhrases: false,
                useOfficeEntityRouting: false,
                createTaxAndInsuranceExcel: false
            ),
            internetSettings: InternetProviderSettings(
                prioritizeKnownProviders: false,
                allowSpecialProviderSubfolders: false,
                createSubfoldersByOfficeContractors: false,
                normalizeBrokenProviderText: false
            )
        )
        let general = RulesEditing.buildGeneralSection(
            from: GeneralRulesForm(
                purposeLines: ["Назначение"],
                principles: ["Принцип"],
                archiveFolders: ["Зарплата"],
                folderOrder: ["Порядок"],
                tableRules: RulesEditing.mergeTableRules(
                    nonSalaryRules: ["Пользовательская таблица"],
                    salarySettings: disabledSalary,
                    commissionSettings: CommissionSettings(
                        detectByPaymentText: false,
                        useOfficeEntityRouting: false,
                        createOfficeExcel: false
                    ),
                    taxSettings: TaxAndInsuranceSettings(
                        detectByPaymentPhrases: false,
                        useOfficeEntityRouting: false,
                        createTaxAndInsuranceExcel: false
                    )
                ),
                namingFormat: "<id>",
                lowQualityRules: ["Низкое качество"],
                extraHandlers: ["OCR"],
                specialRules: disabledSpecialRules
            )
        )
        let officeSection = """
        ## 11. Офисы

        ### Офис 76
        Юрлицо:
        - `ООО ПРИМЕР`

        Сотрудники:
        - Иван Иванов
        """
        let original = general + "\n\n" + officeSection

        let updated = RulesEditing.enforcingRequiredOperationalRules(in: original)
        let form = RulesEditing.parseGeneralRules(from: updated)
        let salary = RulesEditing.parseSalaryTableSettings(from: form.tableRules)
        let folders = RulesEditing.parseFolderCreationSettings(from: form.specialRules)
        let routing = RulesEditing.parseRoutingCategorySettings(from: form.specialRules)
        let manual = RulesEditing.parseManualReviewSettings(from: form.specialRules)
        let naming = RulesEditing.parseNamingBehaviorSettings(from: form.specialRules)
        let commissions = RulesEditing.parseCommissionSettings(from: form.specialRules, tableRules: form.tableRules)
        let taxes = RulesEditing.parseTaxAndInsuranceSettings(from: form.specialRules, tableRules: form.tableRules)
        let internet = RulesEditing.parseInternetProviderSettings(from: form.specialRules)

        XCTAssertTrue(salary.isEnabled)
        XCTAssertFalse(salary.splitSameDatePaymentsIntoSeparateColumns)
        XCTAssertEqual(salary.totalColumnTitle, "Итог сотрудника")
        XCTAssertEqual(salary.totalsRowTitle, "Итог офиса")
        XCTAssertTrue(form.tableRules.contains("Для каждой фактической даты исполнения зарплатных платежей создается один столбец; суммы выплат сотрудника за эту дату учитываются в одной ячейке."))
        XCTAssertFalse(form.tableRules.contains("Если у сотрудника несколько выплат в одну дату, создаются отдельные колонки `(2)`, `(3)` и далее."))
        XCTAssertTrue(folders.createFoldersOnlyWhenDocumentsExist)
        XCTAssertTrue(folders.doNotCreateEmptyFoldersInAdvance)
        XCTAssertTrue(folders.createManualReviewFolderOnlyWhenNeeded)
        XCTAssertTrue(folders.createSpecialSubfoldersByRoutingRules)
        XCTAssertTrue(folders.protectExistingFilesWithUniqueSuffix)
        XCTAssertTrue(routing.routeByDocumentTextFirst)
        XCTAssertTrue(routing.routeOfficeBeforeCategoryFinalization)
        XCTAssertTrue(routing.useContractorsAsCategorySignals)
        XCTAssertTrue(routing.unresolvedRouteGoesToManualReview)
        XCTAssertTrue(manual.sendLowConfidenceDocumentsToManualReview)
        XCTAssertTrue(manual.sendMissingOfficeDocumentsToManualReview)
        XCTAssertFalse(manual.preserveReadableNamesInManualReview)
        XCTAssertFalse(manual.createManualReviewReport)
        XCTAssertTrue(naming.useExtractedTextForNaming)
        XCTAssertTrue(naming.fallbackToOriginalNameWhenNoText)
        XCTAssertTrue(naming.makeNamesWindowsSafe)
        XCTAssertTrue(naming.keepUniqueSuffixOnConflict)
        XCTAssertTrue(commissions.detectByPaymentText)
        XCTAssertTrue(commissions.useOfficeEntityRouting)
        XCTAssertTrue(commissions.createOfficeExcel)
        XCTAssertTrue(taxes.detectByPaymentPhrases)
        XCTAssertTrue(taxes.useOfficeEntityRouting)
        XCTAssertTrue(taxes.createTaxAndInsuranceExcel)
        XCTAssertTrue(internet.prioritizeKnownProviders)
        XCTAssertTrue(internet.allowSpecialProviderSubfolders)
        XCTAssertTrue(internet.createSubfoldersByOfficeContractors)
        XCTAssertTrue(internet.normalizeBrokenProviderText)
        XCTAssertTrue(form.tableRules.contains("Пользовательская таблица"))
        XCTAssertTrue(form.specialRules.contains("Пользовательское правило"))
        XCTAssertTrue(form.specialRules.contains(
            "Если у одного сотрудника найдены две выплаты зарплаты с одинаковой суммой, все совпавшие чеки отправляются в ручную проверку до создания таблиц."
        ))
        XCTAssertTrue(form.specialRules.contains(
            "Подтвержденный повторный зарплатный чек сохраняется в `Требует_ручной_проверки/Исключенные_повторы`, не переносится в офис и не учитывается в таблицах."
        ))
        XCTAssertTrue(form.specialRules.contains(
            "После успешного создания таблиц и объединенных PDF отдельные чеки зарплаты и комиссий переносятся в `Исходные_чеки/<офис>/<категория>`."
        ))
        XCTAssertEqual(updated.components(separatedBy: "## 13. Общие специальные правила").count - 1, 1)
        XCTAssertLessThan(
            try XCTUnwrap(updated.range(of: "## 11. Офисы")?.lowerBound),
            try XCTUnwrap(updated.range(of: "## 13. Общие специальные правила")?.lowerBound)
        )
        XCTAssertEqual(
            RulesEditing.extractOfficeSection(from: updated, office: "76"),
            RulesEditing.extractOfficeSection(from: original, office: "76")
        )
    }
}
