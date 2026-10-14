import XCTest
@testable import SortingFilesNativeApp

@MainActor
final class AppStateManualReviewTests: XCTestCase {
    private var tempRoots: [URL] = []

    override func tearDown() {
        AppPaths.rulesFileOverride = nil
        for root in tempRoots {
            try? FileManager.default.removeItem(at: root)
        }
        tempRoots = []
        super.tearDown()
    }

    func testManualReviewDestinationDoesNotCreateCounterpartySubfolder() throws {
        let root = try makeTempRoot()
        let rulesFile = try makeRulesFile(in: root)
        AppPaths.rulesFileOverride = rulesFile
        let archive = root.appendingPathComponent("archive", isDirectory: true)
        let state = AppState()
        state.manualReviewType = .counterparty
        state.manualReviewOffice = "120"
        state.manualReviewEntity = "ТЕСТ"
        state.manualReviewCategory = "Интернет"
        state.manualReviewCounterpartyOrSubfolder = "Провайдер"

        let destination = state.manualReviewDestinationURL(archiveRoot: archive, fileName: "a_problem.pdf")

        XCTAssertEqual(destination.path, archive.appendingPathComponent("120/Интернет/a_problem.pdf").path)
        XCTAssertFalse(destination.path.contains("/Провайдер/"))
    }

    func testManualReviewUsesSharedProcessorWithExplicitEmployeeAndRules() throws {
        let root = try makeTempRoot()
        AppPaths.rulesFileOverride = try makeRulesFile(in: root)
        let state = AppState()
        state.manualReviewType = .salary
        state.manualReviewOffice = "120"
        state.manualReviewCounterpartyOrSubfolder = "Новый Сотрудник"
        let command = state.manualDecisionCommand(archiveRoot: root, fileName: "scan.pdf")
        XCTAssertTrue(command.contains(AppPaths.applyManualDecisionScript.path))
        XCTAssertTrue(command.contains("salary"))
        XCTAssertTrue(command.contains("Новый Сотрудник"))
        XCTAssertTrue(command.contains("--save-to-rules"))
        XCTAssertFalse(command.contains("--subfolder"))
    }

    func testReviewFieldsPrefillAndCorrectionsArePassedToProcessor() throws {
        let root = try makeTempRoot()
        AppPaths.rulesFileOverride = try makeRulesFile(in: root)
        let manual = root.appendingPathComponent("Требует_ручной_проверки")
        try FileManager.default.createDirectory(at: manual, withIntermediateDirectories: true)
        try Data("pdf".utf8).write(to: manual.appendingPathComponent("scan.pdf"))
        let details: [String: Any] = ["scan.pdf": ["office": "120", "entity": "ООО ТЕСТ", "category": "Зарплата",
            "reason": "Проверьте реквизиты", "review_fields": ["label": "Старый Сотрудник", "date": "14-08-2026", "amount": "1000.00"]]]
        try JSONSerialization.data(withJSONObject: details).write(to: manual.appendingPathComponent(".manual_review.json"))
        let state = AppState()
        state.resultArchivePath = root.path
        state.refreshManualReviewItems()
        XCTAssertEqual(state.manualReviewPaymentDate, "14-08-2026")
        XCTAssertEqual(state.manualReviewPaymentAmount, "1000.00")
        XCTAssertFalse(state.manualPaymentFieldsHaveEdits)
        state.manualReviewPaymentAmount = "1500,00"
        XCTAssertTrue(state.manualPaymentFieldsHaveEdits)
        let command = state.manualDecisionCommand(archiveRoot: root, fileName: "scan.pdf")
        XCTAssertTrue(command.contains("--payment-date"))
        XCTAssertTrue(command.contains("--payment-amount"))
        XCTAssertTrue(command.contains("1500,00"))
        state.startManualReviewReprocess()
        XCTAssertFalse(state.isRunning)
        XCTAssertTrue(state.errorMessage?.contains("Применить") == true)
    }

