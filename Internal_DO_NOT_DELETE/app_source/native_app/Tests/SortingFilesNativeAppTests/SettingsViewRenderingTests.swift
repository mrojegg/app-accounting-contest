import AppKit
import SwiftUI
import XCTest
@testable import SortingFilesNativeApp

@MainActor
final class SettingsViewRenderingTests: XCTestCase {
    func testGuideAndOfficeViewsRenderWithoutChangingRules() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer {
            AppPaths.rulesFileOverride = nil
            try? FileManager.default.removeItem(at: root)
        }
        let rules = root.appendingPathComponent("rules.md")
        try """
        # Правила сортировки

        ## 3. Базовая структура архива

        - `Зарплата`
        - `Интернет`

        ## 11. Офисы

        ### Офис 120

        Юрлицо:
        - `ООО ТЕСТ`

        Разрешенные категории по умолчанию:
        - `Зарплата`
        - `Интернет`

        Сотрудники:
        - Тестовый Сотрудник

        Контрагенты:
        - `Интернет`: Провайдер | папка: нет | алиасы: Провайдер

        ## 13. Общие специальные правила

        """.write(to: rules, atomically: true, encoding: .utf8)
        AppPaths.rulesFileOverride = rules
        let state = AppState()
        let original = try Data(contentsOf: rules)
        state.openSettings()
        state.selectedOffice = "120"
        state.loadOfficeRules()
        XCTAssertEqual(state.officeItems, ["120"])
        XCTAssertEqual(state.officeEntityInput, "ООО ТЕСТ")
        XCTAssertEqual(state.officeEmployees, ["Тестовый Сотрудник"])

        for section in SettingsSection.allCases {
            state.selectedSettingsSection = section
            let view = NSHostingView(rootView: SettingsRootView(state: state)
                .environment(\.colorScheme, .light))
            view.frame = NSRect(x: 0, y: 0, width: 1240, height: 780)
            view.layoutSubtreeIfNeeded()
            let bitmap = try XCTUnwrap(view.bitmapImageRepForCachingDisplay(in: view.bounds))
            view.cacheDisplay(in: view.bounds, to: bitmap)
            var colors: Set<String> = []
            for y in stride(from: 0, to: bitmap.pixelsHigh, by: 12) {
                for x in stride(from: 0, to: bitmap.pixelsWide, by: 12) {
                    if let color = bitmap.colorAt(x: x, y: y)?.usingColorSpace(.deviceRGB) {
                        colors.insert("\(Int(color.redComponent * 255)),\(Int(color.greenComponent * 255)),\(Int(color.blueComponent * 255))")
                    }
                }
            }
            XCTAssertGreaterThan(colors.count, 20, "Blank settings view: \(section)")
            if let directory = ProcessInfo.processInfo.environment["SORTING_UI_SNAPSHOT_DIR"] {
                let destination = URL(fileURLWithPath: directory)
                try FileManager.default.createDirectory(at: destination, withIntermediateDirectories: true)
                let png = try XCTUnwrap(bitmap.representation(using: .png, properties: [:]))
                try png.write(to: destination.appendingPathComponent("\(section == .admin ? "guide" : "offices").png"))
            }
        }
        state.closeSettingsWithoutSaving()
        XCTAssertFalse(state.isShowingSettings)
        XCTAssertEqual(try Data(contentsOf: rules), original)
    }
}
