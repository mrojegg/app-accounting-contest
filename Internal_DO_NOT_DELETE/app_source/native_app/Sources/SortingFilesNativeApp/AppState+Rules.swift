import Foundation

extension AppState {
    func openSettings() {
        do {
            try enforceRequiredOperationalRules()
        } catch {
            showError("Не удалось проверить обязательные правила.\n\(error.localizedDescription)")
        }
        settingsOriginalRulesContent = (try? String(contentsOf: AppPaths.rulesFile, encoding: .utf8)) ?? ""
        loadOfficeList()
        loadSpecialRules()
        loadOfficeRules()
        isShowingSettings = true
    }

    func loadOfficeList() {
        let content = (try? String(contentsOf: AppPaths.rulesFile, encoding: .utf8)) ?? ""
        let offices = RulesEditing.loadOfficeList(from: content)
        if !offices.isEmpty {
            officeItems = offices
            if !officeItems.contains(selectedOffice) {
                selectedOffice = officeItems.first ?? selectedOffice
            }
        }
    }

    func loadOfficeRules() {
        let content = (try? String(contentsOf: AppPaths.rulesFile, encoding: .utf8)) ?? ""
        let parsed = RulesEditing.parseOfficeForm(from: content, office: selectedOffice)
        let form = RulesEditing.normalizeOfficeForm(
            parsed,
            allowedCategories: officeCategoryUniverse(from: parsed)
        )
        officeEntityInput = form.entity
        officeEmployees = form.employees
        officeAllowedCategories = form.allowedCategories
        officeContractorRules = form.contractorRules
    }

    @discardableResult
    func saveOfficeRules() -> Bool {
        guard RulesEditing.isValidOfficeNumber(selectedOffice) else {
            showError("Номер офиса должен состоять только из цифр.")
            return false
        }
        let content = (try? String(contentsOf: AppPaths.rulesFile, encoding: .utf8)) ?? ""
        let input = OfficeRuleForm(
            office: selectedOffice,
            entity: officeEntityInput,
            allowedCategories: officeAllowedCategories,
            employees: officeEmployees,
            contractorRules: officeContractorRules
        )
        let form = RulesEditing.normalizeOfficeForm(
            input,
            allowedCategories: officeCategoryUniverse(from: input)
        )
        let section = RulesEditing.buildOfficeSection(from: form)
        let updated = RulesEditing.replaceOfficeSection(in: content, office: selectedOffice, newSection: section)
        do {
            try updated.write(to: AppPaths.rulesFile, atomically: true, encoding: .utf8)
            statusText = "Правила офиса сохранены."
            loadOfficeList()
            loadOfficeRules()
            return true
        } catch {
            showError("Не удалось сохранить правила офиса.\n\(error.localizedDescription)")
            return false
        }
    }

    func addOffice() {
        let office = newOfficeInput.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !office.isEmpty else { return }
        guard RulesEditing.isValidOfficeNumber(office) else {
            showError("Номер офиса должен состоять только из цифр.")
            return
        }
        let content = (try? String(contentsOf: AppPaths.rulesFile, encoding: .utf8)) ?? ""
        if RulesEditing.loadOfficeList(from: content).contains(office) {
            selectedOffice = office
            loadOfficeList()
            loadOfficeRules()
            return
        }
        let updated = RulesEditing.addOffice(in: content, office: office)
        do {
            try updated.write(to: AppPaths.rulesFile, atomically: true, encoding: .utf8)
            newOfficeInput = ""
            loadOfficeList()
            selectedOffice = office
            loadOfficeRules()
        } catch {
            showError("Не удалось добавить офис.\n\(error.localizedDescription)")
        }
    }

    func deleteSelectedOffice() {
        let office = selectedOffice.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !office.isEmpty else { return }
        loadOfficeList()
        guard officeItems.count > 1 else {
            showError("Нельзя удалить последний офис.")
            return
        }
        guard confirmAction(
            title: "Удалить офис \(office)?",
            message: "Сотрудники, контрагенты и категории этого офиса будут удалены из правил."
        ) else {
            return
        }

        let content = (try? String(contentsOf: AppPaths.rulesFile, encoding: .utf8)) ?? ""
        let updated = RulesEditing.removeOffice(in: content, office: office)
        do {
            try updated.write(to: AppPaths.rulesFile, atomically: true, encoding: .utf8)
            loadOfficeList()
            selectedOffice = officeItems.first ?? ""
            loadOfficeRules()
            statusText = "Офис удален."
        } catch {
            showError("Не удалось удалить офис.\n\(error.localizedDescription)")
        }
    }

