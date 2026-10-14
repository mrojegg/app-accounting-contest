import Foundation

extension AppState {
    func startSorting() {
        let source = sourceFolder.trimmingCharacters(in: .whitespacesAndNewlines)
        let output = outputFolder.trimmingCharacters(in: .whitespacesAndNewlines)
        let archive = archiveName.trimmingCharacters(in: .whitespacesAndNewlines)

        guard !isRunning else { return }
        guard !source.isEmpty else {
            showError("Выберите исходную папку.")
            return
        }
        guard !output.isEmpty else {
            showError("Выберите папку назначения.")
            return
        }
        guard !archive.isEmpty else {
            showError("Укажите имя итоговой папки.")
            return
        }

        do {
            try enforceRequiredOperationalRules()
            try validateEnvironment(source: source, output: output)
        } catch {
            statusText = "Предпроверка не пройдена."
            appendLog("Ошибка предпроверки: \(error.localizedDescription)\n")
            showError(error.localizedDescription)
            return
        }

        let targetArchive = URL(fileURLWithPath: output).appendingPathComponent(archive)
        if FileManager.default.fileExists(atPath: targetArchive.path) {
            showError("Папка уже существует:\n\(targetArchive.path)")
            return
        }

        let pipeline = AppPaths.pipelineScript
        guard FileManager.default.fileExists(atPath: pipeline.path) else {
            showError("Не найден пайплайн сортировки:\n\(pipeline.path)")
            return
        }

        let command = [
            "/usr/bin/env",
            "python3",
            "-u",
            pipeline.path,
            "--source", source,
            "--output", output,
            "--archive-name", archive,
            "--mode", mode.rawValue,
        ]

        var environment = ProcessInfo.processInfo.environment
        environment["SORTING_RULES_FILE"] = AppPaths.rulesFile.path
        environment["SORTING_TRACE_EXTRACTION"] = "1"
        if let bundledOCRBinary = AppPaths.bundledOCRBinary {
            environment["SORTING_OCR_BINARY"] = bundledOCRBinary.path
        }
        if let bundledPDFMerger = AppPaths.bundledPDFMerger {
            environment["SORTING_PDF_MERGER"] = bundledPDFMerger.path
        }
        startPythonProcess(
            command: command,
            environment: environment,
            startedStatus: "Идет сортировка...",
            completionLine: "Сортировка завершена.",
            targetArchivePath: targetArchive.path,
            resetSummary: true
        )
    }

    func startManualReviewReprocess() {
        let archive = resultArchivePath.trimmingCharacters(in: .whitespacesAndNewlines)

        guard !isRunning else { return }
        if manualPaymentFieldsHaveEdits {
            showError("Сначала сохраните исправленные дату и сумму кнопкой «Применить» в ручной корректировке.")
            return
        }
        guard !archive.isEmpty else {
            showError("Сначала выполните сортировку и дождитесь результата.")
            return
        }

        let archiveURL = URL(fileURLWithPath: archive)
        let manualRoot = archiveURL.appendingPathComponent("Требует_ручной_проверки")
        guard FileManager.default.fileExists(atPath: archiveURL.path) else {
            showError("Не найден итоговый архив:\n\(archiveURL.path)")
            return
        }
        guard FileManager.default.fileExists(atPath: manualRoot.path) else {
            showError("Папка ручной проверки не найдена:\n\(manualRoot.path)")
            return
        }

        do {
            try enforceRequiredOperationalRules()
            try saveCurrentManualReviewRules()
        } catch {
            showError("Не удалось подготовить правила ручной корректировки.\n\(error.localizedDescription)")
            return
        }

        let script = AppPaths.manualReviewReprocessScript
        guard FileManager.default.fileExists(atPath: script.path) else {
            showError("Не найден скрипт дообработки:\n\(script.path)")
            return
        }

        let command = [
            "/usr/bin/env",
            "python3",
            "-u",
            script.path,
            "--archive-root", archiveURL.path,
        ]

        var environment = ProcessInfo.processInfo.environment
        environment["SORTING_RULES_FILE"] = AppPaths.rulesFile.path
        environment["SORTING_TRACE_EXTRACTION"] = "1"
        if let bundledOCRBinary = AppPaths.bundledOCRBinary {
            environment["SORTING_OCR_BINARY"] = bundledOCRBinary.path
        }
        if let bundledPDFMerger = AppPaths.bundledPDFMerger {
            environment["SORTING_PDF_MERGER"] = bundledPDFMerger.path
        }

        startPythonProcess(
            command: command,
            environment: environment,
            startedStatus: "Идет дообработка ручной папки...",
            completionLine: "Дообработка завершена.",
            targetArchivePath: archiveURL.path,
            resetSummary: false
        )
    }

