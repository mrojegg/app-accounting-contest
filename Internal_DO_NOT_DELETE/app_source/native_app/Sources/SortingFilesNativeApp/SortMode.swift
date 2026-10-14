import Foundation

enum SortMode: String, CaseIterable, Identifiable {
    case copy
    case move

    var id: String { rawValue }

    var title: String {
        switch self {
        case .copy: return "Копировать"
        case .move: return "Перемещать"
        }
    }
}