    func testCompletionSummaryReadsIndependentInputCounts() throws {
        let root = try makeTempRoot()
        AppPaths.rulesFileOverride = try makeRulesFile(in: root)
        let report = ["input_count": 7, "processed": 4, "excluded_duplicate": 2, "pending": 1, "missing": 0, "unresolved": 0]
        try JSONSerialization.data(withJSONObject: report).write(to: root.appendingPathComponent("Итог_обработки.json"))
        let state = AppState()
        state.resultArchivePath = root.path
        state.refreshCompletionReport()
        XCTAssertTrue(state.completionReportSummary.contains("Входных: 7"))
        XCTAssertTrue(state.completionReportSummary.contains("Исключено повторов: 2"))
        XCTAssertTrue(state.completionReportSummary.contains("Ручная проверка: 1"))
    }

    func testManualReviewReprocessSavesCurrentRuleBeforeRunning() throws {
        let root = try makeTempRoot()
        let rulesFile = try makeRulesFile(in: root)
        AppPaths.rulesFileOverride = rulesFile
        let archive = root.appendingPathComponent("archive", isDirectory: true)
        let manual = archive.appendingPathComponent("Требует_ручной_проверки", isDirectory: true)
        try FileManager.default.createDirectory(at: manual, withIntermediateDirectories: true)
        let selected = manual.appendingPathComponent("salary.pdf")
        try Data("pdf".utf8).write(to: selected)

        let state = AppState()
        state.resultArchivePath = archive.path
        state.refreshManualReviewItems()
        state.selectedManualReviewItemID = selected.path
        state.manualReviewType = .salary
        state.manualReviewOffice = "120"
        state.manualReviewEntity = "ТЕСТ"
        state.manualReviewCategory = "Зарплата"
        state.manualReviewCounterpartyOrSubfolder = "Авансы"
        try state.saveCurrentManualReviewRules()

        let content = try String(contentsOf: rulesFile, encoding: .utf8)
        XCTAssertTrue(content.contains("- Авансы"))
    }

    func testManualReviewOfficeSelectionChainsEntityAndOfficeCategories() throws {
        let root = try makeTempRoot()
        let rulesFile = try makeRulesFile(in: root)
        AppPaths.rulesFileOverride = rulesFile
        let state = AppState()
        state.manualReviewCategory = "Аренда"

        state.manualReviewOffice = "120"
        state.syncManualReviewOfficeSelection("120")

        XCTAssertEqual(state.manualReviewEntity, "ООО ТЕСТ")
        XCTAssertEqual(state.manualReviewAvailableEntities, ["ООО ТЕСТ"])
        XCTAssertEqual(state.manualReviewAvailableCategories, ["Зарплата", "Интернет"])
        XCTAssertEqual(state.manualReviewCategory, "Зарплата")
    }

    func testSalaryDuplicatePrefillsKnownEmployeeAndShowsDuplicateDecision() throws {
        let root = try makeTempRoot()
        let rulesFile = try makeRulesFile(in: root)
        AppPaths.rulesFileOverride = rulesFile
        let archive = root.appendingPathComponent("archive", isDirectory: true)
        let manual = archive.appendingPathComponent("Требует_ручной_проверки", isDirectory: true)
        try FileManager.default.createDirectory(at: manual, withIntermediateDirectories: true)
        let fileName = "старый_сотрудник_01-06-2026_50000-00.pdf"
        try Data("pdf".utf8).write(to: manual.appendingPathComponent(fileName))
        let report = """
        Отчет по документам, требующим ручной проверки

        Файл: \(fileName)
        Уверенность: 40%
        Офис: 120
        Категория: Зарплата
        Юрлицо: ООО ТЕСТ
        Причина: Возможный повтор зарплаты: сотрудник Старый Сотрудник, сумма 50000,00.
        """
        try report.write(to: manual.appendingPathComponent("_report.txt"), atomically: true, encoding: .utf8)

        let state = AppState()
        state.resultArchivePath = archive.path
        state.refreshManualReviewItems()

        XCTAssertEqual(state.manualReviewType, .salary)
        XCTAssertEqual(state.manualReviewOffice, "120")
        XCTAssertEqual(state.manualReviewCounterpartyOrSubfolder, "Старый Сотрудник")
        XCTAssertTrue(state.selectedManualReviewIsSalaryDuplicate)
    }