    func stopSorting() {
        guard let runningProcess else { return }
        runningProcess.terminate()
        statusText = "Остановка..."
        currentPhaseText = "Остановка"
        appendLog("\nЗапрошена остановка процесса.\n")
    }

    fileprivate func validateEnvironment(source: String, output: String) throws {
        let sourceURL = URL(fileURLWithPath: source)
        let outputURL = URL(fileURLWithPath: output)
        let fileManager = FileManager.default

        guard fileManager.fileExists(atPath: sourceURL.path) else {
            throw ValidationError("Исходная папка не найдена:\n\(sourceURL.path)")
        }
        guard fileManager.fileExists(atPath: outputURL.path) else {
            throw ValidationError("Папка назначения не найдена:\n\(outputURL.path)")
        }
        guard isDirectory(sourceURL) else {
            throw ValidationError("Исходный путь не является папкой:\n\(sourceURL.path)")
        }
        guard isDirectory(outputURL) else {
            throw ValidationError("Путь назначения не является папкой:\n\(outputURL.path)")
        }
        guard fileManager.fileExists(atPath: AppPaths.rulesFile.path) else {
            throw ValidationError("Не найден файл правил:\n\(AppPaths.rulesFile.path)")
        }
        guard fileManager.fileExists(atPath: AppPaths.pipelineScript.path) else {
            throw ValidationError("Не найден пайплайн сортировки:\n\(AppPaths.pipelineScript.path)")
        }
        guard AppPaths.bundledPython != nil || commandExists("python3") else {
            throw ValidationError("Команда python3 не найдена в системе.")
        }
    }

    private func isDirectory(_ url: URL) -> Bool {
        var isDirectory: ObjCBool = false
        guard FileManager.default.fileExists(atPath: url.path, isDirectory: &isDirectory) else {
            return false
        }
        return isDirectory.boolValue
    }

    private func commandExists(_ name: String) -> Bool {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/which")
        process.arguments = [name]
        process.standardOutput = Pipe()
        process.standardError = Pipe()
        do {
            try process.run()
            process.waitUntilExit()
            return process.terminationStatus == 0
        } catch {
            return false
        }
    }

    func startPythonProcess(
        command: [String],
        environment: [String: String],
        startedStatus: String,
        completionLine: String,
        targetArchivePath: String,
        resetSummary: Bool
    ) {
        resetLog("$ " + command.joined(separator: " ") + "\n")
        statusText = startedStatus
        currentPhaseText = "Подготовка"
        isRunning = true
        progressValue = 0
        progressText = "0%"
        if resetSummary {
            manualReviewCount = 0
            unresolvedCount = 0
        }
        resultArchivePath = targetArchivePath

        let process = Process()
        AppPaths.configurePythonProcess(process, command: command, environment: environment)

        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = pipe

        pipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty, let chunk = String(data: data, encoding: .utf8) else { return }
            Task { @MainActor in
                self?.appendLog(chunk)
                self?.consumeLogChunk(chunk)
            }
        }

        process.terminationHandler = { [weak self] proc in
            pipe.fileHandleForReading.readabilityHandler = nil
            Task { @MainActor in
                self?.isRunning = false
                self?.loadOfficeList()
                self?.loadOfficeRules()
                self?.refreshManualReviewItems()
                if proc.terminationStatus == 0 {
                    self?.statusText = self?.completionStatusText() ?? "Готово."
                    self?.currentPhaseText = "Завершено"
                    self?.progressValue = 100
                    self?.progressText = "100%"
                    self?.appendLog("\n\(completionLine)\n")
                } else {
                    self?.statusText = "Ошибка выполнения."
                    self?.currentPhaseText = "Ошибка"
                    self?.appendLog("\nПроцесс завершился с ошибкой.\n")
                    self?.showError("Процесс завершился с ошибкой. Подробности есть в логе.")
                }
                self?.runningProcess = nil
            }
        }

        do {
            try process.run()
            runningProcess = process
        } catch {
            isRunning = false
            statusText = "Ошибка запуска."
            currentPhaseText = "Ошибка запуска"
            showError("Не удалось запустить процесс.\n\(error.localizedDescription)")
        }
    }
}