    func loadSpecialRules() {
        let content = (try? String(contentsOf: AppPaths.rulesFile, encoding: .utf8)) ?? ""
        let form = RulesEditing.parseGeneralRules(from: content)
        let salarySettings = RulesEditing.parseSalaryTableSettings(from: form.tableRules)
        let manualReviewSettings = RulesEditing.parseManualReviewSettings(from: form.specialRules)
        generalPurposeLines = form.purposeLines
        generalPrinciples = form.principles
        generalArchiveFolders = form.archiveFolders
        generalFolderOrder = form.folderOrder
        generalTableRules = RulesEditing.nonSalaryTableRules(from: form.tableRules)
        salaryTableEnabled = true
        salaryTableSplitSameDatePayments = false
        salaryTableTotalColumnTitle = salarySettings.totalColumnTitle
        salaryTableTotalsRowTitle = salarySettings.totalsRowTitle
        createFoldersOnlyWhenDocumentsExist = true
        doNotCreateEmptyFoldersInAdvance = true
        createManualReviewFolderOnlyWhenNeeded = true
        createSpecialSubfoldersByRoutingRules = true
        protectExistingFilesWithUniqueSuffix = true
        routeByDocumentTextFirst = true
        routeOfficeBeforeCategoryFinalization = true
        useContractorsAsCategorySignals = true
        unresolvedRouteGoesToManualReview = true
        sendLowConfidenceDocumentsToManualReview = true
        sendMissingOfficeDocumentsToManualReview = true
        preserveReadableNamesInManualReview = manualReviewSettings.preserveReadableNamesInManualReview
        createManualReviewReport = manualReviewSettings.createManualReviewReport
        namingUseExtractedText = true
        namingFallbackToOriginalWhenNoText = true
        namingMakeWindowsSafe = true
        namingKeepUniqueSuffixOnConflict = true
        commissionsDetectedByPaymentText = true
        commissionsUseOfficeEntityRouting = true
        commissionsCreateOfficeExcel = true
        taxesDetectedByPaymentPhrases = true
        taxesUseOfficeEntityRouting = true
        taxesCreateTaxAndInsuranceExcel = true
        internetPrioritizeKnownProviders = true
        internetAllowSpecialProviderSubfolders = true
        internetCreateSubfoldersByOfficeContractors = true
        internetNormalizeBrokenProviderText = true
        generalNamingFormat = form.namingFormat
        generalLowQualityRules = form.lowQualityRules
        generalExtraHandlers = form.extraHandlers
        specialRules = RulesEditing.nonFolderCreationSpecialRules(from: form.specialRules)
    }

