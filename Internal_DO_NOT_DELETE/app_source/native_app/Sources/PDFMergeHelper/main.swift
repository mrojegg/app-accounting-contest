import Foundation
import PDFKit

enum MergeError: LocalizedError {
    case invalidArguments
    case sourceNotFound(String)
    case openFailed(String)
    case protectedDocument(String)
    case readPageFailed(String, Int)
    case noPages
    case writeFailed(String)

    var errorDescription: String? {
        switch self {
        case .invalidArguments:
            return "Использование: PDFMergeHelper <результат.pdf> <файл1.pdf> [файл2.pdf ...]"
        case let .sourceNotFound(path):
            return "Не найден исходный PDF: \(path)"
        case let .openFailed(path):
            return "Не удалось открыть PDF: \(path)"
        case let .protectedDocument(path):
            return "PDF защищен паролем или запрещает объединение: \(path)"
        case let .readPageFailed(path, page):
            return "Не удалось прочитать страницу \(page): \(path)"
        case .noPages:
            return "В исходных PDF нет страниц."
        case let .writeFailed(path):
            return "Не удалось записать объединенный PDF: \(path)"
        }
    }
}

func merge(outputURL: URL, inputURLs: [URL]) throws -> Int {
    let fileManager = FileManager.default
    guard !inputURLs.isEmpty else { throw MergeError.invalidArguments }

    let merged = PDFDocument()
    var pageCount = 0
    for inputURL in inputURLs {
        guard fileManager.fileExists(atPath: inputURL.path) else {
            throw MergeError.sourceNotFound(inputURL.path)
        }
        guard let source = PDFDocument(url: inputURL) else {
            throw MergeError.openFailed(inputURL.path)
        }
        guard !source.isLocked, source.allowsCopying, source.allowsDocumentAssembly else {
            throw MergeError.protectedDocument(inputURL.path)
        }
        guard source.pageCount > 0 else { throw MergeError.openFailed(inputURL.path) }
        for pageIndex in 0..<source.pageCount {
            guard let page = source.page(at: pageIndex) else {
                throw MergeError.readPageFailed(inputURL.path, pageIndex + 1)
            }
            merged.insert(page.copy() as? PDFPage ?? page, at: merged.pageCount)
            pageCount += 1
        }
    }
    guard pageCount > 0 else { throw MergeError.noPages }

    try fileManager.createDirectory(
        at: outputURL.deletingLastPathComponent(),
        withIntermediateDirectories: true
    )
    let temporaryURL = outputURL.deletingLastPathComponent()
        .appendingPathComponent(".\(UUID().uuidString).pdf")
    defer { try? fileManager.removeItem(at: temporaryURL) }
    guard merged.write(to: temporaryURL),
          let verified = PDFDocument(url: temporaryURL),
          !verified.isLocked, verified.pageCount == pageCount else {
        throw MergeError.writeFailed(outputURL.path)
    }
    if fileManager.fileExists(atPath: outputURL.path) {
        try fileManager.removeItem(at: outputURL)
    }
    try fileManager.moveItem(at: temporaryURL, to: outputURL)
    return pageCount
}

do {
    let arguments = Array(CommandLine.arguments.dropFirst())
    guard arguments.count >= 2 else { throw MergeError.invalidArguments }
    let outputURL = URL(fileURLWithPath: arguments[0])
    let inputURLs = arguments.dropFirst().map { URL(fileURLWithPath: $0) }
    let pages = try merge(outputURL: outputURL, inputURLs: inputURLs)
    print("files=\(inputURLs.count) pages=\(pages) output=\(outputURL.path)")
} catch {
    fputs("\(error.localizedDescription)\n", stderr)
    exit(1)
}
