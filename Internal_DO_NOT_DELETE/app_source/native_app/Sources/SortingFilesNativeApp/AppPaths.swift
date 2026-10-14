import Foundation

enum AppPaths {
    static var rulesFileOverride: URL?

    static var defaultOutputFolder: URL {
        FileManager.default.homeDirectoryForCurrentUser
    }

    static var projectRoot: URL {
        Bundle.main.bundleURL
            .deletingLastPathComponent()
            .deletingLastPathComponent()
    }

    static var internalRoot: URL {
        resolveInternalRoot(
            bundleURL: Bundle.main.bundleURL,
            resourceURL: Bundle.main.resourceURL,
            fileManager: .default
        )
    }

    static var pipelineScript: URL {
        internalRoot
            .appendingPathComponent("scripts")
            .appendingPathComponent("run_sorting_pipeline.py")
    }

    static var bundledPython: URL? {
        let url = internalRoot.appendingPathComponent("python-runtime/bin/python3")
        return FileManager.default.isExecutableFile(atPath: url.path) ? url : nil
    }

    static func configurePythonProcess(_ process: Process, command: [String], environment: [String: String]) {
        var environment = environment
        if let python = bundledPython {
            process.executableURL = python
            process.arguments = ["-B", "-E", "-s"] + Array(command.dropFirst(2))
            environment.removeValue(forKey: "PYTHONHOME")
            environment.removeValue(forKey: "PYTHONPATH")
        } else {
            process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
            process.arguments = Array(command.dropFirst())
        }
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        process.environment = environment
    }

    static var manualReviewReprocessScript: URL {
        internalRoot
            .appendingPathComponent("scripts")
            .appendingPathComponent("reprocess_manual_review.py")
    }

    static var salaryExcelProcessorScript: URL {
        internalRoot
            .appendingPathComponent("scripts")
            .appendingPathComponent("salary_excel_processor.py")
    }

    static var applyManualDecisionScript: URL {
        internalRoot
            .appendingPathComponent("scripts")
            .appendingPathComponent("apply_manual_decision.py")
    }

    static var finalizeArchiveScript: URL {
        internalRoot
            .appendingPathComponent("scripts")
            .appendingPathComponent("finalize_archive_postprocess.py")
    }

    static var bundledOCRBinary: URL? {
        resolveBundledOCRBinary(
            resourceURL: Bundle.main.resourceURL,
            fileManager: .default
        )
    }

    static var bundledPDFMerger: URL? {
        resolveBundledPDFMerger(
            resourceURL: Bundle.main.resourceURL,
            fileManager: .default
        )
    }

    static var appSupportDirectory: URL {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support")
        return base.appendingPathComponent("SortingFilesContestApp", isDirectory: true)
    }

    static var rulesFile: URL {
        rulesFileOverride ?? appSupportDirectory.appendingPathComponent("sorting_rules.md")
    }

    static var bundledDefaultRulesFile: URL? {
        Bundle.main.url(forResource: "default_sorting_rules", withExtension: "md")
    }

    static var legacyRulesFile: URL {
        internalRoot
            .appendingPathComponent("project_rules")
            .appendingPathComponent("sorting_rules.md")
    }

    static func resolveInternalRoot(
        bundleURL: URL,
        resourceURL: URL?,
        fileManager: FileManager
    ) -> URL {
        if let resourceURL {
            let bundled = resourceURL.appendingPathComponent("Internal_DO_NOT_DELETE", isDirectory: true)
            if fileManager.fileExists(atPath: bundled.path) {
                return bundled
            }
        }
        return bundleURL
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .appendingPathComponent("Internal_DO_NOT_DELETE", isDirectory: true)
    }

    static func resolveBundledOCRBinary(
        resourceURL: URL?,
        fileManager: FileManager
    ) -> URL? {
        guard let resourceURL else { return nil }
        let candidate = resourceURL
            .appendingPathComponent("Internal_DO_NOT_DELETE", isDirectory: true)
            .appendingPathComponent("ocr", isDirectory: true)
            .appendingPathComponent("bin", isDirectory: true)
            .appendingPathComponent("pdf_ocr_pkg")
        return fileManager.fileExists(atPath: candidate.path) ? candidate : nil
    }

    static func resolveBundledPDFMerger(
        resourceURL: URL?,
        fileManager: FileManager
    ) -> URL? {
        guard let resourceURL else { return nil }
        let candidate = resourceURL
            .appendingPathComponent("Internal_DO_NOT_DELETE", isDirectory: true)
            .appendingPathComponent("pdf", isDirectory: true)
            .appendingPathComponent("bin", isDirectory: true)
            .appendingPathComponent("pdf_merge_helper")
        return fileManager.fileExists(atPath: candidate.path) ? candidate : nil
    }

    static func ensureEditableRulesFile() throws {
        try ensureEditableRulesFile(
            fileManager: .default,
            rulesFile: rulesFile,
            bundledDefaultRulesFile: bundledDefaultRulesFile,
            legacyRulesFile: legacyRulesFile
        )
    }

    static func ensureEditableRulesFile(
        fileManager: FileManager,
        rulesFile: URL,
        bundledDefaultRulesFile: URL?,
        legacyRulesFile: URL
    ) throws {
        try fileManager.createDirectory(
            at: rulesFile.deletingLastPathComponent(),
            withIntermediateDirectories: true,
            attributes: nil
        )
        guard !fileManager.fileExists(atPath: rulesFile.path) else { return }

        if let bundledDefaultRulesFile, fileManager.fileExists(atPath: bundledDefaultRulesFile.path) {
            try fileManager.copyItem(at: bundledDefaultRulesFile, to: rulesFile)
            return
        }

        if fileManager.fileExists(atPath: legacyRulesFile.path) {
            try fileManager.copyItem(at: legacyRulesFile, to: rulesFile)
            return
        }

        try "# Правила сортировки\n".write(to: rulesFile, atomically: true, encoding: .utf8)
    }
}
