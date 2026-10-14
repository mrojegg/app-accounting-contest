import AppKit
import PDFKit
import XCTest
@testable import SortingFilesNativeApp

final class PDFSplitServiceTests: XCTestCase {
    func testSplitCreatesOnePDFPerPage() throws {
        let fileManager = FileManager.default
        let tempRoot = fileManager.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        let inputURL = tempRoot.appendingPathComponent("source.pdf")
        let outputURL = tempRoot.appendingPathComponent("out", isDirectory: true)

        defer { try? fileManager.removeItem(at: tempRoot) }

        try fileManager.createDirectory(at: tempRoot, withIntermediateDirectories: true)
        try makePDF(pageCount: 3, outputURL: inputURL)

        let result = try PDFSplitService.split(inputFile: inputURL, outputDirectory: outputURL)

        XCTAssertEqual(result.files.count, 3)
        XCTAssertEqual(result.files.map(\.lastPathComponent), [
            "source_page_001.pdf",
            "source_page_002.pdf",
            "source_page_003.pdf",
        ])
        XCTAssertTrue(result.files.allSatisfy { fileManager.fileExists(atPath: $0.path) })
    }

    func testSplitKeepsExistingFilesAndAddsSuffix() throws {
        let fileManager = FileManager.default
        let tempRoot = fileManager.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        let inputURL = tempRoot.appendingPathComponent("source.pdf")
        let outputURL = tempRoot.appendingPathComponent("out", isDirectory: true)

        defer { try? fileManager.removeItem(at: tempRoot) }

        try fileManager.createDirectory(at: outputURL, withIntermediateDirectories: true)
        try makePDF(pageCount: 1, outputURL: inputURL)
        try Data("existing".utf8).write(to: outputURL.appendingPathComponent("source_page_001.pdf"))

        let result = try PDFSplitService.split(inputFile: inputURL, outputDirectory: outputURL)

        XCTAssertEqual(result.files.count, 1)
        XCTAssertEqual(result.files.first?.lastPathComponent, "source_page_001_2.pdf")
    }

