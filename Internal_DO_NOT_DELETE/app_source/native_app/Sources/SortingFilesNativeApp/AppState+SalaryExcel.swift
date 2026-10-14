import AppKit
import Foundation

extension AppState {
    var salaryAllUnknownAssigned: Bool {
        !salaryUnknownEmployees.isEmpty
            && salaryUnknownEmployees.allSatisfy { !(salaryOfficeAssignments[$0.employee] ?? "").isEmpty }
    }

    func startSalaryExcelAnalyze() {
        guard !isRunning else { return }
        guard !salaryExcelFiles.isEmpty else {
            showError("Выберите Excel-файлы ведомостей.")
            return
        }
        let output = outputFolder.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !output.isEmpty else {
            showError("Выберите папку назначения.")
            return
        }
        guard FileManager.default.fileExists(atPath: output) else {
            showError("Папка назначения не найдена:\n\(output)")
            return
        }
        guard FileManager.default.fileExists(atPath: AppPaths.salaryExcelProcessorScript.path) else {
            showError("Не найден обработчик зарплатных Excel:\n\(AppPaths.salaryExcelProcessorScript.path)")
            return
        }
        do {
            try enforceRequiredOperationalRules()
        } catch {
            showError("Не удалось проверить обязательные правила.\n\(error.localizedDescription)")
            return
        }

        salaryUnknownEmployees = []
        salaryOfficeAssignments = [:]
        salaryCreatedFiles = []
        resultArchivePath = ""
        let stateFile = AppPaths.appSupportDirectory
            .appendingPathComponent("salary_excel", isDirectory: true)
            .appendingPathComponent("state-\(UUID().uuidString).json")
        salaryStateFilePath = stateFile.path

        let command = [
            "/usr/bin/env",
            "python3",
            "-u",
            AppPaths.salaryExcelProcessorScript.path,
            "analyze",
            "--state-file", stateFile.path,
            "--files",
        ] + salaryExcelFiles.map(\.url.path)

        runSalaryCommand(
            command: command,
            startedStatus: "Проверяю зарплатные ведомости...",
            completionLine: "Проверка ведомостей завершена."
        ) { [weak self] success in
            guard let self else { return }
            guard success else { return }
            self.handleSalaryAnalyzeCompletion()
        }
    }

    func startSalaryExcelFinalize() {
        guard !isRunning else { return }
        guard !salaryStateFilePath.isEmpty else {
            showError("Сначала проверьте ведомости.")
            return
        }
        if !salaryUnknownEmployees.isEmpty && !salaryAllUnknownAssigned {
            showError("Выберите офис для всех неизвестных сотрудников.")
            return
        }
        let output = outputFolder.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !output.isEmpty else {
            showError("Выберите папку назначения.")
            return
        }

        do {
            try enforceRequiredOperationalRules()
            try FileManager.default.createDirectory(
                at: AppPaths.appSupportDirectory.appendingPathComponent("salary_excel", isDirectory: true),
                withIntermediateDirectories: true
            )
            let assignmentsFile = AppPaths.appSupportDirectory
                .appendingPathComponent("salary_excel", isDirectory: true)
                .appendingPathComponent("assignments-\(UUID().uuidString).json")
            let data = try JSONSerialization.data(
                withJSONObject: salaryOfficeAssignments,
                options: [.prettyPrinted, .sortedKeys]
            )
            try data.write(to: assignmentsFile)

            let command = [
                "/usr/bin/env",
                "python3",
                "-u",
                AppPaths.salaryExcelProcessorScript.path,
                "finalize",
                "--state-file", salaryStateFilePath,
                "--assignments-file", assignmentsFile.path,
                "--output-dir", output,
            ]
            runSalaryCommand(
                command: command,
                startedStatus: "Создаю таблицы по офисам...",
                completionLine: "Таблицы по офисам созданы."
            ) { [weak self] success in
                guard let self else { return }
                self.handleSalaryFinalizeCompletion(success: success)
            }
        } catch {
            showError("Не удалось подготовить распределение.\n\(error.localizedDescription)")
        }
    }

