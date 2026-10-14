import Foundation

struct OfficeRuleForm {
    var office: String
    var entity: String
    var allowedCategories: [String]
    var employees: [String]
    var contractorRules: [String: [ContractorRuleForm]]
}

struct ContractorRuleForm: Identifiable, Hashable {
    var id = UUID()
    var name: String
    var createFolder: Bool
    var aliases: [String]
}

struct GeneralRulesForm {
    var purposeLines: [String]
    var principles: [String]
    var archiveFolders: [String]
    var folderOrder: [String]
    var tableRules: [String]
    var namingFormat: String
    var lowQualityRules: [String]
    var extraHandlers: [String]
    var specialRules: [String]
}

struct SalaryTableSettings {
    var isEnabled: Bool
    var splitSameDatePaymentsIntoSeparateColumns: Bool
    var totalColumnTitle: String
    var totalsRowTitle: String
}

struct FolderCreationSettings {
    var createFoldersOnlyWhenDocumentsExist: Bool
    var doNotCreateEmptyFoldersInAdvance: Bool
    var createManualReviewFolderOnlyWhenNeeded: Bool
    var createSpecialSubfoldersByRoutingRules: Bool
    var protectExistingFilesWithUniqueSuffix: Bool
}

struct RoutingCategorySettings {
    var routeByDocumentTextFirst: Bool
    var routeOfficeBeforeCategoryFinalization: Bool
    var useContractorsAsCategorySignals: Bool
    var unresolvedRouteGoesToManualReview: Bool
}

struct ManualReviewSettings {
    var sendLowConfidenceDocumentsToManualReview: Bool
    var sendMissingOfficeDocumentsToManualReview: Bool
    var preserveReadableNamesInManualReview: Bool
    var createManualReviewReport: Bool
}

struct NamingBehaviorSettings {
    var useExtractedTextForNaming: Bool
    var fallbackToOriginalNameWhenNoText: Bool
    var makeNamesWindowsSafe: Bool
    var keepUniqueSuffixOnConflict: Bool
}

struct CommissionSettings {
    var detectByPaymentText: Bool
    var useOfficeEntityRouting: Bool
    var createOfficeExcel: Bool
}

struct TaxAndInsuranceSettings {
    var detectByPaymentPhrases: Bool
    var useOfficeEntityRouting: Bool
    var createTaxAndInsuranceExcel: Bool
}

struct InternetProviderSettings {
    var prioritizeKnownProviders: Bool
    var allowSpecialProviderSubfolders: Bool
    var createSubfoldersByOfficeContractors: Bool
    var normalizeBrokenProviderText: Bool
}

enum RulesEditing {
    static let standardCategories = ["Зарплата", "Аренда", "Интернет", "Коммунальные", "Услуги", "Прочее", "Комиссии", "Ндфл и Взносы", "УСН"]
    static let contractorCategories = ["Аренда", "Интернет", "Коммунальные", "Услуги", "Прочее", "Комиссии", "Ндфл и Взносы", "УСН"]
    private static let officesMarker = "\n## 11. Офисы"
    private static let specialRulesHeader = "## 13. Общие специальные правила"
    private static let salaryCreateRule = "Для любого офиса с папкой `Зарплата` автоматически создается `Зарплата_<офис>.xlsx`."
    private static let salaryOneRowRule = "Для зарплатной таблицы используется правило: одна строка = один сотрудник."
    private static let salaryDateColumnRule = "Для зарплатной таблицы используется правило: отдельная колонка на каждую дату выплаты."
    private static let salarySplitSameDateRule = "Если у сотрудника несколько выплат в одну дату, создаются отдельные колонки `(2)`, `(3)` и далее."
    private static let salaryOneColumnPerDateRule = "Для каждой фактической даты исполнения зарплатных платежей создается один столбец; суммы выплат сотрудника за эту дату учитываются в одной ячейке."
    private static let salaryTotalColumnPrefix = "Итоговый столбец зарплатной таблицы называется "
    private static let salaryTotalsRowPrefix = "Итоговая строка зарплатной таблицы называется "
    private static let salaryDuplicateReviewRule = "Если у одного сотрудника найдены две выплаты зарплаты с одинаковой суммой, все совпавшие чеки отправляются в ручную проверку до создания таблиц."
    private static let salaryExcludedDuplicateRule = "Подтвержденный повторный зарплатный чек сохраняется в `Требует_ручной_проверки/Исключенные_повторы`, не переносится в офис и не учитывается в таблицах."
    private static let sourceReceiptsArchiveRule = "После успешного создания таблиц и объединенных PDF отдельные чеки зарплаты и комиссий переносятся в `Исходные_чеки/<офис>/<категория>`."
    private static let folderCreateOnDemandRule = "Папки офисов и категорий создаются только при первой реальной раскладке документа."
    private static let folderNoEmptyRule = "Пустые папки заранее не создаются."
    private static let folderManualReviewOnDemandRule = "Папка `Требует_ручной_проверки` создается только когда в нее реально попадает файл или отчет."
    private static let folderSpecialSubfoldersRule = "Специальные подпапки создаются только если сработало специальное правило маршрутизации."
    private static let folderUniqueNameRule = "При конфликте имен создается новый файл с безопасным уникальным суффиксом, а существующий файл не перезаписывается."
    private static let routingTextFirstRule = "Если текст документа читается, маршрутизация опирается на него раньше, чем на имя файла."
    private static let routingOfficeBeforeCategoryRule = "Сначала приложение старается понять офис, а уже потом окончательно фиксирует категорию и путь."
    private static let routingContractorSignalRule = "Контрагент из правил офиса усиливает выбор категории и папки."
    private static let routingManualReviewFallbackRule = "Если после всех проверок путь не собран уверенно, файл уходит в `Требует_ручной_проверки`."
    private static let manualLowConfidenceRule = "Документы с низкой уверенностью распознавания отправляются в `Требует_ручной_проверки`."
    private static let manualMissingOfficeRule = "Если тип документа понятен, но офис не определен, файл отправляется в `Требует_ручной_проверки`."
    private static let manualPreserveReadableNameRule = "В ручной проверке сохраняется читаемое имя из текста, если его удалось собрать."
    private static let manualCreateReportRule = "Для папки `Требует_ручной_проверки` автоматически создается `_report.txt` с причинами ручной обработки."
    private static let namingExtractedTextRule = "Имя файла собирается из извлеченного текста документа, если полезные поля найдены."
    private static let namingOriginalFallbackRule = "Если полезный текст не найден, приложение оставляет безопасный fallback от исходного имени файла."
    private static let namingWindowsSafeRule = "Имена файлов автоматически приводятся к безопасному виду для macOS и Windows."
    private static let namingUniqueSuffixRule = "Если итоговое имя уже занято, приложение добавляет уникальный суффикс вместо перезаписи."
    private static let commissionDetectTextRule = "Банковские комиссии определяются по формулировкам платежа и банковским маркерам в тексте."
    private static let commissionEntityRoutingRule = "Комиссии стараются попасть в офис по юрлицу документа, даже если в имени файла это не видно."
    private static let commissionExcelRule = "Для любого офиса с папкой `Комиссии` автоматически создается `Комиссии_<офис>.xlsx`."
    private static let taxDetectPhraseRule = "Налоги, НДФЛ, ЕНП и страховые взносы определяются по платежным формулировкам документа."
    private static let taxEntityRoutingRule = "Налоги и взносы стараются попасть в офис по юрлицу документа."
    private static let taxExcelRule = "Для любого офиса с папкой `Ндфл и Взносы` автоматически создаются `Распределение_налогов_<офис>.xlsx` и `Распределение_взносов_<офис>.xlsx`."
    private static let internetProviderPriorityRule = "Известные провайдеры и телеком-компании приоритетно относятся к категории `Интернет`."
    private static let internetProviderSubfolderRule = "Для отдельных провайдеров могут создаваться специальные подпапки внутри `Интернет`, если это поддержано маршрутизацией."
    private static let internetOfficeContractorSubfolderRule = "Для контрагентов с включенной настройкой `Создавать папку` приложение создает подпапку внутри категории."
    private static let internetNormalizeBrokenTextRule = "Перед поиском провайдера приложение пытается исправить битый OCR и сломанную кодировку названий."

