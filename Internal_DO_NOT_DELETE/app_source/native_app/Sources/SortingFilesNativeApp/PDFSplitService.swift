import Foundation
import PDFKit

struct PDFSplitResult {
    let files: [URL]
}

struct PDFMergeResult {
    let file: URL
    let sourceFiles: [URL]
    let removedFiles: [URL]
    let pageCount: Int
}

enum PDFSplitService {
    static func split(
        inputFile: URL,
        outputDirectory: URL,
        progress: ((Int, Int, URL) -> Void)? = nil
    ) throws -> PDFSplitResult {
        let fileManager = FileManager.default
        guard fileManager.fileExists(atPath: inputFile.path) else {
            throw PDFSplitError.fileNotFound(inputFile.path)
        }

        try fileManager.createDirectory(at: outputDirectory, withIntermediateDirectories: true, attributes: nil)

        guard let pdf = PDFDocument(url: inputFile) else {
            throw PDFSplitError.openFailed(inputFile.path)
        }
        // Exporting page copies does not require changing the source document's assembly.
        guard !pdf.isLocked, pdf.allowsCopying else {
            throw PDFSplitError.protectedDocument(inputFile.path)
        }

        let pageCount = pdf.pageCount
        guard pageCount > 0 else {
            throw PDFSplitError.noPages
        }

        let digits = max(3, String(pageCount).count)
        let baseName = inputFile.deletingPathExtension().lastPathComponent
        var files: [URL] = []

        for index in 0..<pageCount {
            guard let page = pdf.page(at: index) else {
                throw PDFSplitError.readPageFailed(index + 1)
            }

            let singlePagePDF = PDFDocument()
            singlePagePDF.insert(page, at: 0)

            let fileName = String(format: "%@_page_%0*d.pdf", baseName, digits, index + 1)
            let targetURL = uniqueOutputURL(
                in: outputDirectory,
                preferredName: fileName,
                fileManager: fileManager
            )

            guard singlePagePDF.write(to: targetURL) else {
                throw PDFSplitError.writeFailed(targetURL.path)
            }

            files.append(targetURL)
            progress?(index + 1, pageCount, targetURL)
        }

        return PDFSplitResult(files: files)
    }

    static func mergePDFs(
        sourceDirectory: URL,
        outputDirectory: URL,
        removeSourceFilesAfterMerge: Bool = false,
        permanentlyRemoveSourceFilesAfterMerge: Bool = false,
        progress: ((Int, Int, URL) -> Void)? = nil
    ) throws -> PDFMergeResult {
        let fileManager = FileManager.default
        guard isDirectory(sourceDirectory, fileManager: fileManager) else {
            throw PDFMergeError.sourceFolderNotFound(sourceDirectory.path)
        }
        guard isDirectory(outputDirectory, fileManager: fileManager) else {
            throw PDFMergeError.outputFolderNotFound(outputDirectory.path)
        }

        let pdfFiles = try collectPDFs(in: sourceDirectory, fileManager: fileManager)
        guard !pdfFiles.isEmpty else {
            throw PDFMergeError.noPDFs(sourceDirectory.path)
        }

        let mergedPDF = PDFDocument()
        var pageCount = 0

        for (index, fileURL) in pdfFiles.enumerated() {
            guard let sourcePDF = PDFDocument(url: fileURL) else {
                throw PDFMergeError.openFailed(fileURL.path)
            }
            guard !sourcePDF.isLocked, sourcePDF.allowsCopying, sourcePDF.allowsDocumentAssembly else {
                throw PDFMergeError.protectedDocument(fileURL.path)
            }
            guard sourcePDF.pageCount > 0 else {
                throw PDFMergeError.openFailed(fileURL.path)
            }

            for pageIndex in 0..<sourcePDF.pageCount {
                guard let page = sourcePDF.page(at: pageIndex) else {
                    throw PDFMergeError.readPageFailed(fileURL.path, pageIndex + 1)
                }
                let copiedPage = page.copy() as? PDFPage ?? page
                mergedPDF.insert(copiedPage, at: mergedPDF.pageCount)
                pageCount += 1
            }

            progress?(index + 1, pdfFiles.count, fileURL)
        }

        guard pageCount > 0 else {
            throw PDFMergeError.noPages
        }

        let targetURL = uniqueOutputURL(
            in: outputDirectory,
            preferredName: "Объединенные_PDF.pdf",
            fileManager: fileManager
        )

        let temporaryURL = outputDirectory.appendingPathComponent(".\(UUID().uuidString).pdf")
        defer { try? fileManager.removeItem(at: temporaryURL) }
        guard mergedPDF.write(to: temporaryURL),
              let verified = PDFDocument(url: temporaryURL),
              !verified.isLocked, verified.pageCount == pageCount else {
            throw PDFMergeError.writeFailed(targetURL.path)
        }
        try fileManager.moveItem(at: temporaryURL, to: targetURL)

        var removedFiles: [URL] = []
        if removeSourceFilesAfterMerge {
            for fileURL in pdfFiles where fileURL.standardizedFileURL != targetURL.standardizedFileURL {
                try removeOriginalPDF(
                    fileURL,
                    permanently: permanentlyRemoveSourceFilesAfterMerge,
                    fileManager: fileManager
                )
                removedFiles.append(fileURL)
            }
        }

        return PDFMergeResult(file: targetURL, sourceFiles: pdfFiles, removedFiles: removedFiles, pageCount: pageCount)
    }

