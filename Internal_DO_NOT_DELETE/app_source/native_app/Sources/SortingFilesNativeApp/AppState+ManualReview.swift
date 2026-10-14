import AppKit
import Foundation

private struct ManualReviewDetails: Decodable {
    let office: String
    let category: String
    let entity: String
    let reason: String
    let salary_duplicate: Bool?
    var review_fields: [String: String]? = nil

    var isSalaryDuplicate: Bool {
        salary_duplicate ?? reason.localizedCaseInsensitiveContains("Возможный повтор зарплаты")
    }
}

extension AppState {
    var manualReviewRootURL: URL? {
        let trimmed = resultArchivePath.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return nil }
        return URL(fileURLWithPath: trimmed).appendingPathComponent("Требует_ручной_проверки")
    }

    var selectedManualReviewItem: ManualReviewItem? {
        manualReviewItems.first(where: { $0.id == selectedManualReviewItemID })
    }

    var selectedManualReviewReason: String {
        guard let item = selectedManualReviewItem else { return "" }
        return manualReviewReportDetails()[item.name]?.reason ?? "Ожидает ручного решения."
    }

    var selectedManualReviewIsSalaryDuplicate: Bool {
        guard let item = selectedManualReviewItem else { return false }
        return manualReviewReportDetails()[item.name]?.isSalaryDuplicate ?? false
    }

    var manualPaymentFieldsHaveEdits: Bool {
        guard selectedManualReviewItem != nil else { return false }
        return manualReviewPaymentDate != manualReviewOriginalPaymentDate || manualReviewPaymentAmount != manualReviewOriginalPaymentAmount
    }

    var manualReviewAvailableEntities: [String] {
        if !manualReviewOffice.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            let entity = officeEntity(for: manualReviewOffice).trimmingCharacters(in: .whitespacesAndNewlines)
            return entity.isEmpty ? [] : [entity]
        }
        let content = (try? String(contentsOf: AppPaths.rulesFile, encoding: .utf8)) ?? ""
        let offices = RulesEditing.loadOfficeList(from: content)
        let entities = offices.compactMap { office in
            let form = RulesEditing.parseOfficeForm(from: content, office: office)
            let trimmed = form.entity.trimmingCharacters(in: .whitespacesAndNewlines)
            return trimmed.isEmpty ? nil : trimmed
        }
        return Array(Set(entities)).sorted()
    }

    var manualReviewAvailableCategories: [String] {
        let office = manualReviewOffice.trimmingCharacters(in: .whitespacesAndNewlines)
        if !office.isEmpty {
            let categories = officeCategories(for: office)
            if !categories.isEmpty {
                return categories
            }
        }
        let normalized = generalArchiveFolders
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
        return normalized.isEmpty ? RulesEditing.standardCategories : normalized
    }

    func refreshManualReviewItems() {
        refreshCompletionReport()
        guard let root = manualReviewRootURL else {
            manualReviewItems = []
            selectedManualReviewItemID = ""
            return
        }
        let fileManager = FileManager.default
        guard fileManager.fileExists(atPath: root.path) else {
            manualReviewItems = []
            selectedManualReviewItemID = ""
            return
        }
        let urls = (try? fileManager.contentsOfDirectory(
            at: root,
            includingPropertiesForKeys: [.isRegularFileKey],
            options: [.skipsHiddenFiles]
        )) ?? []
        let items = urls
            .filter { $0.lastPathComponent != "_report.txt" }
            .filter { (try? $0.resourceValues(forKeys: [.isRegularFileKey]).isRegularFile) ?? false }
            .sorted { $0.lastPathComponent.localizedCaseInsensitiveCompare($1.lastPathComponent) == .orderedAscending }
            .map(ManualReviewItem.init(url:))
        manualReviewItems = items
        manualReviewCount = items.count
        if let selected = selectedManualReviewItem, items.contains(selected) {
            return
        }
        selectedManualReviewItemID = items.first?.id ?? ""
        prepareSelectedManualReviewDefaults()
    }

    func syncManualReviewDefaultsFromType() {
        switch manualReviewType {
        case .salary:
            manualReviewCategory = "Зарплата"
        case .counterparty:
            if manualReviewCategory == "Зарплата" {
                manualReviewCategory = "Прочее"
            }
        case .commission:
            manualReviewCategory = "Комиссии"
        case .taxes:
            manualReviewCategory = "Ндфл и Взносы"
        case .other:
            if manualReviewCategory.isEmpty {
                manualReviewCategory = "Прочее"
            }
        }
        syncManualReviewCategoryWithSelectedOffice()
    }

    func syncManualReviewOfficeSelection(_ office: String) {
        if office.isEmpty {
            let entity = selectedManualReviewItem.flatMap { manualReviewReportDetails()[$0.name]?.entity } ?? ""
            func entityKey(_ value: String) -> String {
                value.trimmingCharacters(in: .whitespacesAndNewlines)
                    .replacingOccurrences(of: "^(ООО|ИП|АО|ПАО)\\s+", with: "", options: [.regularExpression, .caseInsensitive])
                    .lowercased()
            }
            manualReviewEntity = manualReviewAvailableEntities.first { entityKey($0) == entityKey(entity) } ?? ""
            syncManualReviewCategoryWithSelectedOffice()
            return
        }
        manualReviewEntity = officeEntity(for: office)
        syncManualReviewCategoryWithSelectedOffice()
    }

    func syncManualReviewCategoryWithSelectedOffice() {
        let categories = manualReviewAvailableCategories
        guard !categories.isEmpty else { return }
        if !categories.contains(manualReviewCategory) {
            if manualReviewType == .salary, categories.contains("Зарплата") {
                manualReviewCategory = "Зарплата"
            } else if manualReviewType == .commission, categories.contains("Комиссии") {
                manualReviewCategory = "Комиссии"
            } else if manualReviewType == .taxes, categories.contains("Ндфл и Взносы") {
                manualReviewCategory = "Ндфл и Взносы"
            } else {
                manualReviewCategory = categories[0]
            }
        }
    }

    func prepareSelectedManualReviewDefaults() {
        guard let item = selectedManualReviewItem else { return }
        let details = manualReviewReportDetails()[item.name]
        manualReviewPaymentDate = details?.review_fields?["date"] ?? ""
        manualReviewPaymentAmount = details?.review_fields?["amount"] ?? ""
        if details?.review_fields == nil,
           let expression = try? NSRegularExpression(pattern: "_(\\d{2}-\\d{2}-\\d{4})(?:_(?:\\d+|без_номера))?_(\\d+-\\d{2})(?:_\\d+)?\\.pdf$", options: .caseInsensitive),
           let match = expression.firstMatch(in: item.name, range: NSRange(item.name.startIndex..., in: item.name)),
           let dateRange = Range(match.range(at: 1), in: item.name),
           let amountRange = Range(match.range(at: 2), in: item.name) {
            manualReviewPaymentDate = String(item.name[dateRange])
            manualReviewPaymentAmount = String(item.name[amountRange]).replacingOccurrences(of: "-", with: ".")
        }
        manualReviewOriginalPaymentDate = manualReviewPaymentDate
        manualReviewOriginalPaymentAmount = manualReviewPaymentAmount
        if let office = details?.office, officeItems.contains(office) {
            manualReviewOffice = office
        } else {
            manualReviewOffice = ""
        }
        if let category = details?.category, !category.isEmpty {
            manualReviewCategory = normalizedManualReviewCategory(category)
        }
        manualReviewType = suggestedManualReviewType(from: details?.category ?? "")
        manualReviewCounterpartyOrSubfolder = suggestedLabel(from: item.name, removingPaymentSuffix: manualReviewType == .salary)
        if let label = details?.review_fields?["label"], !label.isEmpty {
            manualReviewCounterpartyOrSubfolder = label
        }
        syncManualReviewOfficeSelection(manualReviewOffice)
        syncManualReviewDefaultsFromType()
        if manualReviewType == .salary,
           let employee = suggestedEmployeeLabel(
               fileName: item.name,
               office: manualReviewOffice,
               reason: details?.reason ?? ""
           ) {
            manualReviewCounterpartyOrSubfolder = employee
        }
    }

    func openSelectedManualReviewFile() {
        guard let item = selectedManualReviewItem else { return }
        NSWorkspace.shared.open(item.url)
    }

    func applyManualReviewSelection() {
        guard !isRunning else { return }
        guard let item = selectedManualReviewItem else {
            showError("Выберите файл из ручной папки.")
            return
        }
        guard let archiveRoot = resultArchiveRootURL() else {
            showError("Не найден итоговый архив.")
            return
        }
        guard !manualReviewOffice.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            showError("Выберите офис для документа.")
            return
        }
        let label = manualReviewCounterpartyOrSubfolder.trimmingCharacters(in: .whitespacesAndNewlines)
        if (manualReviewType == .salary || manualReviewType == .counterparty) && label.isEmpty {
            showError(manualReviewType == .salary ? "Укажите ФИО сотрудника." : "Укажите контрагента.")
            return
        }
        if manualReviewType == .salary || manualReviewType == .commission || manualReviewType == .taxes {
            guard !manualReviewPaymentDate.isEmpty, !manualReviewPaymentAmount.isEmpty else {
                showError("Проверьте дату и сумму платежа по документу.")
                return
            }
        }

        var environment = ProcessInfo.processInfo.environment
        environment["SORTING_RULES_FILE"] = AppPaths.rulesFile.path
        if let binary = AppPaths.bundledOCRBinary {
            environment["SORTING_OCR_BINARY"] = binary.path
        }
        if let binary = AppPaths.bundledPDFMerger {
            environment["SORTING_PDF_MERGER"] = binary.path
        }
        startPythonProcess(
            command: manualDecisionCommand(archiveRoot: archiveRoot, fileName: item.name),
            environment: environment,
            startedStatus: "Применение ручного решения...",
            completionLine: "Ручная корректировка применена.",
            targetArchivePath: archiveRoot.path,
            resetSummary: false
        )
    }

    func manualDecisionCommand(archiveRoot: URL, fileName: String) -> [String] {
        let kind: String
        switch manualReviewType {
        case .salary: kind = "salary"
        case .counterparty: kind = "contractor"
        case .commission: kind = "commission"
        case .taxes: kind = "taxes"
        case .other: kind = "other"
        }
        var command = ["/usr/bin/env", "python3", "-u", AppPaths.applyManualDecisionScript.path,
                "--archive-root", archiveRoot.path, "--file-name", fileName,
                "--action", "move", "--kind", kind, "--office", manualReviewOffice,
                "--entity", manualReviewEntity, "--category", manualReviewCategory,
                "--label", manualReviewCounterpartyOrSubfolder, "--save-to-rules"]
        if !manualReviewPaymentDate.isEmpty || !manualReviewPaymentAmount.isEmpty {
            command += ["--payment-date", manualReviewPaymentDate, "--payment-amount", manualReviewPaymentAmount]
        }
        return command
    }

    func refreshCompletionReport() {
        guard !resultArchivePath.isEmpty,
              let data = try? Data(contentsOf: URL(fileURLWithPath: resultArchivePath).appendingPathComponent("Итог_обработки.json")),
              let report = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            completionReportSummary = ""
            return
        }
        func count(_ key: String) -> Int { report[key] as? Int ?? 0 }
        completionReportSummary = "Входных: \(count("input_count"))\nОбработано: \(count("processed"))\nИсключено повторов: \(count("excluded_duplicate"))\nРучная проверка: \(count("pending"))\nНе распределено: \(count("unresolved"))\nНе найдено: \(count("missing"))"
    }

    func openCompletionReport() {
        guard !resultArchivePath.isEmpty else { return }
        NSWorkspace.shared.open(URL(fileURLWithPath: resultArchivePath).appendingPathComponent("Итог_обработки.txt"))
    }

    func deleteSelectedManualReviewFile() {
        guard !isRunning else { return }
        if selectedManualReviewIsSalaryDuplicate {
            excludeSelectedSalaryDuplicate()
            return
        }
        guard let item = selectedManualReviewItem else { return }
        do {
            try FileManager.default.trashItem(at: item.url, resultingItemURL: nil)
            statusText = "Файл удален из ручной папки."
            refreshManualReviewItems()
            runFinalizeIfNeeded()
        } catch {
            showError("Не удалось удалить файл.\n\(error.localizedDescription)")
        }
    }

    func excludeSelectedSalaryDuplicate() {
        guard !isRunning else { return }
        guard let item = selectedManualReviewItem, selectedManualReviewIsSalaryDuplicate else { return }
        guard let manualRoot = manualReviewRootURL else {
            showError("Не найдена папка ручной проверки.")
            return
        }
        let excludedRoot = manualRoot.appendingPathComponent("Исключенные_повторы", isDirectory: true)
        let destination = excludedRoot.appendingPathComponent(item.url.lastPathComponent)
        do {
            try FileManager.default.createDirectory(at: excludedRoot, withIntermediateDirectories: true)
            let finalDestination = uniqueManualReviewDestination(for: destination)
            try FileManager.default.moveItem(at: item.url, to: finalDestination)
            statusText = "Повтор сохранен в ручной проверке и исключен из расчетов."
            refreshManualReviewItems()
            runFinalizeIfNeeded()
        } catch {
            showError("Не удалось исключить повторную выплату.\n\(error.localizedDescription)")
        }
    }

    private func resultArchiveRootURL() -> URL? {
        let trimmed = resultArchivePath.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return nil }
        return URL(fileURLWithPath: trimmed)
    }

    func manualReviewDestinationURL(archiveRoot: URL, fileName: String) -> URL {
        var url = archiveRoot
        let office = manualReviewOffice.trimmingCharacters(in: .whitespacesAndNewlines)
        let category = manualReviewCategory.trimmingCharacters(in: .whitespacesAndNewlines)

        if !office.isEmpty {
            url.appendPathComponent(office)
        }
        if !category.isEmpty {
            url.appendPathComponent(category)
        }
        return url.appendingPathComponent(fileName)
    }

    private func uniqueManualReviewDestination(for destination: URL) -> URL {
        let fileManager = FileManager.default
        guard fileManager.fileExists(atPath: destination.path) else { return destination }

        let ext = destination.pathExtension
        let stem = destination.deletingPathExtension().lastPathComponent
        let parent = destination.deletingLastPathComponent()
        var index = 2
        var candidate = destination

        while fileManager.fileExists(atPath: candidate.path) {
            let newName = ext.isEmpty ? "\(stem)_\(index)" : "\(stem)_\(index).\(ext)"
            candidate = parent.appendingPathComponent(newName)
            index += 1
        }
        return candidate
    }

    private func saveManualReviewSelectionToRules() throws {
        let office = manualReviewOffice.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !office.isEmpty else { return }

        let content = (try? String(contentsOf: AppPaths.rulesFile, encoding: .utf8)) ?? ""
        let currentFolders = manualReviewAvailableCategories
        var form = RulesEditing.normalizeOfficeForm(
            RulesEditing.parseOfficeForm(from: content, office: office),
            allowedCategories: currentFolders
        )

        let entity = manualReviewEntity.trimmingCharacters(in: .whitespacesAndNewlines)
        if !entity.isEmpty {
            form.entity = entity
        }

        let category = manualReviewCategory.trimmingCharacters(in: .whitespacesAndNewlines)
        if !category.isEmpty && !form.allowedCategories.contains(category) {
            form.allowedCategories.append(category)
        }

        let label = manualReviewCounterpartyOrSubfolder.trimmingCharacters(in: .whitespacesAndNewlines)
        if manualReviewType == .salary && !label.isEmpty {
            if !form.employees.contains(where: { $0.caseInsensitiveCompare(label) == .orderedSame }) {
                form.employees.append(label)
            }
        }

        if manualReviewType != .salary && !category.isEmpty && !label.isEmpty {
            var rules = form.contractorRules[category] ?? []
            if !rules.contains(where: { rule in
                rule.name.caseInsensitiveCompare(label) == .orderedSame
                    || rule.aliases.contains(where: { $0.caseInsensitiveCompare(label) == .orderedSame })
            }) {
                rules.append(ContractorRuleForm(name: label, createFolder: false, aliases: [label]))
            }
            form.contractorRules[category] = rules
        }

        let normalized = RulesEditing.normalizeOfficeForm(form, allowedCategories: currentFolders)
        let updated = RulesEditing.replaceOfficeSection(
            in: content,
            office: office,
            newSection: RulesEditing.buildOfficeSection(from: normalized)
        )
        try updated.write(to: AppPaths.rulesFile, atomically: true, encoding: .utf8)
        loadOfficeList()
        loadOfficeRules()
    }

    private func runFinalizeIfNeeded() {
        guard let archiveRoot = resultArchiveRootURL(), !isRunning else { return }
        let script = AppPaths.finalizeArchiveScript
        guard FileManager.default.fileExists(atPath: script.path) else { return }
        let command = [
            "/usr/bin/env",
            "python3",
            "-u",
            script.path,
            "--archive-root", archiveRoot.path,
        ]
        var environment = ProcessInfo.processInfo.environment
        environment["SORTING_RULES_FILE"] = AppPaths.rulesFile.path
        if let bundledPDFMerger = AppPaths.bundledPDFMerger {
            environment["SORTING_PDF_MERGER"] = bundledPDFMerger.path
        }
        startPythonProcess(
            command: command,
            environment: environment,
            startedStatus: "Идет финализация архива...",
            completionLine: "Финализация завершена.",
            targetArchivePath: archiveRoot.path,
            resetSummary: false
        )
    }

    func officeEntity(for office: String) -> String {
        let content = (try? String(contentsOf: AppPaths.rulesFile, encoding: .utf8)) ?? ""
        return RulesEditing.parseOfficeForm(from: content, office: office).entity
    }

    func officeCategories(for office: String) -> [String] {
        let content = (try? String(contentsOf: AppPaths.rulesFile, encoding: .utf8)) ?? ""
        let form = RulesEditing.parseOfficeForm(from: content, office: office)
        let categories = form.allowedCategories
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
        return categories.isEmpty ? RulesEditing.standardCategories : categories
    }

    private func manualReviewReportDetails() -> [String: ManualReviewDetails] {
        if let metadataURL = manualReviewRootURL?.appendingPathComponent(".manual_review.json"),
           let data = try? Data(contentsOf: metadataURL),
           let details = try? JSONDecoder().decode([String: ManualReviewDetails].self, from: data) {
            return details
        }
        guard let reportURL = manualReviewReportURL, let text = try? String(contentsOf: reportURL, encoding: .utf8) else {
            return [:]
        }
        var result: [String: ManualReviewDetails] = [:]
        let blocks = text.components(separatedBy: "\n\n")
        for block in blocks {
            let lines = block.split(separator: "\n").map(String.init)
            guard let fileLine = lines.first(where: { $0.hasPrefix("Файл: ") }) else { continue }
            let name = String(fileLine.dropFirst("Файл: ".count))
            let office = value(prefix: "Офис: ", in: lines)
            let category = value(prefix: "Категория: ", in: lines)
            let entity = value(prefix: "Юрлицо: ", in: lines)
            let reason = value(prefix: "Причина: ", in: lines)
            result[name] = ManualReviewDetails(
                office: office == "?" ? "" : office,
                category: category == "?" ? "" : category,
                entity: entity == "?" ? "" : entity,
                reason: reason,
                salary_duplicate: nil
            )
        }
        return result
    }

    private func value(prefix: String, in lines: [String]) -> String {
        guard let line = lines.first(where: { $0.hasPrefix(prefix) }) else { return "" }
        return String(line.dropFirst(prefix.count))
    }

    private func normalizedManualReviewCategory(_ category: String) -> String {
        switch category {
        case "Комиссии":
            return "Комиссии"
        case "Налоги", "Взносы", "Ндфл и Взносы":
            return "Ндфл и Взносы"
        default:
            return category
        }
    }

    func saveCurrentManualReviewRules() throws {
        try saveManualReviewSelectionToRules()
    }

    private func suggestedManualReviewType(from category: String) -> ManualReviewType {
        switch normalizedManualReviewCategory(category) {
        case "Зарплата":
            return .salary
        case "Комиссии":
            return .commission
        case "Ндфл и Взносы":
            return .taxes
        case "":
            return .other
        default:
            return .counterparty
        }
    }

    private func suggestedLabel(from fileName: String, removingPaymentSuffix: Bool = false) -> String {
        var stem = URL(fileURLWithPath: fileName).deletingPathExtension().lastPathComponent
        if removingPaymentSuffix {
            stem = stem.replacingOccurrences(
                of: "[_\\s]\\d{2}-\\d{2}-\\d{4}[_\\s]\\d+-\\d{2}(?:_\\d+)?$",
                with: "", options: .regularExpression
            )
        }
        return stem.replacingOccurrences(of: "_", with: " ").trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private func suggestedEmployeeLabel(fileName: String, office: String, reason: String) -> String? {
        let content = (try? String(contentsOf: AppPaths.rulesFile, encoding: .utf8)) ?? ""
        let employees = RulesEditing.parseOfficeForm(from: content, office: office).employees
        let fileLabel = suggestedLabel(from: fileName)
        return employees.first { employee in
            reason.range(of: employee, options: [.caseInsensitive, .diacriticInsensitive]) != nil
                || fileLabel.range(of: employee, options: [.caseInsensitive, .diacriticInsensitive]) != nil
        }
    }
}
