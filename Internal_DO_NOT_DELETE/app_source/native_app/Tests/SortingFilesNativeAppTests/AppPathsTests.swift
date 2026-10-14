import XCTest
@testable import SortingFilesNativeApp

final class AppPathsTests: XCTestCase {
    func testResolveInternalRootPrefersBundledRuntime() throws {
        let fileManager = FileManager.default
        let tempRoot = fileManager.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        let bundleURL = tempRoot.appendingPathComponent("SortingFilesNativeApp.app", isDirectory: true)
        let resourceURL = bundleURL.appendingPathComponent("Contents/Resources", isDirectory: true)
        let bundledInternalRoot = resourceURL.appendingPathComponent("Internal_DO_NOT_DELETE", isDirectory: true)

        defer { try? fileManager.removeItem(at: tempRoot) }

        try fileManager.createDirectory(at: bundledInternalRoot, withIntermediateDirectories: true)

        let resolved = AppPaths.resolveInternalRoot(
            bundleURL: bundleURL,
            resourceURL: resourceURL,
            fileManager: fileManager
        )

        XCTAssertEqual(resolved, bundledInternalRoot)
    }

    func testResolveBundledOCRBinaryReturnsExpectedPath() throws {
        let fileManager = FileManager.default
        let tempRoot = fileManager.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        let resourceURL = tempRoot.appendingPathComponent("Contents/Resources", isDirectory: true)
        let binaryURL = resourceURL
            .appendingPathComponent("Internal_DO_NOT_DELETE", isDirectory: true)
            .appendingPathComponent("ocr", isDirectory: true)
            .appendingPathComponent("bin", isDirectory: true)
            .appendingPathComponent("pdf_ocr_pkg")

        defer { try? fileManager.removeItem(at: tempRoot) }

        try fileManager.createDirectory(at: binaryURL.deletingLastPathComponent(), withIntermediateDirectories: true)
        try Data("bin".utf8).write(to: binaryURL)

        let resolved = AppPaths.resolveBundledOCRBinary(
            resourceURL: resourceURL,
            fileManager: fileManager
        )

        XCTAssertEqual(resolved, binaryURL)
    }

    func testResolveBundledPDFMergerReturnsExpectedPath() throws {
        let fileManager = FileManager.default
        let tempRoot = fileManager.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
        let resourceURL = tempRoot.appendingPathComponent("Contents/Resources", isDirectory: true)
        let binaryURL = resourceURL
            .appendingPathComponent("Internal_DO_NOT_DELETE", isDirectory: true)
            .appendingPathComponent("pdf", isDirectory: true)
            .appendingPathComponent("bin", isDirectory: true)
            .appendingPathComponent("pdf_merge_helper")

        defer { try? fileManager.removeItem(at: tempRoot) }
        try fileManager.createDirectory(at: binaryURL.deletingLastPathComponent(), withIntermediateDirectories: true)
        try Data("bin".utf8).write(to: binaryURL)

        XCTAssertEqual(
            AppPaths.resolveBundledPDFMerger(resourceURL: resourceURL, fileManager: fileManager),
            binaryURL
        )
    }
}