    @discardableResult
    func saveSpecialRules() -> Bool {
        let content = (try? String(contentsOf: AppPaths.rulesFile, encoding: .utf8)) ?? ""
        let salaryDefaults = RulesEditing.defaultSalaryTableSettings()
        let totalColumnTitle = salaryTableTotalColumnTitle.trimmingCharacters(in: .whitespacesAndNewlines)
        let totalsRowTitle = salaryTableTotalsRowTitle.trimmingCharacters(in: .whitespacesAndNewlines)
        let tableRules = RulesEditing.mergeTableRules(
            nonSalaryRules: generalTableRules,
            salarySettings: SalaryTableSettings(
                isEnabled: true,
                splitSameDatePaymentsIntoSeparateColumns: false,
                totalColumnTitle: totalColumnTitle.isEmpty ? salaryDefaults.totalColumnTitle : totalColumnTitle,
                totalsRowTitle: totalsRowTitle.isEmpty ? salaryDefaults.totalsRowTitle : totalsRowTitle
            ),
            commissionSettings: RulesEditing.defaultCommissionSettings(),
            taxSettings: RulesEditing.defaultTaxAndInsuranceSettings()
        )
        let mergedSpecialRules = RulesEditing.mergeSpecialRules(
            nonFolderRules: specialRules,
            folderSettings: RulesEditing.defaultFolderCreationSettings(),
            routingSettings: RulesEditing.defaultRoutingCategorySettings(),
            manualReviewSettings: ManualReviewSettings(
                sendLowConfidenceDocumentsToManualReview: true,
                sendMissingOfficeDocumentsToManualReview: true,
                preserveReadableNamesInManualReview: preserveReadableNamesInManualReview,
                createManualReviewReport: createManualReviewReport
            ),
            namingSettings: RulesEditing.defaultNamingBehaviorSettings(),
            commissionSettings: RulesEditing.defaultCommissionSettings(),
            taxSettings: RulesEditing.defaultTaxAndInsuranceSettings(),
            internetSettings: RulesEditing.defaultInternetProviderSettings()
        )
        let form = GeneralRulesForm(
            purposeLines: generalPurposeLines,
            principles: generalPrinciples,
            archiveFolders: generalArchiveFolders,
            folderOrder: generalFolderOrder,
            tableRules: tableRules,
            namingFormat: generalNamingFormat,
            lowQualityRules: generalLowQualityRules,
            extraHandlers: generalExtraHandlers,
            specialRules: mergedSpecialRules
        )
        let updated = RulesEditing.replaceGeneralRules(in: content, form: form)
        do {
            try updated.write(to: AppPaths.rulesFile, atomically: true, encoding: .utf8)
            statusText = "Настройки сохранены."
            loadSpecialRules()
            loadOfficeRules()
            return true
        } catch {
            showError("Не удалось сохранить специальные правила.\n\(error.localizedDescription)")
            return false
        }
    }

    func closeSettingsWithoutSaving() {
        if let original = settingsOriginalRulesContent {
            do {
                try original.write(to: AppPaths.rulesFile, atomically: true, encoding: .utf8)
            } catch {
                showError("Не удалось откатить несохраненные настройки.\n\(error.localizedDescription)")
            }
        }
        settingsOriginalRulesContent = nil
        loadOfficeList()
        loadOfficeRules()
        loadSpecialRules()
        isShowingSettings = false
    }

    func saveSettingsAndClose() {
        guard saveOfficeRules() else { return }
        guard saveSpecialRules() else { return }
        settingsOriginalRulesContent = nil
        isShowingSettings = false
    }

    func enforceRequiredOperationalRules() throws {
        let content = try String(contentsOf: AppPaths.rulesFile, encoding: .utf8)
        let updated = RulesEditing.enforcingRequiredOperationalRules(in: content)
        if updated != content {
            try updated.write(to: AppPaths.rulesFile, atomically: true, encoding: .utf8)
        }
    }

    private func activeArchiveFolders() -> [String] {
        normalizedArchiveFolders(from: generalArchiveFolders)
    }

    private func officeCategoryUniverse(from form: OfficeRuleForm) -> [String] {
        uniqueOrdered(
            activeArchiveFolders()
                + form.allowedCategories
                + Array(form.contractorRules.keys)
                + officeAllowedCategories
                + Array(officeContractorRules.keys)
        )
    }

    private func normalizedArchiveFolders(from folders: [String]) -> [String] {
        let normalized = folders
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
        return normalized.isEmpty ? RulesEditing.standardCategories : normalized
    }

    private func uniqueOrdered(_ values: [String]) -> [String] {
        var seen: Set<String> = []
        return values
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
            .filter { seen.insert($0).inserted }
    }

    private func normalizeAllOfficeSections(in content: String, allowedCategories: [String]) -> String {
        var updated = content
        for office in RulesEditing.loadOfficeList(from: content) {
            let normalizedForm = RulesEditing.normalizeOfficeForm(
                RulesEditing.parseOfficeForm(from: updated, office: office),
                allowedCategories: allowedCategories
            )
            updated = RulesEditing.replaceOfficeSection(
                in: updated,
                office: office,
                newSection: RulesEditing.buildOfficeSection(from: normalizedForm)
            )
        }
        return updated
    }
}
