import Foundation

enum ManualDecisionKind: String, CaseIterable, Identifiable {
    case salary = "Зарплата"
    case contractor = "Контрагент"
    case commission = "Комиссия"
    case taxes = "Налоги/Взносы"
    case other = "Прочее"

    var id: String { rawValue }
    var scriptValue: String {
        switch self {
        case .salary: return "salary"
        case .contractor: return "contractor"
        case .commission: return "commission"
        case .taxes: return "taxes"
        case .other: return "other"
        }
    }
}

struct ManualReviewEntry: Identifiable, Equatable {
    let fileName: String
    let fileURL: URL
    var suggestedOffice: String
    var suggestedCategory: String
    var suggestedEntity: String
    var reason: String

    var id: String { fileName }
}

enum ManualReviewParsing {
    static func parseEntries(reportURL: URL?, folderURL: URL?) -> [ManualReviewEntry] {
        guard let folderURL else { return [] }
        let reportEntries = parseReport(reportURL)
        let fileManager = FileManager.default
        let files = (try? fileManager.contentsOfDirectory(at: folderURL, includingPropertiesForKeys: nil)) ?? []
        return files
            .filter { $0.lastPathComponent != "_report.txt" }
            .filter { !$0.hasDirectoryPath }
            .map { url in
                let key = url.lastPathComponent
                let report = reportEntries[key]
                return ManualReviewEntry(
                    fileName: key,
                    fileURL: url,
                    suggestedOffice: report?.office ?? "",
                    suggestedCategory: report?.category ?? "",
                    suggestedEntity: report?.entity ?? "",
                    reason: report?.reason ?? "Ожидает ручного решения."
                )
            }
            .sorted { $0.fileName.localizedCaseInsensitiveCompare($1.fileName) == .orderedAscending }
    }

    private static func parseReport(_ reportURL: URL?) -> [String: (office: String, category: String, entity: String, reason: String)] {
        guard
            let reportURL,
            let text = try? String(contentsOf: reportURL, encoding: .utf8)
        else { return [:] }

        let blocks = text.components(separatedBy: "\n\n")
        var result: [String: (office: String, category: String, entity: String, reason: String)] = [:]
        for block in blocks {
            let lines = block.split(separator: "\n").map(String.init)
            guard let fileLine = lines.first(where: { $0.hasPrefix("Файл: ") }) else { continue }
            let fileName = String(fileLine.dropFirst("Файл: ".count))
            let office = extractValue(prefix: "Офис: ", lines: lines)
            let category = extractValue(prefix: "Категория: ", lines: lines)
            let entity = extractValue(prefix: "Юрлицо: ", lines: lines)
            let reason = extractValue(prefix: "Причина: ", lines: lines)
            result[fileName] = (
                office == "?" ? "" : office,
                category == "?" ? "" : category,
                entity == "?" ? "" : entity,
                reason
            )
        }
        return result
    }

    private static func extractValue(prefix: String, lines: [String]) -> String {
        guard let line = lines.first(where: { $0.hasPrefix(prefix) }) else { return "" }
        return String(line.dropFirst(prefix.count))
    }
}