    func testSplitAllowsCopyingWhenSourceAssemblyIsForbidden() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: root) }
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        let input = root.appendingPathComponent("bank-statement.pdf")
        let document = PDFDocument()
        for index in 0..<3 {
            let image = NSImage(size: NSSize(width: 300, height: 200))
            image.lockFocus()
            NSColor.white.setFill()
            NSBezierPath(rect: NSRect(x: 0, y: 0, width: 300, height: 200)).fill()
            NSString(string: "Payment page \(index + 1)").draw(
                at: NSPoint(x: 24, y: 90),
                withAttributes: [.font: NSFont.systemFont(ofSize: 24), .foregroundColor: NSColor.black]
            )
            image.unlockFocus()
            let page = try XCTUnwrap(PDFPage(image: image))
            page.rotation = index * 90
            document.insert(page, at: index)
        }
        XCTAssertTrue(document.write(to: input, withOptions: [
            .ownerPasswordOption: "owner", .userPasswordOption: "",
            .accessPermissionsOption: NSNumber(value: PDFAccessPermissions.allowsContentCopying.rawValue),
        ]))
        let source = try XCTUnwrap(PDFDocument(url: input))
        XCTAssertFalse(source.isLocked)
        XCTAssertTrue(source.allowsCopying)
        XCTAssertFalse(source.allowsDocumentAssembly)
        let original = try Data(contentsOf: input)

        let result = try PDFSplitService.split(inputFile: input, outputDirectory: root.appendingPathComponent("out"))

        XCTAssertEqual(result.files.count, 3)
        XCTAssertEqual(try Data(contentsOf: input), original)
        for (index, file) in result.files.enumerated() {
            let output = try XCTUnwrap(PDFDocument(url: file))
            XCTAssertEqual(output.pageCount, 1)
            XCTAssertFalse(output.isLocked)
            let expected = try XCTUnwrap(source.page(at: index))
            let actual = try XCTUnwrap(output.page(at: 0))
            XCTAssertEqual(actual.rotation, expected.rotation)
            XCTAssertEqual(actual.bounds(for: .mediaBox), expected.bounds(for: .mediaBox))
            XCTAssertEqual(
                actual.thumbnail(of: NSSize(width: 300, height: 300), for: .mediaBox).tiffRepresentation,
                expected.thumbnail(of: NSSize(width: 300, height: 300), for: .mediaBox).tiffRepresentation
            )
        }
    }

    func testMergePDFsCombinesAllPDFFiles() throws {
        let fileManager = FileManager.default
        let tempRoot = fileManager.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        let sourceURL = tempRoot.appendingPathComponent("archive", isDirectory: true)
        let outputURL = tempRoot.appendingPathComponent("out", isDirectory: true)
        let salaryFolder = sourceURL.appendingPathComponent("84/Зарплата", isDirectory: true)
        let otherFolder = sourceURL.appendingPathComponent("84/Прочее", isDirectory: true)

        defer { try? fileManager.removeItem(at: tempRoot) }

        try fileManager.createDirectory(at: salaryFolder, withIntermediateDirectories: true)
        try fileManager.createDirectory(at: otherFolder, withIntermediateDirectories: true)
        try fileManager.createDirectory(at: outputURL, withIntermediateDirectories: true)
        try makePDF(pageCount: 1, outputURL: salaryFolder.appendingPathComponent("Аванс.pdf"))
        try makePDF(pageCount: 2, outputURL: salaryFolder.appendingPathComponent("Заработная плата.pdf"))
        try makePDF(pageCount: 1, outputURL: otherFolder.appendingPathComponent("Прочее.pdf"))

        let result = try PDFSplitService.mergePDFs(sourceDirectory: sourceURL, outputDirectory: outputURL)

        XCTAssertEqual(result.sourceFiles.count, 3)
        XCTAssertEqual(result.pageCount, 4)
        XCTAssertEqual(result.file.lastPathComponent, "Объединенные_PDF.pdf")
        XCTAssertEqual(PDFDocument(url: result.file)?.pageCount, 4)
    }

    func testMergePDFsUsesSelectedFolderWithGenericNames() throws {
        let fileManager = FileManager.default
        let tempRoot = fileManager.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        let sourceURL = tempRoot.appendingPathComponent("Документы", isDirectory: true)
        let outputURL = tempRoot.appendingPathComponent("out", isDirectory: true)

        defer { try? fileManager.removeItem(at: tempRoot) }

        try fileManager.createDirectory(at: sourceURL, withIntermediateDirectories: true)
        try fileManager.createDirectory(at: outputURL, withIntermediateDirectories: true)
        try makePDF(pageCount: 1, outputURL: sourceURL.appendingPathComponent("Иванов.pdf"))

        let result = try PDFSplitService.mergePDFs(sourceDirectory: sourceURL, outputDirectory: outputURL)

        XCTAssertEqual(result.sourceFiles.count, 1)
        XCTAssertEqual(result.pageCount, 1)
    }

    func testMergePDFsCanRemoveSourceFilesAfterMerge() throws {
        let fileManager = FileManager.default
        let tempRoot = fileManager.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        let sourceURL = tempRoot.appendingPathComponent("Документы", isDirectory: true)
        let firstPDF = sourceURL.appendingPathComponent("one.pdf")
        let secondPDF = sourceURL.appendingPathComponent("two.pdf")

        defer { try? fileManager.removeItem(at: tempRoot) }

        try fileManager.createDirectory(at: sourceURL, withIntermediateDirectories: true)
        try makePDF(pageCount: 1, outputURL: firstPDF)
        try makePDF(pageCount: 1, outputURL: secondPDF)

        let result = try PDFSplitService.mergePDFs(
            sourceDirectory: sourceURL,
            outputDirectory: sourceURL,
            removeSourceFilesAfterMerge: true,
            permanentlyRemoveSourceFilesAfterMerge: true
        )

        XCTAssertEqual(result.sourceFiles.count, 2)
        XCTAssertEqual(result.removedFiles.count, 2)
        XCTAssertTrue(fileManager.fileExists(atPath: result.file.path))
        XCTAssertFalse(fileManager.fileExists(atPath: firstPDF.path))
        XCTAssertFalse(fileManager.fileExists(atPath: secondPDF.path))
        XCTAssertEqual(PDFDocument(url: result.file)?.pageCount, 2)
    }

    func testProtectedInputsCannotProduceBlankMergeOrRemoveSources() throws {
        for password in ["secret", ""] {
            let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
            defer { try? FileManager.default.removeItem(at: root) }
            try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
            let ordinary = root.appendingPathComponent("a.pdf")
            let protected = root.appendingPathComponent("b.pdf")
            try makePDF(pageCount: 1, outputURL: ordinary)
            let document = try XCTUnwrap(PDFDocument(url: ordinary))
            XCTAssertTrue(document.write(to: protected, withOptions: [
                .ownerPasswordOption: "owner", .userPasswordOption: password,
                .accessPermissionsOption: NSNumber(value: 0),
            ]))
            let opened = try XCTUnwrap(PDFDocument(url: protected))
            XCTAssertTrue(opened.isLocked || !opened.allowsDocumentAssembly || !opened.allowsCopying)
            let before = try [Data(contentsOf: ordinary), Data(contentsOf: protected)]
            for removeSources in [false, true] {
                XCTAssertThrowsError(try PDFSplitService.mergePDFs(
                    sourceDirectory: root, outputDirectory: root,
                    removeSourceFilesAfterMerge: removeSources,
                    permanentlyRemoveSourceFilesAfterMerge: true
                )) { error in
                    guard case PDFMergeError.protectedDocument = error else {
                        return XCTFail("Unexpected error: \(error)")
                    }
                }
                XCTAssertEqual(try Data(contentsOf: ordinary), before[0])
                XCTAssertEqual(try Data(contentsOf: protected), before[1])
                XCTAssertEqual(try FileManager.default.contentsOfDirectory(atPath: root.path).count, 2)
            }
            XCTAssertThrowsError(try PDFSplitService.split(
                inputFile: protected, outputDirectory: root.appendingPathComponent("split")
            ))
        }
    }

    @MainActor
    func testThreePageSplitCompletesAtOneHundredPercent() async throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer {
            AppPaths.rulesFileOverride = nil
            try? FileManager.default.removeItem(at: root)
        }
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        let rules = root.appendingPathComponent("rules.md")
        try "### Офис 120\nСотрудники:\n- Тест\n".write(to: rules, atomically: true, encoding: .utf8)
        AppPaths.rulesFileOverride = rules
        let input = root.appendingPathComponent("source.pdf")
        try makePDF(pageCount: 3, outputURL: input)
        let state = AppState()
        state.sourcePDFFile = input.path
        state.outputFolder = root.path
        state.startPDFSplit()
        let deadline = Date().addingTimeInterval(10)
        while state.isRunning && Date() < deadline {
            try await Task.sleep(nanoseconds: 10_000_000)
            XCTAssertTrue((0...100).contains(state.progressValue))
        }
        try await Task.sleep(nanoseconds: 50_000_000)
        XCTAssertFalse(state.isRunning)
        XCTAssertEqual(state.progressValue, 100)
        XCTAssertEqual(state.progressText, "100%")
        XCTAssertEqual(state.currentPhaseText, "Готово")
    }

    @MainActor
    func testMergeCanCompleteAfterProtectedPDFError() async throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer {
            AppPaths.rulesFileOverride = nil
            try? FileManager.default.removeItem(at: root)
        }
        let sources = root.appendingPathComponent("source")
        try FileManager.default.createDirectory(at: sources, withIntermediateDirectories: true)
        let rules = root.appendingPathComponent("rules.md")
        try "### Офис 120\nСотрудники:\n- Тест\n".write(to: rules, atomically: true, encoding: .utf8)
        AppPaths.rulesFileOverride = rules
        let ordinary = sources.appendingPathComponent("ordinary.pdf")
        let locked = sources.appendingPathComponent("locked.pdf")
        try makePDF(pageCount: 2, outputURL: ordinary)
        let document = try XCTUnwrap(PDFDocument(url: ordinary))
        XCTAssertTrue(document.write(to: locked, withOptions: [.ownerPasswordOption: "owner", .userPasswordOption: "secret"]))
        let state = AppState()
        state.sourceFolder = sources.path
        state.startPDFMerge()
        var deadline = Date().addingTimeInterval(10)
        while state.isRunning && Date() < deadline { try await Task.sleep(nanoseconds: 10_000_000) }
        XCTAssertFalse(state.isRunning)
        XCTAssertTrue(state.errorMessage?.contains("защищен") == true)
        XCTAssertEqual(state.currentPhaseText, "Ошибка")
        try FileManager.default.moveItem(at: locked, to: root.appendingPathComponent("locked.pdf"))
        state.errorMessage = nil
        state.startPDFMerge()
        deadline = Date().addingTimeInterval(10)
        while state.isRunning && Date() < deadline { try await Task.sleep(nanoseconds: 10_000_000) }
        XCTAssertFalse(state.isRunning)
        XCTAssertNil(state.errorMessage)
        XCTAssertEqual(state.progressValue, 100)
        XCTAssertEqual(state.currentPhaseText, "Готово")
        XCTAssertEqual(PDFDocument(url: URL(fileURLWithPath: state.resultArchivePath))?.pageCount, 2)
    }

    private func makePDF(pageCount: Int, outputURL: URL) throws {
        let doc = PDFDocument()
        for _ in 0..<pageCount {
            let image = NSImage(size: NSSize(width: 300, height: 300))
            image.lockFocus()
            NSColor.white.setFill()
            NSBezierPath(rect: NSRect(x: 0, y: 0, width: 300, height: 300)).fill()
            image.unlockFocus()
            guard let page = PDFPage(image: image) else {
                XCTFail("Не удалось создать PDFPage")
                return
            }
            doc.insert(page, at: doc.pageCount)
        }
        XCTAssertTrue(doc.write(to: outputURL))
    }
}