    private static func uniqueOutputURL(
        in directory: URL,
        preferredName: String,
        fileManager: FileManager
    ) -> URL {
        let preferredURL = directory.appendingPathComponent(preferredName)
        guard fileManager.fileExists(atPath: preferredURL.path) else {
            return preferredURL
        }

        let ext = preferredURL.pathExtension
        let stem = preferredURL.deletingPathExtension().lastPathComponent
        var counter = 2

        while true {
            let candidateName = ext.isEmpty ? "\(stem)_\(counter)" : "\(stem)_\(counter).\(ext)"
            let candidateURL = directory.appendingPathComponent(candidateName)
            if !fileManager.fileExists(atPath: candidateURL.path) {
                return candidateURL
            }
            counter += 1
        }
    }

    private static func collectPDFs(
        in sourceDirectory: URL,
        fileManager: FileManager
    ) throws -> [URL] {
        let keys: [URLResourceKey] = [.isRegularFileKey]
        guard let enumerator = fileManager.enumerator(
            at: sourceDirectory,
            includingPropertiesForKeys: keys,
            options: [.skipsHiddenFiles, .skipsPackageDescendants]
        ) else {
            throw PDFMergeError.sourceFolderNotFound(sourceDirectory.path)
        }

        var files: [URL] = []
        for case let fileURL as URL in enumerator {
            let values = try? fileURL.resourceValues(forKeys: Set(keys))
            guard values?.isRegularFile == true else { continue }
            guard fileURL.pathExtension.caseInsensitiveCompare("pdf") == .orderedSame else { continue }
            guard !isGeneratedMergeOutput(fileURL) else { continue }
            files.append(fileURL)
        }

        return files.sorted { lhs, rhs in
            lhs.path.localizedStandardCompare(rhs.path) == .orderedAscending
        }
    }

    private static func isGeneratedMergeOutput(_ fileURL: URL) -> Bool {
        let stem = fileURL
            .deletingPathExtension()
            .lastPathComponent
        return stem.hasPrefix("Объединенные_PDF")
            || stem.hasPrefix("Зарплатные_PDF_объединенные")
    }

    private static func isDirectory(_ url: URL, fileManager: FileManager) -> Bool {
        var isDirectory: ObjCBool = false
        guard fileManager.fileExists(atPath: url.path, isDirectory: &isDirectory) else {
            return false
        }
        return isDirectory.boolValue
    }

    private static func removeOriginalPDF(
        _ fileURL: URL,
        permanently: Bool,
        fileManager: FileManager
    ) throws {
        if permanently {
            do {
                try fileManager.removeItem(at: fileURL)
                return
            } catch {
                throw PDFMergeError.removeSourceFailed(fileURL.path, error.localizedDescription)
            }
        }
        do {
            try fileManager.trashItem(at: fileURL, resultingItemURL: nil)
        } catch {
            do {
                try fileManager.removeItem(at: fileURL)
            } catch {
                throw PDFMergeError.removeSourceFailed(fileURL.path, error.localizedDescription)
            }
        }
    }
}

enum PDFSplitError: LocalizedError {
    case fileNotFound(String)
    case openFailed(String)
    case protectedDocument(String)
    case noPages
    case readPageFailed(Int)
    case writeFailed(String)

    var errorDescription: String? {
        switch self {
        case .fileNotFound(let path):
            return "PDF не найден:\n\(path)"
        case .openFailed(let path):
            return "Не удалось открыть PDF:\n\(path)"
        case .protectedDocument(let path):
            return "PDF защищен паролем или запрещает извлечение страниц. Исходный файл сохранен:\n\(path)"
        case .noPages:
            return "В PDF нет страниц."
        case .readPageFailed(let page):
            return "Не удалось прочитать страницу \(page)."
        case .writeFailed(let path):
            return "Не удалось записать файл:\n\(path)"
        }
    }
}

enum PDFMergeError: LocalizedError {
    case sourceFolderNotFound(String)
    case outputFolderNotFound(String)
    case noPDFs(String)
    case openFailed(String)
    case protectedDocument(String)
    case readPageFailed(String, Int)
    case noPages
    case writeFailed(String)
    case removeSourceFailed(String, String)

    var errorDescription: String? {
        switch self {
        case .sourceFolderNotFound(let path):
            return "Папка с PDF не найдена:\n\(path)"
        case .outputFolderNotFound(let path):
            return "Папка назначения не найдена:\n\(path)"
        case .noPDFs(let path):
            return "В папке не найдены PDF:\n\(path)"
        case .openFailed(let path):
            return "Не удалось открыть PDF:\n\(path)"
        case .protectedDocument(let path):
            return "PDF защищен паролем или запрещает объединение. Исходные файлы сохранены:\n\(path)"
        case .readPageFailed(let path, let page):
            return "Не удалось прочитать страницу \(page):\n\(path)"
        case .noPages:
            return "В выбранных PDF нет страниц."
        case .writeFailed(let path):
            return "Не удалось записать объединенный PDF:\n\(path)"
        case .removeSourceFailed(let path, let reason):
            return "Не удалось убрать исходный PDF:\n\(path)\n\(reason)"
        }
    }
}
