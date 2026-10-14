import AppKit
import PDFKit
import SwiftUI
import XCTest
@testable import SortingFilesNativeApp

@MainActor
final class DocumentReviewRenderingTests: XCTestCase {
    func testManualPanelRendersDocumentAndFieldsAtTwoWidthsWithoutChangingRules() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer {
            AppPaths.rulesFileOverride = nil
            try? FileManager.default.removeItem(at: root)
        }
        let rules = root.appendingPathComponent("rules.md")
        try """
        # Правила
        ## 11. Офисы
        ### Офис 98
        Юрлицо:
        - `ООО ТЕСТ`
        Разрешенные категории по умолчанию:
        - `Зарплата`
        Сотрудники:
        - Иванов Иван
        Контрагенты:
        """.write(to: rules, atomically: true, encoding: .utf8)
        AppPaths.rulesFileOverride = rules
        let manual = root.appendingPathComponent("Требует_ручной_проверки")
        try FileManager.default.createDirectory(at: manual, withIntermediateDirectories: true)
        let image = NSImage(size: NSSize(width: 480, height: 640))
        image.lockFocus()
        NSColor.white.setFill()
        NSRect(x: 0, y: 0, width: 480, height: 640).fill()
        ("ПЛАТЕЖНОЕ ПОРУЧЕНИЕ\n\nПолучатель: Иванов Иван\n\nДата: 14.08.2026\n\nСумма: 1000,00" as NSString).draw(
            in: NSRect(x: 30, y: 240, width: 420, height: 330),
            withAttributes: [.font: NSFont.systemFont(ofSize: 18), .foregroundColor: NSColor.black])
        image.unlockFocus()
        let document = PDFDocument()
        document.insert(try XCTUnwrap(PDFPage(image: image)), at: 0)
        let pdf = manual.appendingPathComponent("scan.pdf")
        XCTAssertTrue(document.write(to: pdf))
        let metadata: [String: Any] = ["scan.pdf": ["office": "98", "entity": "ООО ТЕСТ", "category": "Зарплата",
            "reason": "Проверьте реквизиты", "review_fields": ["label": "Иванов Иван", "date": "14-08-2026", "amount": "1000.00"]]]
        try JSONSerialization.data(withJSONObject: metadata).write(to: manual.appendingPathComponent(".manual_review.json"))
        let state = AppState()
        let originalRules = try Data(contentsOf: rules)
        state.runOperation = .sorting
        state.resultArchivePath = root.path
        state.refreshManualReviewItems()
        XCTAssertEqual(state.manualReviewPaymentAmount, "1000.00")
        for width in [1240.0, 1520.0] {
            let view = NSHostingView(rootView: ContentView(state: state).environment(\.colorScheme, .light))
            view.frame = NSRect(x: 0, y: 0, width: width, height: 1200)
            let window = NSWindow(contentRect: view.frame, styleMask: [.titled], backing: .buffered, defer: false)
            window.isReleasedWhenClosed = false
            window.contentView = view
            window.orderFront(nil)
            defer { window.close() }
            view.layoutSubtreeIfNeeded()
            RunLoop.main.run(until: Date().addingTimeInterval(0.5))
            window.displayIfNeeded()
            func pdfViews(in parent: NSView) -> [PDFView] {
                (parent as? PDFView).map { [$0] } ?? parent.subviews.flatMap { pdfViews(in: $0) }
            }
            let preview = try XCTUnwrap(pdfViews(in: view).first)
            XCTAssertEqual(preview.document?.pageCount, 1)
            XCTAssertGreaterThan(preview.scaleFactor, 0)
            if width == 1240, let seconds = ProcessInfo.processInfo.environment["SORTING_UI_REVIEW_PAUSE_SECONDS"].flatMap(Double.init) {
                RunLoop.main.run(until: Date().addingTimeInterval(seconds))
            }
            let bitmap = try XCTUnwrap(view.bitmapImageRepForCachingDisplay(in: view.bounds))
            view.cacheDisplay(in: view.bounds, to: bitmap)
            var colors = Set<String>()
            for y in stride(from: 0, to: bitmap.pixelsHigh, by: 10) {
                for x in stride(from: 0, to: bitmap.pixelsWide, by: 10) {
                    if let color = bitmap.colorAt(x: x, y: y)?.usingColorSpace(.deviceRGB) {
                        colors.insert("\(Int(color.redComponent * 255)),\(Int(color.greenComponent * 255)),\(Int(color.blueComponent * 255))")
                    }
                }
            }
            XCTAssertGreaterThan(colors.count, 20)
            if let directory = ProcessInfo.processInfo.environment["SORTING_UI_SNAPSHOT_DIR"] {
                let output = URL(fileURLWithPath: directory)
                try FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)
                try XCTUnwrap(bitmap.representation(using: .png, properties: [:])).write(to: output.appendingPathComponent("review-\(Int(width)).png"))
            }
        }
        XCTAssertEqual(try Data(contentsOf: rules), originalRules)
    }
}
