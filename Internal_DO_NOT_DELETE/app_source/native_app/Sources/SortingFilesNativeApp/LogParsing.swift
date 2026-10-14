import Foundation

struct ProgressSnapshot {
    let value: Double
    let text: String
}

enum SummaryUpdate {
    case manualReview(Int)
    case unresolved(Int)
    case archiveRoot(String)
}

private struct EventPayload: Decodable {
    let type: String
    let archiveRoot: String?
    let unresolved: Int?
    let manualReview: Int?
    let phase: String?

    private enum CodingKeys: String, CodingKey {
        case type
        case archiveRoot = "archive_root"
        case unresolved
        case manualReview = "manual_review"
        case phase
    }
}

enum LogParsing {
    static func limitedTail(appending chunk: String, to existing: String, maxCharacters: Int) -> String {
        guard maxCharacters > 0 else { return "" }

        let combined: String
        if chunk.count >= maxCharacters {
            combined = String(chunk.suffix(maxCharacters))
        } else {
            combined = existing + chunk
        }

        guard combined.count > maxCharacters else { return combined }

        let start = combined.index(combined.endIndex, offsetBy: -maxCharacters)
        var tail = String(combined[start...])
        if let newline = tail.firstIndex(where: \.isNewline), newline != tail.startIndex {
            tail = String(tail[tail.index(after: newline)...])
        }
        return tail
    }

    static func progressSnapshot(from chunk: String) -> ProgressSnapshot? {
        let pattern = #"\[scan\s+(\d+)\/(\d+)\]"#
        guard let regex = try? NSRegularExpression(pattern: pattern) else { return nil }
        let range = NSRange(chunk.startIndex..<chunk.endIndex, in: chunk)
        var snapshot: ProgressSnapshot?

        for match in regex.matches(in: chunk, range: range) {
            guard
                let currentRange = Range(match.range(at: 1), in: chunk),
                let totalRange = Range(match.range(at: 2), in: chunk),
                let current = Double(chunk[currentRange]),
                let total = Double(chunk[totalRange]),
                total > 0
            else { continue }

            let percent = max(0, min(100, (current / total) * 100))
            snapshot = ProgressSnapshot(value: percent, text: String(format: "%.0f%%", percent))
        }

        return snapshot
    }

    static func summaryUpdates(from chunk: String) -> [SummaryUpdate] {
        var updates: [SummaryUpdate] = []

        for line in chunk.split(whereSeparator: \.isNewline) {
            let text = String(line)
            if let event = parseEventPayload(in: text), event.type == "summary" {
                if let count = event.manualReview {
                    updates.append(.manualReview(count))
                }
                if let count = event.unresolved {
                    updates.append(.unresolved(count))
                }
                if let archiveRoot = event.archiveRoot {
                    updates.append(.archiveRoot(archiveRoot))
                }
                continue
            }
            if let (key, value) = parseSummaryMarker(in: text) {
                switch key {
                case "manual_review":
                    if let count = Int(value) {
                        updates.append(.manualReview(count))
                    }
                case "unresolved":
                    if let count = Int(value) {
                        updates.append(.unresolved(count))
                    }
                case "archive_root":
                    updates.append(.archiveRoot(value))
                default:
                    break
                }
                continue
            }

            if let count = parseTrailingNumber(prefix: "Ручная проверка:", in: text) {
                updates.append(.manualReview(count))
            }
            if let count = parseTrailingNumber(prefix: "Не распределено:", in: text) {
                updates.append(.unresolved(count))
            }
            if let value = parseTrailingValue(prefix: "Готово:", in: text) {
                updates.append(.archiveRoot(value))
            } else if let value = parseTrailingValue(prefix: "Итоговый архив:", in: text) {
                updates.append(.archiveRoot(value))
            }
        }

        return updates
    }

    static func phaseText(from chunk: String) -> String? {
        var phase: String?

        for line in chunk.split(whereSeparator: \.isNewline) {
            let text = String(line).trimmingCharacters(in: .whitespacesAndNewlines)
            if let event = parseEventPayload(in: text), event.type == "phase", let phaseKey = event.phase {
                switch phaseKey {
                case "validation":
                    phase = "Проверка окружения"
                case "sorting":
                    phase = "Сканирование и сортировка"
                case "cleanup":
                    phase = "Очистка результата"
                case "postprocess":
                    phase = "Постобработка и Excel"
                case "finished":
                    phase = "Завершено"
                default:
                    break
                }
                continue
            }
            switch text {
            case "[phase] validation":
                phase = "Проверка окружения"
            case "[phase] sorting":
                phase = "Сканирование и сортировка"
            case "[phase] cleanup":
                phase = "Очистка результата"
            case "[phase] postprocess":
                phase = "Постобработка и Excel"
            case "[phase] finished":
                phase = "Завершено"
            default:
                break
            }
        }

        return phase
    }

    private static func parseTrailingNumber(prefix: String, in line: String) -> Int? {
        guard line.hasPrefix(prefix) else { return nil }
        return Int(line.dropFirst(prefix.count).trimmingCharacters(in: .whitespaces))
    }

    private static func parseTrailingValue(prefix: String, in line: String) -> String? {
        guard line.hasPrefix(prefix) else { return nil }
        let value = line.dropFirst(prefix.count).trimmingCharacters(in: .whitespaces)
        return value.isEmpty ? nil : value
    }

    private static func parseSummaryMarker(in line: String) -> (String, String)? {
        let prefix = "[summary] "
        guard line.hasPrefix(prefix) else { return nil }
        let payload = line.dropFirst(prefix.count)
        guard let separator = payload.firstIndex(of: "=") else { return nil }
        let key = String(payload[..<separator]).trimmingCharacters(in: .whitespaces)
        let value = String(payload[payload.index(after: separator)...]).trimmingCharacters(in: .whitespaces)
        guard !key.isEmpty, !value.isEmpty else { return nil }
        return (key, value)
    }

    private static func parseEventPayload(in line: String) -> EventPayload? {
        let prefix = "[event-json] "
        guard line.hasPrefix(prefix) else { return nil }
        let payload = String(line.dropFirst(prefix.count))
        guard let data = payload.data(using: .utf8) else { return nil }
        return try? JSONDecoder().decode(EventPayload.self, from: data)
    }
}