    func openSalaryCreatedFile(_ file: SalaryCreatedFile) {
        NSWorkspace.shared.open(URL(fileURLWithPath: file.file))
    }

    private func handleSalaryAnalyzeCompletion() {
        do {
            let payload = try loadSalaryPayload()
            guard !payload.rows.isEmpty else {
                showError("В ведомостях не найдены выплаты. Проверьте входные файлы.")
                return
            }
            salaryUnknownEmployees = payload.unknown
            salaryOfficeAssignments = Dictionary(uniqueKeysWithValues: payload.unknown.map { ($0.employee, "") })
            salarySummaryText = "\(payload.rows.count) выплат · неизвестных: \(payload.unknown.count)"
            if payload.unknown.isEmpty {
                appendLog("\nВсе сотрудники найдены в правилах. Начинаю создание таблиц.\n")
                startSalaryExcelFinalize()
            } else {
                statusText = "Выберите офис для новых сотрудников."
                currentPhaseText = "Ожидает выбора"
                progressValue = 50
                progressText = "50%"
            }
        } catch {
            showError("Не удалось прочитать результат проверки.\n\(error.localizedDescription)")
        }
    }

    private func handleSalaryFinalizeCompletion(success: Bool) {
        do {
            let payload = try loadSalaryPayload()
            salaryUnknownEmployees = payload.unknown
            salaryCreatedFiles = payload.created ?? []
            salarySummaryText = "\(payload.rows.count) выплат · файлов создано: \(salaryCreatedFiles.count)"
            if let outputDir = payload.outputDir, !outputDir.isEmpty {
                resultArchivePath = outputDir
            } else if let first = salaryCreatedFiles.first {
                resultArchivePath = URL(fileURLWithPath: first.file).deletingLastPathComponent().path
            }
            if success && !salaryCreatedFiles.isEmpty {
                statusText = "Таблицы по офисам готовы."
                currentPhaseText = "Завершено"
                progressValue = 100
                progressText = "100%"
                loadOfficeList()
                loadOfficeRules()
            } else if success {
                showError("Таблицы не созданы. Проверьте входные ведомости и журнал обработки.")
            }
        } catch {
            if success {
                showError("Таблицы созданы, но не удалось прочитать итоговый отчет.\n\(error.localizedDescription)")
            }
        }
    }

    private func loadSalaryPayload() throws -> SalaryExcelStatePayload {
        let data = try Data(contentsOf: URL(fileURLWithPath: salaryStateFilePath))
        return try JSONDecoder().decode(SalaryExcelStatePayload.self, from: data)
    }

    private func runSalaryCommand(
        command: [String],
        startedStatus: String,
        completionLine: String,
        completion: @escaping (Bool) -> Void
    ) {
        resetLog("$ " + command.joined(separator: " ") + "\n")
        statusText = startedStatus
        currentPhaseText = "Зарплатные Excel"
        isRunning = true
        progressValue = 10
        progressText = "10%"

        var environment = ProcessInfo.processInfo.environment
        environment["SORTING_RULES_FILE"] = AppPaths.rulesFile.path

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
            }
        }

        process.terminationHandler = { [weak self] proc in
            pipe.fileHandleForReading.readabilityHandler = nil
            Task { @MainActor in
                self?.isRunning = false
                let success = proc.terminationStatus == 0
                if success {
                    self?.appendLog("\n\(completionLine)\n")
                    self?.progressValue = 100
                    self?.progressText = "100%"
                } else {
                    self?.statusText = "Ошибка обработки зарплатных Excel."
                    self?.currentPhaseText = "Ошибка"
                    self?.appendLog("\nПроцесс завершился с ошибкой.\n")
                    self?.showError("Процесс завершился с ошибкой. Подробности есть в логе.")
                }
                self?.runningProcess = nil
                completion(success)
            }
        }

        do {
            try process.run()
            runningProcess = process
        } catch {
            isRunning = false
            statusText = "Ошибка запуска."
            currentPhaseText = "Ошибка запуска"
            showError("Не удалось запустить обработку Excel.\n\(error.localizedDescription)")
            completion(false)
        }
    }
}
