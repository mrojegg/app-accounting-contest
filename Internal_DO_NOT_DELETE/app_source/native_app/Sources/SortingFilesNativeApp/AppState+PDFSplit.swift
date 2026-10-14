import Foundation

extension AppState {
    func startPDFSplit() {
        let source = sourcePDFFile.trimmingCharacters(in: .whitespacesAndNewlines)
        let output = outputFolder.trimmingCharacters(in: .whitespacesAndNewlines)

        guard !isRunning else { return }
        guard !source.isEmpty else {
            showError("Выберите PDF файл.")
            return
        }
        guard !output.isEmpty else {
            showError("Выберите папку назначения.")
            return
        }

        let sourceURL = URL(fileURLWithPath: source)
        let outputURL = URL(fileURLWithPath: output)
        guard FileManager.default.fileExists(atPath: sourceURL.path) else {
            showError("PDF не найден:\n\(sourceURL.path)")
            return
        }
        guard pdfSplitIsDirectory(outputURL) else {
            showError("Папка назначения не найдена:\n\(outputURL.path)")
            return
        }

        resetLog("Разбиение PDF:\n\(sourceURL.path)\n-> \(outputURL.path)\n\n")
        statusText = "Идет разбиение PDF..."
        currentPhaseText = "Разбиение PDF"
        isRunning = true
        progressValue = 0
        progressText = "0%"
        manualReviewCount = 0
        unresolvedCount = 0
        resultArchivePath = outputURL.path

        Task.detached { [weak self] in
            do {
                let result = try PDFSplitService.split(
                    inputFile: sourceURL,
                    outputDirectory: outputURL
                ) { completed, total, url in
                    Task { @MainActor in
                        guard let self, self.isRunning else { return }
                        self.progressValue = Double(completed) / Double(max(total, 1)) * 100
                        self.progressText = "\(completed)/\(total)"
                        self.appendLog("[split \(completed)/\(total)] \(url.lastPathComponent)\n")
                    }
                }

                await MainActor.run { [weak self] in
                    guard let self else { return }
                    isRunning = false
                    progressValue = 100
                    progressText = "100%"
                    statusText = "PDF разбит: \(result.files.count) файлов."
                    currentPhaseText = "Готово"
                    appendLog("\nГотово: \(result.files.count) файлов\n")
                }
            } catch {
                await MainActor.run { [weak self] in
                    guard let self else { return }
                    isRunning = false
                    statusText = "Ошибка разбиения PDF."
                    currentPhaseText = "Ошибка"
                    appendLog("\nОшибка: \(error.localizedDescription)\n")
                    showError(error.localizedDescription)
                }
            }
        }
    }

    func startPDFMerge() {
        let source = sourceFolder.trimmingCharacters(in: .whitespacesAndNewlines)
        let shouldRemoveSourceFiles = mode == .move
        let mergeModeTitle = mode.title

        guard !isRunning else { return }
        guard !source.isEmpty else {
            showError("Выберите папку с PDF.")
            return
        }

        let sourceURL = URL(fileURLWithPath: source)
        guard pdfSplitIsDirectory(sourceURL) else {
            showError("Папка с PDF не найдена:\n\(sourceURL.path)")
            return
        }

        resetLog("Объединение PDF:\n\(sourceURL.path)\nРежим: \(mergeModeTitle)\n\n")
        statusText = "Идет объединение PDF..."
        currentPhaseText = "Объединение PDF"
        isRunning = true
        progressValue = 0
        progressText = "0%"
        manualReviewCount = 0
        unresolvedCount = 0
        resultArchivePath = sourceURL.path

        Task.detached { [weak self] in
            do {
                let result = try PDFSplitService.mergePDFs(
                    sourceDirectory: sourceURL,
                    outputDirectory: sourceURL,
                    removeSourceFilesAfterMerge: shouldRemoveSourceFiles
                ) { completed, total, url in
                    Task { @MainActor in
                        guard let self, self.isRunning else { return }
                        self.progressValue = Double(completed) / Double(max(total, 1)) * 100
                        self.progressText = "\(completed)/\(total)"
                        self.appendLog("[merge \(completed)/\(total)] \(url.lastPathComponent)\n")
                    }
                }

                await MainActor.run { [weak self] in
                    guard let self else { return }
                    isRunning = false
                    progressValue = 100
                    progressText = "100%"
                    if shouldRemoveSourceFiles {
                        statusText = "PDF объединен: \(result.sourceFiles.count) файлов, исходные PDF убраны."
                    } else {
                        statusText = "PDF объединен: \(result.sourceFiles.count) файлов, исходные PDF оставлены."
                    }
                    currentPhaseText = "Готово"
                    resultArchivePath = result.file.path
                    appendLog("\nГотово: \(result.file.lastPathComponent)\n")
                    if shouldRemoveSourceFiles {
                        appendLog("Убрано исходных PDF: \(result.removedFiles.count)\n")
                    }
                }
            } catch {
                await MainActor.run { [weak self] in
                    guard let self else { return }
                    isRunning = false
                    statusText = "Ошибка объединения PDF."
                    currentPhaseText = "Ошибка"
                    appendLog("\nОшибка: \(error.localizedDescription)\n")
                    showError(error.localizedDescription)
                }
            }
        }
    }

    private func pdfSplitIsDirectory(_ url: URL) -> Bool {
        var isDirectory: ObjCBool = false
        guard FileManager.default.fileExists(atPath: url.path, isDirectory: &isDirectory) else {
            return false
        }
        return isDirectory.boolValue
    }
}