    static func isValidOfficeNumber(_ office: String) -> Bool {
        let trimmed = office.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.range(of: #"^\d+$"#, options: .regularExpression) != nil
    }

    static func loadOfficeList(from content: String) -> [String] {
        let pattern = #"(?m)^### Офис (\d+)\s*$"#
        let regex = try? NSRegularExpression(pattern: pattern)
        let nsrange = NSRange(content.startIndex..<content.endIndex, in: content)
        return regex?.matches(in: content, range: nsrange).compactMap {
            guard let range = Range($0.range(at: 1), in: content) else { return nil }
            return String(content[range])
        } ?? []
    }

    private static func officeHeadingRange(in content: String, office: String) -> Range<String.Index>? {
        guard isValidOfficeNumber(office) else { return nil }
        let escapedOffice = NSRegularExpression.escapedPattern(for: office.trimmingCharacters(in: .whitespacesAndNewlines))
        let pattern = #"(?m)^### Офис \#(escapedOffice)\s*$"#
        guard let regex = try? NSRegularExpression(pattern: pattern) else { return nil }
        let nsrange = NSRange(content.startIndex..<content.endIndex, in: content)
        guard let match = regex.firstMatch(in: content, range: nsrange),
              let range = Range(match.range, in: content) else {
            return nil
        }
        return range
    }

    static func extractOfficeSection(from content: String, office: String) -> String {
        guard let headingRange = officeHeadingRange(in: content, office: office) else { return "" }
        let start = headingRange.lowerBound
        let headingEnd = headingRange.upperBound
        let tail = content[start...]
        if let nextOffice = content[headingEnd...].range(of: #"(?m)^### Офис \d+\s*$"#, options: .regularExpression)?.lowerBound {
            return String(content[start..<nextOffice]).trimmingCharacters(in: .whitespacesAndNewlines)
        }
        if let nextMain = content[headingEnd...].range(of: #"(?m)^## "#, options: .regularExpression)?.lowerBound {
            return String(content[start..<nextMain]).trimmingCharacters(in: .whitespacesAndNewlines)
        }
        return String(tail).trimmingCharacters(in: .whitespacesAndNewlines)
    }

    static func parseOfficeForm(from content: String, office: String) -> OfficeRuleForm {
        let section = extractOfficeSection(from: content, office: office)
        guard !section.isEmpty else {
            return OfficeRuleForm(
                office: office,
                entity: "",
                allowedCategories: ["Зарплата"],
                employees: [],
                contractorRules: [:]
            )
        }

        let entity = parseBulletSection("Юрлицо", from: section)
            .first?
            .trimmingCharacters(in: CharacterSet(charactersIn: "`"))
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""

        let categories = parseBulletSection("Разрешенные категории по умолчанию", from: section)
            .map { $0.trimmingCharacters(in: CharacterSet(charactersIn: "`")) }
            .filter { !$0.isEmpty }

        let employees = parseBulletSection("Сотрудники", from: section)

        var contractorRules: [String: [ContractorRuleForm]] = [:]
        for line in parseBulletSection("Контрагенты", from: section) {
            let parts = line.split(separator: ":", maxSplits: 1).map(String.init)
            guard parts.count == 2 else { continue }
            let category = parts[0].trimmingCharacters(in: CharacterSet(charactersIn: "` "))
            guard category != "Зарплата" else { continue }
            contractorRules[category, default: []].append(contentsOf: parseContractorRules(from: parts[1], category: category))
        }

        return OfficeRuleForm(
            office: office,
            entity: entity,
            allowedCategories: categories.isEmpty ? ["Зарплата"] : categories,
            employees: employees,
            contractorRules: contractorRules
        )
    }

    static func buildOfficeSection(from form: OfficeRuleForm) -> String {
        let office = form.office.trimmingCharacters(in: .whitespacesAndNewlines)
        let entity = form.entity.trimmingCharacters(in: .whitespacesAndNewlines)
        let categories = form.allowedCategories
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
        let employees = form.employees
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
        let contractorLines = contractorLines(from: form.contractorRules)

        var lines = ["### Офис \(office)", "", "Юрлицо:"]
        lines.append(entity.isEmpty ? "- `ООО ВАША КОМПАНИЯ`" : "- `\(normalizedEntity(entity))`")
        lines.append("")
        lines.append("Разрешенные категории по умолчанию:")
        lines.append(contentsOf: (categories.isEmpty ? ["Зарплата"] : categories).map { "- `\($0)`" })
        lines.append("")
        lines.append("Сотрудники:")
        if employees.isEmpty {
            lines.append("- Новый сотрудник")
        } else {
            lines.append(contentsOf: employees.map { "- \($0)" })
        }
        lines.append("")
        lines.append("Контрагенты:")
        if contractorLines.isEmpty {
            lines.append("- `Интернет`: Провайдер | папка: нет | алиасы: Провайдер")
        } else {
            lines.append(contentsOf: contractorLines)
        }
        return lines.joined(separator: "\n")
    }

    static func extractGeneralSection(from content: String) -> String {
        if let officeStart = content.range(of: officesMarker)?.lowerBound {
            return String(content[..<officeStart]).trimmingCharacters(in: .whitespacesAndNewlines)
        }
        return content.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    static func replaceOfficeSection(in content: String, office: String, newSection: String) -> String {
        guard let headingRange = officeHeadingRange(in: content, office: office) else { return content }
        let start = headingRange.lowerBound
        let headingEnd = headingRange.upperBound
        let trimmedSection = newSection.trimmingCharacters(in: .whitespacesAndNewlines)
        let replacement = trimmedSection + "\n\n"
        if let nextOffice = content[headingEnd...].range(of: #"(?m)^### Офис \d+\s*$"#, options: .regularExpression)?.lowerBound {
            return content.replacingCharacters(in: start..<nextOffice, with: replacement)
        }
        if let nextMain = content[headingEnd...].range(of: #"(?m)^## "#, options: .regularExpression)?.lowerBound {
            return content.replacingCharacters(in: start..<nextMain, with: replacement)
        }
        return String(content[..<start]) + replacement
    }

    static func removeOffice(in content: String, office: String) -> String {
        guard let headingRange = officeHeadingRange(in: content, office: office) else { return content }
        let start = headingRange.lowerBound
        let headingEnd = headingRange.upperBound
        let end: String.Index
        if let nextOffice = content[headingEnd...].range(of: #"(?m)^### Офис \d+\s*$"#, options: .regularExpression)?.lowerBound {
            end = nextOffice
        } else if let nextMain = content[headingEnd...].range(of: #"(?m)^## "#, options: .regularExpression)?.lowerBound {
            end = nextMain
        } else {
            end = content.endIndex
        }
        return content.replacingCharacters(in: start..<end, with: "").trimmingCharacters(in: .whitespacesAndNewlines) + "\n"
    }

    static func replaceGeneralSection(in content: String, newSection: String) -> String {
        let trimmed = newSection.trimmingCharacters(in: .whitespacesAndNewlines)
        if let officeStart = content.range(of: officesMarker)?.lowerBound {
            return trimmed + "\n\n" + String(content[officeStart...]).trimmingCharacters(in: .whitespacesAndNewlines) + "\n"
        }
        return trimmed + "\n"
    }

    static func addOffice(in content: String, office: String) -> String {
        let trimmedOffice = office.trimmingCharacters(in: .whitespacesAndNewlines)
        guard isValidOfficeNumber(trimmedOffice) else { return content }
        if officeHeadingRange(in: content, office: trimmedOffice) != nil {
            return content
        }
        let template = buildOfficeSection(from: OfficeRuleForm(
            office: trimmedOffice,
            entity: "",
            allowedCategories: ["Зарплата"],
            employees: [],
            contractorRules: [:]
        ))
        if let range = content.range(of: specialRulesHeader) {
            return content.replacingCharacters(in: range.lowerBound..<range.lowerBound, with: template + "\n\n")
        }
        return content + "\n\n" + template
    }

    static func parseGeneralRules(from content: String) -> GeneralRulesForm {
        let purposeSection = extractSection(content, header: "## 1. Назначение файла") ?? ""
        let namingSection = extractSection(content, header: "## 6. Именование файлов") ?? ""

        let namingLines = normalizedLines(from: namingSection)
        let namingFormat = namingLines.last(where: { $0.hasPrefix("`") && $0.hasSuffix("`") })?
            .trimmingCharacters(in: CharacterSet(charactersIn: "`")) ?? "<основной_идентификатор>_<дата>_<номер>_<сумма>"

        return GeneralRulesForm(
            purposeLines: normalizedParagraphLines(from: purposeSection, droppingHeader: "## 1. Назначение файла"),
            principles: parseSectionList("## 2. Общие принципы", from: content),
            archiveFolders: parseSectionList("## 3. Базовая структура архива", from: content),
            folderOrder: parseSectionList("## 4. Порядок определения папки", from: content),
            tableRules: parseSectionList("## 5. Таблицы", from: content),
            namingFormat: namingFormat,
            lowQualityRules: parseSectionList("## 7. Обработка плохо читаемых файлов", from: content),
            extraHandlers: parseSectionList("## 8. Дополнительные обработчики документов", from: content),
            specialRules: parseSectionList(specialRulesHeader, from: content)
        )
    }

    static func replaceGeneralRules(in content: String, form: GeneralRulesForm) -> String {
        let builtGeneral = buildGeneralSection(from: form)
        let generalWithoutSpecialRules: String
        if let specialStart = builtGeneral.range(of: "\n\(specialRulesHeader)")?.lowerBound {
            generalWithoutSpecialRules = String(builtGeneral[..<specialStart])
                .trimmingCharacters(in: .whitespacesAndNewlines)
        } else {
            generalWithoutSpecialRules = builtGeneral.trimmingCharacters(in: .whitespacesAndNewlines)
        }

        var sections = [generalWithoutSpecialRules]
        if let officeStart = content.range(of: "## 11. Офисы")?.lowerBound {
            let officeTail = content[officeStart...]
            let officeBlock: String
            if let specialStart = officeTail.range(of: specialRulesHeader)?.lowerBound {
                officeBlock = String(officeTail[..<specialStart])
                    .trimmingCharacters(in: .whitespacesAndNewlines)
            } else {
                officeBlock = String(officeTail).trimmingCharacters(in: .whitespacesAndNewlines)
            }
            if !officeBlock.isEmpty {
                sections.append(officeBlock)
            }
        }
        sections.append(buildGeneralSpecialRulesSection(rules: form.specialRules))
        return sections.joined(separator: "\n\n") + "\n"
    }

    static func defaultSalaryTableSettings() -> SalaryTableSettings {
        SalaryTableSettings(
            isEnabled: true,
            splitSameDatePaymentsIntoSeparateColumns: false,
            totalColumnTitle: "Общий итог",
            totalsRowTitle: "ИТОГО"
        )
    }

    static func defaultFolderCreationSettings() -> FolderCreationSettings {
        FolderCreationSettings(
            createFoldersOnlyWhenDocumentsExist: true,
            doNotCreateEmptyFoldersInAdvance: true,
            createManualReviewFolderOnlyWhenNeeded: true,
            createSpecialSubfoldersByRoutingRules: true,
            protectExistingFilesWithUniqueSuffix: true
        )
    }

    static func defaultRoutingCategorySettings() -> RoutingCategorySettings {
        RoutingCategorySettings(
            routeByDocumentTextFirst: true,
            routeOfficeBeforeCategoryFinalization: true,
            useContractorsAsCategorySignals: true,
            unresolvedRouteGoesToManualReview: true
        )
    }

    static func defaultManualReviewSettings() -> ManualReviewSettings {
        ManualReviewSettings(
            sendLowConfidenceDocumentsToManualReview: true,
            sendMissingOfficeDocumentsToManualReview: true,
            preserveReadableNamesInManualReview: true,
            createManualReviewReport: true
        )
    }

    static func defaultNamingBehaviorSettings() -> NamingBehaviorSettings {
        NamingBehaviorSettings(
            useExtractedTextForNaming: true,
            fallbackToOriginalNameWhenNoText: true,
            makeNamesWindowsSafe: true,
            keepUniqueSuffixOnConflict: true
        )
    }

    static func defaultCommissionSettings() -> CommissionSettings {
        CommissionSettings(
            detectByPaymentText: true,
            useOfficeEntityRouting: true,
            createOfficeExcel: true
        )
    }

    static func defaultTaxAndInsuranceSettings() -> TaxAndInsuranceSettings {
        TaxAndInsuranceSettings(
            detectByPaymentPhrases: true,
            useOfficeEntityRouting: true,
            createTaxAndInsuranceExcel: true
        )
    }

    static func defaultInternetProviderSettings() -> InternetProviderSettings {
        InternetProviderSettings(
            prioritizeKnownProviders: true,
            allowSpecialProviderSubfolders: true,
            createSubfoldersByOfficeContractors: true,
            normalizeBrokenProviderText: true
        )
    }

    static func enforcingRequiredOperationalRules(in content: String) -> String {
        let form = parseGeneralRules(from: content)
        let currentSalary = parseSalaryTableSettings(from: form.tableRules)
        let currentManualReview = parseManualReviewSettings(from: form.specialRules)
        let salaryDefaults = defaultSalaryTableSettings()
        let totalColumnTitle = currentSalary.totalColumnTitle.trimmingCharacters(in: .whitespacesAndNewlines)
        let totalsRowTitle = currentSalary.totalsRowTitle.trimmingCharacters(in: .whitespacesAndNewlines)

        let tableRules = mergeTableRules(
            nonSalaryRules: nonSalaryTableRules(from: form.tableRules),
            salarySettings: SalaryTableSettings(
                isEnabled: true,
                splitSameDatePaymentsIntoSeparateColumns: false,
                totalColumnTitle: totalColumnTitle.isEmpty ? salaryDefaults.totalColumnTitle : totalColumnTitle,
                totalsRowTitle: totalsRowTitle.isEmpty ? salaryDefaults.totalsRowTitle : totalsRowTitle
            ),
            commissionSettings: defaultCommissionSettings(),
            taxSettings: defaultTaxAndInsuranceSettings()
        )
        var requiredNonFolderRules = nonFolderCreationSpecialRules(from: form.specialRules)
        requiredNonFolderRules.removeAll { rule in
            rule == salarySplitSameDateRule
                || rule == salaryOneColumnPerDateRule
                || rule.hasPrefix(salaryTotalColumnPrefix)
                || rule.hasPrefix(salaryTotalsRowPrefix)
        }
        if !requiredNonFolderRules.contains(salaryDuplicateReviewRule) {
            requiredNonFolderRules.append(salaryDuplicateReviewRule)
        }
        if !requiredNonFolderRules.contains(salaryExcludedDuplicateRule) {
            requiredNonFolderRules.append(salaryExcludedDuplicateRule)
        }
        if !requiredNonFolderRules.contains(sourceReceiptsArchiveRule) {
            requiredNonFolderRules.append(sourceReceiptsArchiveRule)
        }
        let specialRules = mergeSpecialRules(
            nonFolderRules: requiredNonFolderRules,
            folderSettings: defaultFolderCreationSettings(),
            routingSettings: defaultRoutingCategorySettings(),
            manualReviewSettings: ManualReviewSettings(
                sendLowConfidenceDocumentsToManualReview: true,
                sendMissingOfficeDocumentsToManualReview: true,
                preserveReadableNamesInManualReview: currentManualReview.preserveReadableNamesInManualReview,
                createManualReviewReport: currentManualReview.createManualReviewReport
            ),
            namingSettings: defaultNamingBehaviorSettings(),
            commissionSettings: defaultCommissionSettings(),
            taxSettings: defaultTaxAndInsuranceSettings(),
            internetSettings: defaultInternetProviderSettings()
        )
        return replaceGeneralRules(
            in: content,
            form: GeneralRulesForm(
                purposeLines: form.purposeLines,
                principles: form.principles,
                archiveFolders: form.archiveFolders,
                folderOrder: form.folderOrder,
                tableRules: tableRules,
                namingFormat: form.namingFormat,
                lowQualityRules: form.lowQualityRules,
                extraHandlers: form.extraHandlers,
                specialRules: specialRules
            )
        )
    }

    static func parseSalaryTableSettings(from tableRules: [String]) -> SalaryTableSettings {
        var settings = defaultSalaryTableSettings()
        settings.isEnabled = tableRules.contains(salaryCreateRule)
        settings.splitSameDatePaymentsIntoSeparateColumns = tableRules.contains(salarySplitSameDateRule)
            && !tableRules.contains(salaryOneColumnPerDateRule)
        if let totalColumnRule = tableRules.first(where: { $0.hasPrefix(salaryTotalColumnPrefix) }) {
            settings.totalColumnTitle = totalColumnRule
                .replacingOccurrences(of: salaryTotalColumnPrefix, with: "")
                .trimmingCharacters(in: CharacterSet(charactersIn: " `.“”\""))
        }
        if let totalsRowRule = tableRules.first(where: { $0.hasPrefix(salaryTotalsRowPrefix) }) {
            settings.totalsRowTitle = totalsRowRule
                .replacingOccurrences(of: salaryTotalsRowPrefix, with: "")
                .trimmingCharacters(in: CharacterSet(charactersIn: " `.“”\""))
        }
        return settings
    }

    static func nonSalaryTableRules(from tableRules: [String]) -> [String] {
        tableRules.filter { rule in
            rule != salaryCreateRule
                && rule != salaryOneRowRule
                && rule != salaryDateColumnRule
                && rule != salarySplitSameDateRule
                && rule != salaryOneColumnPerDateRule
                && rule != commissionExcelRule
                && rule != taxExcelRule
                && !rule.hasPrefix(salaryTotalColumnPrefix)
                && !rule.hasPrefix(salaryTotalsRowPrefix)
        }
    }

    static func mergeTableRules(
        nonSalaryRules: [String],
        salarySettings: SalaryTableSettings,
        commissionSettings: CommissionSettings = defaultCommissionSettings(),
        taxSettings: TaxAndInsuranceSettings = defaultTaxAndInsuranceSettings()
    ) -> [String] {
        var rules: [String] = []
        if salarySettings.isEnabled {
            rules.append(salaryCreateRule)
        }
        rules.append(salaryOneRowRule)
        rules.append(salaryDateColumnRule)
        if salarySettings.splitSameDatePaymentsIntoSeparateColumns {
            rules.append(salarySplitSameDateRule)
        } else {
            rules.append(salaryOneColumnPerDateRule)
        }
        let totalColumnTitle = salarySettings.totalColumnTitle.trimmingCharacters(in: .whitespacesAndNewlines)
        if !totalColumnTitle.isEmpty {
            rules.append("\(salaryTotalColumnPrefix)`\(totalColumnTitle)`.")
        }
        let totalsRowTitle = salarySettings.totalsRowTitle.trimmingCharacters(in: .whitespacesAndNewlines)
        if !totalsRowTitle.isEmpty {
            rules.append("\(salaryTotalsRowPrefix)`\(totalsRowTitle)`.")
        }
        if commissionSettings.createOfficeExcel {
            rules.append(commissionExcelRule)
        }
        if taxSettings.createTaxAndInsuranceExcel {
            rules.append(taxExcelRule)
        }
        rules.append(contentsOf: normalizedList(nonSalaryRules, fallback: []))
        return rules
    }

    static func parseFolderCreationSettings(from specialRules: [String]) -> FolderCreationSettings {
        var settings = defaultFolderCreationSettings()
        settings.createFoldersOnlyWhenDocumentsExist = specialRules.contains(folderCreateOnDemandRule)
        settings.doNotCreateEmptyFoldersInAdvance = specialRules.contains(folderNoEmptyRule)
        settings.createManualReviewFolderOnlyWhenNeeded = specialRules.contains(folderManualReviewOnDemandRule)
        settings.createSpecialSubfoldersByRoutingRules = specialRules.contains(folderSpecialSubfoldersRule)
        settings.protectExistingFilesWithUniqueSuffix = specialRules.contains(folderUniqueNameRule)
        return settings
    }

    static func parseRoutingCategorySettings(from specialRules: [String]) -> RoutingCategorySettings {
        var settings = defaultRoutingCategorySettings()
        settings.routeByDocumentTextFirst = specialRules.contains(routingTextFirstRule)
        settings.routeOfficeBeforeCategoryFinalization = specialRules.contains(routingOfficeBeforeCategoryRule)
        settings.useContractorsAsCategorySignals = specialRules.contains(routingContractorSignalRule)
        settings.unresolvedRouteGoesToManualReview = specialRules.contains(routingManualReviewFallbackRule)
        return settings
    }

    static func parseManualReviewSettings(from specialRules: [String]) -> ManualReviewSettings {
        var settings = defaultManualReviewSettings()
        settings.sendLowConfidenceDocumentsToManualReview = specialRules.contains(manualLowConfidenceRule)
        settings.sendMissingOfficeDocumentsToManualReview = specialRules.contains(manualMissingOfficeRule)
        settings.preserveReadableNamesInManualReview = specialRules.contains(manualPreserveReadableNameRule)
        settings.createManualReviewReport = specialRules.contains(manualCreateReportRule)
        return settings
    }

    static func parseNamingBehaviorSettings(from specialRules: [String]) -> NamingBehaviorSettings {
        var settings = defaultNamingBehaviorSettings()
        settings.useExtractedTextForNaming = specialRules.contains(namingExtractedTextRule)
        settings.fallbackToOriginalNameWhenNoText = specialRules.contains(namingOriginalFallbackRule)
        settings.makeNamesWindowsSafe = specialRules.contains(namingWindowsSafeRule)
        settings.keepUniqueSuffixOnConflict = specialRules.contains(namingUniqueSuffixRule)
        return settings
    }

    static func parseCommissionSettings(from specialRules: [String], tableRules: [String]) -> CommissionSettings {
        var settings = defaultCommissionSettings()
        settings.detectByPaymentText = specialRules.contains(commissionDetectTextRule)
        settings.useOfficeEntityRouting = specialRules.contains(commissionEntityRoutingRule)
        settings.createOfficeExcel = tableRules.contains(commissionExcelRule)
        return settings
    }

    static func parseTaxAndInsuranceSettings(from specialRules: [String], tableRules: [String]) -> TaxAndInsuranceSettings {
        var settings = defaultTaxAndInsuranceSettings()
        settings.detectByPaymentPhrases = specialRules.contains(taxDetectPhraseRule)
        settings.useOfficeEntityRouting = specialRules.contains(taxEntityRoutingRule)
        settings.createTaxAndInsuranceExcel = tableRules.contains(taxExcelRule)
        return settings
    }

    static func parseInternetProviderSettings(from specialRules: [String]) -> InternetProviderSettings {
        var settings = defaultInternetProviderSettings()
        settings.prioritizeKnownProviders = specialRules.contains(internetProviderPriorityRule)
        settings.allowSpecialProviderSubfolders = specialRules.contains(internetProviderSubfolderRule)
        settings.createSubfoldersByOfficeContractors = specialRules.contains(internetOfficeContractorSubfolderRule)
        settings.normalizeBrokenProviderText = specialRules.contains(internetNormalizeBrokenTextRule)
        return settings
    }

    static func nonFolderCreationSpecialRules(from specialRules: [String]) -> [String] {
        specialRules.filter { rule in
            rule != folderCreateOnDemandRule
                && rule != folderNoEmptyRule
                && rule != folderManualReviewOnDemandRule
                && rule != folderSpecialSubfoldersRule
                && rule != folderUniqueNameRule
                && rule != routingTextFirstRule
                && rule != routingOfficeBeforeCategoryRule
                && rule != routingContractorSignalRule
                && rule != routingManualReviewFallbackRule
                && rule != manualLowConfidenceRule
                && rule != manualMissingOfficeRule
                && rule != manualPreserveReadableNameRule
                && rule != manualCreateReportRule
                && rule != namingExtractedTextRule
                && rule != namingOriginalFallbackRule
                && rule != namingWindowsSafeRule
                && rule != namingUniqueSuffixRule
                && rule != commissionDetectTextRule
                && rule != commissionEntityRoutingRule
                && rule != taxDetectPhraseRule
                && rule != taxEntityRoutingRule
                && rule != internetProviderPriorityRule
                && rule != internetProviderSubfolderRule
                && rule != internetOfficeContractorSubfolderRule
                && rule != internetNormalizeBrokenTextRule
        }
    }

    static func mergeSpecialRules(
        nonFolderRules: [String],
        folderSettings: FolderCreationSettings,
        routingSettings: RoutingCategorySettings,
        manualReviewSettings: ManualReviewSettings,
        namingSettings: NamingBehaviorSettings,
        commissionSettings: CommissionSettings,
        taxSettings: TaxAndInsuranceSettings,
        internetSettings: InternetProviderSettings
    ) -> [String] {
        var rules: [String] = []
        if folderSettings.createFoldersOnlyWhenDocumentsExist {
            rules.append(folderCreateOnDemandRule)
        }
        if folderSettings.doNotCreateEmptyFoldersInAdvance {
            rules.append(folderNoEmptyRule)
        }
        if folderSettings.createManualReviewFolderOnlyWhenNeeded {
            rules.append(folderManualReviewOnDemandRule)
        }
        if folderSettings.createSpecialSubfoldersByRoutingRules {
            rules.append(folderSpecialSubfoldersRule)
        }
        if folderSettings.protectExistingFilesWithUniqueSuffix {
            rules.append(folderUniqueNameRule)
        }
        if routingSettings.routeByDocumentTextFirst {
            rules.append(routingTextFirstRule)
        }
        if routingSettings.routeOfficeBeforeCategoryFinalization {
            rules.append(routingOfficeBeforeCategoryRule)
        }
        if routingSettings.useContractorsAsCategorySignals {
            rules.append(routingContractorSignalRule)
        }
        if routingSettings.unresolvedRouteGoesToManualReview {
            rules.append(routingManualReviewFallbackRule)
        }
        if manualReviewSettings.sendLowConfidenceDocumentsToManualReview {
            rules.append(manualLowConfidenceRule)
        }
        if manualReviewSettings.sendMissingOfficeDocumentsToManualReview {
            rules.append(manualMissingOfficeRule)
        }
        if manualReviewSettings.preserveReadableNamesInManualReview {
            rules.append(manualPreserveReadableNameRule)
        }
        if manualReviewSettings.createManualReviewReport {
            rules.append(manualCreateReportRule)
        }
        if namingSettings.useExtractedTextForNaming {
            rules.append(namingExtractedTextRule)
        }
        if namingSettings.fallbackToOriginalNameWhenNoText {
            rules.append(namingOriginalFallbackRule)
        }
        if namingSettings.makeNamesWindowsSafe {
            rules.append(namingWindowsSafeRule)
        }
        if namingSettings.keepUniqueSuffixOnConflict {
            rules.append(namingUniqueSuffixRule)
        }
        if commissionSettings.detectByPaymentText {
            rules.append(commissionDetectTextRule)
        }
        if commissionSettings.useOfficeEntityRouting {
            rules.append(commissionEntityRoutingRule)
        }
        if taxSettings.detectByPaymentPhrases {
            rules.append(taxDetectPhraseRule)
        }
        if taxSettings.useOfficeEntityRouting {
            rules.append(taxEntityRoutingRule)
        }
        if internetSettings.prioritizeKnownProviders {
            rules.append(internetProviderPriorityRule)
        }
        if internetSettings.allowSpecialProviderSubfolders {
            rules.append(internetProviderSubfolderRule)
        }
        if internetSettings.createSubfoldersByOfficeContractors {
            rules.append(internetOfficeContractorSubfolderRule)
        }
        if internetSettings.normalizeBrokenProviderText {
            rules.append(internetNormalizeBrokenTextRule)
        }
        rules.append(contentsOf: normalizedList(nonFolderRules, fallback: [
            "Эти правила являются рабочей базой офисов приложения.",
            "Изменения можно вносить через интерфейс приложения.",
        ]))
        return rules
    }

    static func buildGeneralSection(from form: GeneralRulesForm) -> String {
        let purposeLines = normalizedList(form.purposeLines, fallback: [
            "Этот файл управляет сортировкой через интерфейс приложения.",
            "Он содержит рабочие офисы, юрлица, сотрудников, контрагентов и категории для автоматической раскладки документов.",
        ])
        let principles = normalizedList(form.principles, fallback: [
            "Сортировка должна опираться на содержимое документа.",
            "Если документ не удается уверенно распознать, он отправляется в папку `Требует_ручной_проверки`.",
            "Имя файла используется только как слабый fallback.",
        ])
        let archiveFolders = normalizedList(form.archiveFolders, fallback: contractorCategories + ["Зарплата"])
        let folderOrder = normalizedList(form.folderOrder, fallback: [
            "Определить тип документа по содержимому.",
            "Определить юрлицо по содержимому.",
            "Определить офис по сотруднику, юрлицу или контрагенту.",
            "Определить категорию документа.",
        ])
        let tableRules = normalizedList(
            form.tableRules,
            fallback: mergeTableRules(
                nonSalaryRules: [],
                salarySettings: defaultSalaryTableSettings(),
                commissionSettings: defaultCommissionSettings(),
                taxSettings: defaultTaxAndInsuranceSettings()
            )
        )
        let namingFormat = form.namingFormat.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            ? "<основной_идентификатор>_<дата>_<номер>_<сумма>"
            : form.namingFormat.trimmingCharacters(in: .whitespacesAndNewlines)
        let lowQualityRules = normalizedList(form.lowQualityRules, fallback: [
            "Если документ не удается распознать уверенно, он отправляется в `Требует_ручной_проверки`.",
        ])
        let extraHandlers = normalizedList(form.extraHandlers, fallback: [
            "текстовый слой PDF",
            "системные метаданные",
            "OCR",
            "QuickLook OCR",
            "fallback по содержимому файла",
        ])
        let specialRules = normalizedList(
            form.specialRules,
            fallback: mergeSpecialRules(
                nonFolderRules: [],
                folderSettings: defaultFolderCreationSettings(),
                routingSettings: defaultRoutingCategorySettings(),
                manualReviewSettings: defaultManualReviewSettings(),
                namingSettings: defaultNamingBehaviorSettings(),
                commissionSettings: defaultCommissionSettings(),
                taxSettings: defaultTaxAndInsuranceSettings(),
                internetSettings: defaultInternetProviderSettings()
            )
        )

        return [
            "# Регламент сортировки документов",
            "",
            "## 1. Назначение файла",
            "",
            purposeLines.joined(separator: "\n"),
            "",
            "## 2. Общие принципы",
            "",
            principles.map { "- \($0)" }.joined(separator: "\n"),
            "",
            "## 3. Базовая структура архива",
            "",
            "Внутри офисов могут создаваться папки:",
            "",
            archiveFolders.map { "- `\($0)`" }.joined(separator: "\n"),
            "",
            "## 4. Порядок определения папки",
            "",
            folderOrder.enumerated().map { "\($0.offset + 1). \($0.element)" }.joined(separator: "\n"),
            "",
            "## 5. Таблицы",
            "",
            tableRules.map { "- \($0)" }.joined(separator: "\n"),
            "",
            "## 6. Именование файлов",
            "",
            "Используется формат:",
            "",
            "`\(namingFormat)`",
            "",
            "## 7. Обработка плохо читаемых файлов",
            "",
            lowQualityRules.map { "- \($0)" }.joined(separator: "\n"),
            "",
            "## 8. Дополнительные обработчики документов",
            "",
            extraHandlers.map { "- \($0)" }.joined(separator: "\n"),
            "",
            buildGeneralSpecialRulesSection(rules: specialRules),
        ].joined(separator: "\n")
    }

    static func normalizeOfficeForm(_ form: OfficeRuleForm, allowedCategories: [String]) -> OfficeRuleForm {
        let normalizedAllowed = allowedCategories
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
        let allowedSet = Set(normalizedAllowed)

        let filteredCategories = form.allowedCategories.filter { allowedSet.contains($0) }
        let safeCategories = filteredCategories.isEmpty ? Array(normalizedAllowed.prefix(1)) : filteredCategories
        let filteredContractors = form.contractorRules.filter { key, _ in
            allowedSet.contains(key) && key != "Зарплата"
        }

        return OfficeRuleForm(
            office: form.office,
            entity: form.entity,
            allowedCategories: safeCategories,
            employees: form.employees,
            contractorRules: filteredContractors.mapValues(normalizeContractorRules)
        )
    }

    static func replaceGeneralSpecialRules(in content: String, rules: [String]) -> String {
        var form = parseGeneralRules(from: content)
        form.specialRules = rules
        return replaceGeneralRules(in: content, form: form)
    }

    static func buildGeneralSpecialRulesSection(rules: [String]) -> String {
        var lines = [specialRulesHeader, ""]
        if rules.isEmpty {
            lines.append("- Новое специальное правило")
        } else {
            lines.append(contentsOf: rules.map { "- \($0)" })
        }
        return lines.joined(separator: "\n")
    }

    private static func extractSection(_ content: String, header: String) -> String? {
        guard let range = extractSectionRange(content, header: header) else { return nil }
        return String(content[range]).trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private static func extractSectionRange(_ content: String, header: String) -> Range<String.Index>? {
        guard let start = content.range(of: header)?.lowerBound else { return nil }
        let tail = content[start...]
        if let nextMain = tail.dropFirst(header.count).range(of: "\n## ")?.lowerBound {
            return start..<nextMain
        }
        return start..<content.endIndex
    }

    private static func parseBulletSection(_ header: String, from section: String) -> [String] {
        var items: [String] = []
        var currentHeader: String?
        for rawLine in section.split(separator: "\n", omittingEmptySubsequences: false) {
            let line = rawLine.trimmingCharacters(in: .whitespacesAndNewlines)
            if line.isEmpty {
                continue
            }
            if line.hasSuffix(":") && !line.hasPrefix("-") {
                currentHeader = String(line.dropLast())
                continue
            }
            guard currentHeader == header, line.hasPrefix("- ") else { continue }
            items.append(String(line.dropFirst(2)).trimmingCharacters(in: .whitespacesAndNewlines))
        }
        return items
    }

    private static func parseContractorRules(from payload: String, category: String) -> [ContractorRuleForm] {
        let parts = payload
            .split(separator: "|", omittingEmptySubsequences: true)
            .map(String.init)
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
        if parts.count > 1 {
            let name = parts[0].trimmingCharacters(in: CharacterSet(charactersIn: "` "))
            var createFolder = false
            var aliases: [String] = []
            for part in parts.dropFirst() {
                let lowered = part.lowercased()
                if lowered.hasPrefix("папка:") {
                    let value = lowered.replacingOccurrences(of: "папка:", with: "").trimmingCharacters(in: .whitespacesAndNewlines)
                    createFolder = ["да", "true", "1", "yes"].contains(value)
                } else if lowered.hasPrefix("алиасы:") {
                    let rawAliases = part.split(separator: ":", maxSplits: 1).dropFirst().first.map(String.init) ?? ""
                    aliases = splitAliases(rawAliases)
                }
            }
            return [ContractorRuleForm(name: name, createFolder: createFolder, aliases: aliases.isEmpty ? [name] : aliases)]
        }

        let values = splitAliases(payload)
        guard category == "Интернет" else {
            return values.map { ContractorRuleForm(name: $0, createFolder: false, aliases: [$0]) }
        }
        var grouped: [String: ContractorRuleForm] = [:]
        for value in values {
            let folderName = providerFolderName(for: value)
            var rule = grouped[folderName] ?? ContractorRuleForm(name: folderName, createFolder: false, aliases: [])
            if !rule.aliases.contains(where: { $0.caseInsensitiveCompare(value) == .orderedSame }) {
                rule.aliases.append(value)
            }
            grouped[folderName] = rule
        }
        return grouped.values.sorted { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending }
    }

    private static func normalizedEntity(_ value: String) -> String {
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.range(of: #"^(ООО|ИП|АО|ПАО)\s+"#, options: [.regularExpression, .caseInsensitive]) != nil {
            return trimmed
        }
        return "ООО \(trimmed)"
    }

    private static func splitAliases(_ value: String) -> [String] {
        value
            .split(separator: ",")
            .map(String.init)
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
    }

    private static func normalizeContractorRules(_ rules: [ContractorRuleForm]) -> [ContractorRuleForm] {
        rules.compactMap { rule in
            let name = rule.name.trimmingCharacters(in: .whitespacesAndNewlines)
            let aliases = rule.aliases
                .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
                .filter { !$0.isEmpty }
            if name.isEmpty && aliases.isEmpty {
                return nil
            }
            return ContractorRuleForm(
                id: rule.id,
                name: name.isEmpty ? (aliases.first ?? "") : name,
                createFolder: rule.createFolder,
                aliases: aliases.isEmpty ? [name] : aliases
            )
        }
    }

    private static func providerFolderName(for value: String) -> String {
        let normalized = value.lowercased()
        if normalized.contains("билайн") || normalized.contains("вымпелком") || normalized.contains("beeline") {
            return "Билайн"
        }
        if normalized.contains("вип-телеком") || normalized.contains("vip telecom") || normalized.contains("vip-telecom") {
            return "Вип-Телеком-Сервис"
        }
        if normalized.contains("искрателеком") || normalized.contains("искра") {
            return "Искрателеком"
        }
        if normalized.contains("комитерн") || normalized.contains("комитен") {
            return "Комитерн Корп"
        }
        if normalized.contains("таттелеком") {
            return "Таттелеком"
        }
        if normalized.contains("вест-колл") || normalized.contains("вест колл") || normalized.contains("westcall") {
            return "Вест-Колл"
        }
        return value.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private static func contractorLines(from inputs: [String: [ContractorRuleForm]]) -> [String] {
        let filteredInputs = inputs.filter { $0.key != "Зарплата" }
        let extraCategories = filteredInputs.keys.filter { !contractorCategories.contains($0) }.sorted()
        let orderedCategories = contractorCategories + extraCategories
        var lines: [String] = []
        var seen: Set<String> = []
        for category in orderedCategories {
            guard !seen.contains(category) else { continue }
            seen.insert(category)
            let values = normalizeContractorRules(filteredInputs[category, default: []])
            guard !values.isEmpty else { continue }
            for rule in values {
                let aliases = rule.aliases.joined(separator: ", ")
                let folderFlag = rule.createFolder ? "да" : "нет"
                lines.append("- `\(category)`: \(rule.name) | папка: \(folderFlag) | алиасы: \(aliases)")
            }
        }
        return lines
    }

    private static func parseSectionList(_ header: String, from content: String) -> [String] {
        guard let section = extractSection(content, header: header) else { return [] }
        return normalizedLines(from: section).compactMap { line in
            if line.hasPrefix("- ") {
                return String(line.dropFirst(2))
                    .trimmingCharacters(in: .whitespacesAndNewlines)
                    .trimmingCharacters(in: CharacterSet(charactersIn: "`"))
            }
            if let match = line.range(of: #"^\d+\.\s+"#, options: .regularExpression) {
                return String(line[match.upperBound...]).trimmingCharacters(in: .whitespacesAndNewlines)
            }
            return nil
        }
    }

    private static func normalizedParagraphLines(from section: String, droppingHeader header: String) -> [String] {
        normalizedLines(from: section)
            .filter { $0 != header }
    }

    private static func normalizedLines(from section: String) -> [String] {
        section
            .split(separator: "\n", omittingEmptySubsequences: false)
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
    }

    private static func normalizedList(_ values: [String], fallback: [String]) -> [String] {
        let normalized = values
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
        return normalized.isEmpty ? fallback : normalized
    }
}
