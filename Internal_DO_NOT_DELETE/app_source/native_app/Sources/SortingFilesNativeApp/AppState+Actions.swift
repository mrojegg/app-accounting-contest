import AppKit
import Foundation
import UniformTypeIdentifiers

extension AppState {
    func chooseSourceFolder() {
        guard let url = pickDirectory(title: "Выберите папку с исходными файлами") else { return }
        sourceFolder = url.path
        if archiveName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            archiveName = url.lastPathComponent
        }
    }

    func chooseSourcePDFFile() {
        guard let url = pickPDFFile(title: "Выберите PDF файл для разбиения") else { return }
        sourcePDFFile = url.path
    }

    func chooseSalaryExcelFiles() {
        let panel = NSOpenPanel()
        panel.title = "Выберите зарплатные ведомости Excel"
        panel.canChooseDirectories = false
        panel.canChooseFiles = true
        panel.allowsMultipleSelection = true
        panel.allowedContentTypes = [
            UTType(filenameExtension: "xls"),
            UTType(filenameExtension: "xlsx"),
        ].compactMap { $0 }
        guard panel.runModal() == .OK else { return }
        salaryExcelFiles = panel.urls
            .filter { !$0.lastPathComponent.hasPrefix("~$") }
            .map(SalaryExcelFile.init(url:))
        salaryUnknownEmployees = []
        salaryOfficeAssignments = [:]
        salaryCreatedFiles = []
        salarySummaryText = "\(salaryExcelFiles.count) файлов выбрано."
    }

    func chooseOutputFolder() {
        guard let url = pickDirectory(title: "Выберите папку назначения") else { return }
        outputFolder = url.path
    }

    func fillArchiveNameFromSource() {
        let trimmed = sourceFolder.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        archiveName = URL(fileURLWithPath: trimmed).lastPathComponent
    }

    func clearLog() {
        resetLog()
    }

    func openResultFolder() {
        let trimmed = resultArchivePath.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: trimmed)])
    }

    func openManualReviewReport() {
        guard let reportURL = manualReviewReportURL else { return }
        NSWorkspace.shared.open(reportURL)
    }

    func copyLog() {
        let pasteboard = NSPasteboard.general
        pasteboard.clearContents()
        pasteboard.setString(logText, forType: .string)
        statusText = "Лог скопирован."
    }

    func pickDirectory(title: String) -> URL? {
        let panel = NSOpenPanel()
        panel.title = title
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.allowsMultipleSelection = false
        panel.canCreateDirectories = false
        return panel.runModal() == .OK ? panel.url : nil
    }

    func pickPDFFile(title: String) -> URL? {
        let panel = NSOpenPanel()
        panel.title = title
        panel.canChooseDirectories = false
        panel.canChooseFiles = true
        panel.allowsMultipleSelection = false
        panel.allowedContentTypes = [.pdf]
        return panel.runModal() == .OK ? panel.url : nil
    }

    func showError(_ text: String) {
        errorMessage = text
    }

    func confirmAction(title: String, message: String) -> Bool {
        let alert = NSAlert()
        alert.alertStyle = .warning
        alert.messageText = title
        alert.informativeText = message
        alert.addButton(withTitle: "Удалить")
        alert.addButton(withTitle: "Отмена")
        return alert.runModal() == .alertFirstButtonReturn
    }
}