    func testSalaryDuplicateIsPreservedInsideExcludedManualFolder() throws {
        let root = try makeTempRoot()
        let rulesFile = try makeRulesFile(in: root)
        AppPaths.rulesFileOverride = rulesFile
        let archive = root.appendingPathComponent("archive", isDirectory: true)
        let manual = archive.appendingPathComponent("Требует_ручной_проверки", isDirectory: true)
        try FileManager.default.createDirectory(at: manual, withIntermediateDirectories: true)
        let duplicateName = "старый_сотрудник_01-06-2026_50000-00.pdf"
        let duplicate = manual.appendingPathComponent(duplicateName)
        try Data("pdf".utf8).write(to: duplicate)
        try Data("pdf".utf8).write(to: manual.appendingPathComponent("z_other.pdf"))
        let report = """
        Отчет по документам, требующим ручной проверки

        Файл: \(duplicateName)
        Уверенность: 40%
        Офис: 120
        Категория: Зарплата
        Юрлицо: ООО ТЕСТ
        Причина: Возможный повтор зарплаты: сотрудник Старый Сотрудник, сумма 50000,00.
        """
        try report.write(to: manual.appendingPathComponent("_report.txt"), atomically: true, encoding: .utf8)

        let state = AppState()
        state.resultArchivePath = archive.path
        state.refreshManualReviewItems()
        state.selectedManualReviewItemID = try XCTUnwrap(
            state.manualReviewItems.first(where: { $0.name.contains("50000-00") })
        ).id
        state.prepareSelectedManualReviewDefaults()
        state.excludeSelectedSalaryDuplicate()

        XCTAssertFalse(FileManager.default.fileExists(atPath: duplicate.path))
        XCTAssertTrue(FileManager.default.fileExists(
            atPath: manual.appendingPathComponent("Исключенные_повторы/\(duplicateName)").path
        ))
        XCTAssertEqual(state.manualReviewItems.map(\.name), ["z_other.pdf"])
    }

    func testThreeDuplicatesKeepTheirTypeAfterSequentialExclusionWithoutTextReport() throws {
        let root = try makeTempRoot()
        AppPaths.rulesFileOverride = try makeRulesFile(in: root)
        let manual = root.appendingPathComponent("Требует_ручной_проверки")
        try FileManager.default.createDirectory(at: manual, withIntermediateDirectories: true)
        var details: [String: [String: Any]] = [:]
        for day in 1...3 {
            let name = "receipt_\(day).pdf"
            try Data("pdf".utf8).write(to: manual.appendingPathComponent(name))
            details[name] = ["office": "120", "entity": "ООО ТЕСТ", "category": "Зарплата",
                             "reason": "Старый Сотрудник, 1000,00", "salary_duplicate": true]
        }
        try JSONSerialization.data(withJSONObject: details).write(to: manual.appendingPathComponent(".manual_review.json"))
        let state = AppState()
        state.resultArchivePath = root.path
        state.refreshManualReviewItems()
        for remaining in stride(from: 3, through: 1, by: -1) {
            XCTAssertEqual(state.manualReviewItems.count, remaining)
            XCTAssertEqual(state.manualReviewType, .salary)
            XCTAssertEqual(state.manualReviewOffice, "120")
            XCTAssertEqual(state.manualReviewCounterpartyOrSubfolder, "Старый Сотрудник")
            XCTAssertTrue(state.selectedManualReviewIsSalaryDuplicate)
            if remaining > 1 {
                // Even the generic delete entry point must archive a flagged duplicate.
                state.deleteSelectedManualReviewFile()
            }
        }
        XCTAssertEqual(try FileManager.default.contentsOfDirectory(atPath: manual.appendingPathComponent("Исключенные_повторы").path).count, 2)
    }

