import XCTest
@testable import SortingFilesNativeApp

@MainActor
final class AppStateRulesTests: XCTestCase {
    override func tearDown() {
        AppPaths.rulesFileOverride = nil
        super.tearDown()
    }

    func testSaveSettingsAndClosePersistsOfficeAndAdminDrafts() throws {
        let rulesFile = try makeRulesFile()
        AppPaths.rulesFileOverride = rulesFile
        let state = AppState()

        state.openSettings()
        state.selectedOffice = "120"
        state.loadOfficeRules()
        state.officeEntityInput = "ИП Иванов"
        state.officeEmployees.append("Новый Сотрудник")
        state.salaryTableEnabled = false
        state.salaryTableTotalColumnTitle = "Итог сотрудника"
        state.createManualReviewReport = false
        state.selectedSettingsSection = .admin
        state.saveSettingsAndClose()

        let content = try String(contentsOf: rulesFile, encoding: .utf8)
        XCTAssertTrue(content.contains("- `ИП Иванов`"))
        XCTAssertTrue(content.contains("- Новый Сотрудник"))
        XCTAssertTrue(content.contains("Для любого офиса с папкой `Зарплата` автоматически создается `Зарплата_<офис>.xlsx`."))
        XCTAssertTrue(content.contains("Итоговый столбец зарплатной таблицы называется `Итог сотрудника`."))
        XCTAssertFalse(content.contains("автоматически создается `_report.txt`"))
        XCTAssertFalse(state.isShowingSettings)
    }

    func testCloseSettingsWithoutSavingRestoresRulesFile() throws {
        let rulesFile = try makeRulesFile()
        AppPaths.rulesFileOverride = rulesFile
        let state = AppState()
        let original = try String(contentsOf: rulesFile, encoding: .utf8)

        state.openSettings()
        state.newOfficeInput = "130"
        state.addOffice()
        state.salaryTableEnabled = false
        state.closeSettingsWithoutSaving()

        XCTAssertEqual(try String(contentsOf: rulesFile, encoding: .utf8), original)
        XCTAssertFalse(state.officeItems.contains("130"))
    }

    private func makeRulesFile() throws -> URL {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        let rulesFile = root.appendingPathComponent("sorting_rules.md")
        try rulesContent.write(to: rulesFile, atomically: true, encoding: .utf8)
        return rulesFile
    }

    private var rulesContent: String {
        """
        # Регламент сортировки документов

        ## 1. Назначение файла

        Тестовые правила.

        ## 3. Базовая структура архива

        - `Зарплата`
        - `Интернет`

        ## 5. Таблицы

        - Для любого офиса с папкой `Зарплата` автоматически создается `Зарплата_<офис>.xlsx`.

        ## 11. Офисы

        ### Офис 120

        Юрлицо:
        - `ООО ТЕСТ`

        Разрешенные категории по умолчанию:
        - `Зарплата`

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
