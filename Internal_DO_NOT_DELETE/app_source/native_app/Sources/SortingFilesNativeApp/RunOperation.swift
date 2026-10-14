import Foundation

enum RunOperation: String, CaseIterable, Identifiable {
    case sorting = "Сортировка"
    case splitPDF = "Разбить PDF"
    case mergePDF = "Объединить PDF"
    case salaryExcel = "Зарплатные Excel"

    var id: String { rawValue }
    var title: String { rawValue }
}