    func testUnknownEmployeeRequiresExplicitOfficeAndDoesNotCopyPreviousOffice() throws {
        let root = try makeTempRoot()
        AppPaths.rulesFileOverride = try makeRulesFile(in: root)
        let manual = root.appendingPathComponent("Требует_ручной_проверки")
        try FileManager.default.createDirectory(at: manual, withIntermediateDirectories: true)
        let name = "новый_сотрудник_15-08-2026_1234-56.pdf"
        try Data("pdf".utf8).write(to: manual.appendingPathComponent(name))
        let details = [name: ["office": "", "entity": "ТЕСТ", "category": "Зарплата", "reason": "Неизвестный сотрудник"]]
        try JSONSerialization.data(withJSONObject: details).write(to: manual.appendingPathComponent(".manual_review.json"))
        let state = AppState()
        state.manualReviewOffice = "120"
        state.resultArchivePath = root.path
        state.refreshManualReviewItems()
        XCTAssertEqual(state.manualReviewOffice, "")
        XCTAssertEqual(state.manualReviewEntity, "ООО ТЕСТ")
        XCTAssertEqual(state.manualReviewType, .salary)
        XCTAssertEqual(state.manualReviewCounterpartyOrSubfolder, "новый сотрудник")
        state.syncManualReviewOfficeSelection("")
        XCTAssertEqual(state.manualReviewEntity, "ООО ТЕСТ")
    }

    private func makeTempRoot() throws -> URL {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        tempRoots.append(root)
        return root
    }

    private func makeRulesFile(in root: URL) throws -> URL {
        let rulesFile = root.appendingPathComponent("sorting_rules.md")
        try rulesContent.write(to: rulesFile, atomically: true, encoding: .utf8)
        return rulesFile
    }

    private var rulesContent: String {
        """
        # Регламент сортировки документов

        ## 3. Базовая структура архива

        - `Зарплата`
        - `Интернет`
        - `Услуги`
        - `Аренда`

        ## 11. Офисы

        ### Офис 120

        Юрлицо:
        - `ООО ТЕСТ`

        Разрешенные категории по умолчанию:
        - `Зарплата`
        - `Интернет`

        Сотрудники:
        - Старый Сотрудник

        Контрагенты:
        - `Интернет`: Провайдер | папка: нет | алиасы: Провайдер

        ## 13. Общие специальные правила

        - Папки офисов и категорий создаются только при первой реальной раскладке документа.
        - Пустые папки заранее не создаются.
        - Папка `Требует_ручной_проверки` создается только когда в нее реально попадает файл или отчет.
        - Специальные подпапки создаются только если сработало специальное правило маршрутизации.
        - При конфликте имен создается новый файл с безопасным уникальным суффиксом, а существующий файл не перезаписывается.
        - Если текст документа читается, маршрутизация опирается на него раньше, чем на имя файла.
        - Сначала приложение старается понять офис, а уже потом окончательно фиксирует категорию и путь.
        - Контрагент из правил офиса усиливает выбор категории и папки.
        - Если после всех проверок путь не собран уверенно, файл уходит в `Требует_ручной_проверки`.
        - Документы с низкой уверенностью распознавания отправляются в `Требует_ручной_проверки`.
        - Если тип документа понятен, но офис не определен, файл отправляется в `Требует_ручной_проверки`.
        - В ручной проверке сохраняется читаемое имя из текста, если его удалось собрать.
        - Для папки `Требует_ручной_проверки` автоматически создается `_report.txt` с причинами ручной обработки.
        - Имя файла собирается из извлеченного текста документа, если полезные поля найдены.
        - Если полезный текст не найден, приложение оставляет безопасный fallback от исходного имени файла.
        - Имена файлов автоматически приводятся к безопасному виду для macOS и Windows.
        - Если итоговое имя уже занято, приложение добавляет уникальный суффикс вместо перезаписи.
        """
    }
}
