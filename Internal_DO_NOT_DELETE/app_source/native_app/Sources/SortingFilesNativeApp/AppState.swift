import Foundation
import SwiftUI

enum SettingsSection: String, CaseIterable, Identifiable {
    case offices = "Офисы"
    case admin = "Гайд"

    var id: String { rawValue }

    var icon: String {
        switch self {
        case .offices: return "building.2"
        case .admin: return "book.closed"
        }
    }
}

enum ManualReviewType: String, CaseIterable, Identifiable {
    case salary = "Зарплата"
    case counterparty = "Контрагент"
    case commission = "Комиссия"
    case taxes = "Налоги"
    case other = "Прочее"

    var id: String { rawValue }
}

struct ManualReviewItem: Identifiable, Hashable {
    let url: URL

    var id: String { url.path }
    var name: String { url.lastPathComponent }
}

@MainActor
final class AppState: ObservableObject {
    private static let maxLogCharacters = 80_000

    @Published var sourceFolder: String = ""
    @Published var sourcePDFFile: String = ""
    @Published var outputFolder: String
    @Published var archiveName: String = ""
    @Published var runOperation: RunOperation = .sorting
    @Published var mode: SortMode = .copy
    @Published var logText: String = ""
    @Published var statusText: String = "Готово к запуску."
    @Published var errorMessage: String?
    @Published var isRunning: Bool = false
    @Published var progressValue: Double = 0
    @Published var progressText: String = "0%"
    @Published var isShowingSettings: Bool = false
    @Published var selectedSettingsSection: SettingsSection = .offices
    @Published var selectedOffice: String = ""
    @Published var officeItems: [String] = []
    @Published var newOfficeInput: String = ""
    @Published var officeEntityInput: String = ""
    @Published var officeEmployees: [String] = []
    @Published var officeAllowedCategories: [String] = ["Зарплата"]
    @Published var officeContractorRules: [String: [ContractorRuleForm]] = [:]
    @Published var generalPurposeLines: [String] = []
    @Published var generalPrinciples: [String] = []
    @Published var generalArchiveFolders: [String] = []
    @Published var generalFolderOrder: [String] = []
    @Published var generalTableRules: [String] = []
    @Published var salaryTableEnabled: Bool = true
    @Published var salaryTableSplitSameDatePayments: Bool = false
    @Published var salaryTableTotalColumnTitle: String = "Общий итог"
    @Published var salaryTableTotalsRowTitle: String = "ИТОГО"
    @Published var createFoldersOnlyWhenDocumentsExist: Bool = true
    @Published var doNotCreateEmptyFoldersInAdvance: Bool = true
    @Published var createManualReviewFolderOnlyWhenNeeded: Bool = true
    @Published var createSpecialSubfoldersByRoutingRules: Bool = true
    @Published var protectExistingFilesWithUniqueSuffix: Bool = true
    @Published var routeByDocumentTextFirst: Bool = true
    @Published var routeOfficeBeforeCategoryFinalization: Bool = true
    @Published var useContractorsAsCategorySignals: Bool = true
    @Published var unresolvedRouteGoesToManualReview: Bool = true
    @Published var sendLowConfidenceDocumentsToManualReview: Bool = true
    @Published var sendMissingOfficeDocumentsToManualReview: Bool = true
    @Published var preserveReadableNamesInManualReview: Bool = true
    @Published var createManualReviewReport: Bool = true
    @Published var namingUseExtractedText: Bool = true
    @Published var namingFallbackToOriginalWhenNoText: Bool = true
    @Published var namingMakeWindowsSafe: Bool = true
    @Published var namingKeepUniqueSuffixOnConflict: Bool = true
    @Published var commissionsDetectedByPaymentText: Bool = true
    @Published var commissionsUseOfficeEntityRouting: Bool = true
    @Published var commissionsCreateOfficeExcel: Bool = true
    @Published var taxesDetectedByPaymentPhrases: Bool = true
    @Published var taxesUseOfficeEntityRouting: Bool = true
    @Published var taxesCreateTaxAndInsuranceExcel: Bool = true
    @Published var internetPrioritizeKnownProviders: Bool = true
    @Published var internetAllowSpecialProviderSubfolders: Bool = true
    @Published var internetCreateSubfoldersByOfficeContractors: Bool = false
    @Published var internetNormalizeBrokenProviderText: Bool = true
    @Published var generalNamingFormat: String = ""
    @Published var generalLowQualityRules: [String] = []
    @Published var generalExtraHandlers: [String] = []
    @Published var specialRules: [String] = []
    @Published var manualReviewCount: Int = 0
    @Published var unresolvedCount: Int = 0
    @Published var resultArchivePath: String = ""
    @Published var currentPhaseText: String = "Ожидание запуска"
    @Published var manualReviewItems: [ManualReviewItem] = []
    @Published var selectedManualReviewItemID: String = ""
    @Published var manualReviewType: ManualReviewType = .other
    @Published var manualReviewOffice: String = ""
    @Published var manualReviewEntity: String = ""
    @Published var manualReviewCategory: String = "Прочее"
    @Published var manualReviewCounterpartyOrSubfolder: String = ""
    @Published var manualReviewPaymentDate: String = ""
    @Published var manualReviewPaymentAmount: String = ""
    var manualReviewOriginalPaymentDate: String = ""
    var manualReviewOriginalPaymentAmount: String = ""
    @Published var completionReportSummary: String = ""
    @Published var salaryExcelFiles: [SalaryExcelFile] = []
    @Published var salaryUnknownEmployees: [SalaryUnknownEmployee] = []
    @Published var salaryOfficeAssignments: [String: String] = [:]
    @Published var salaryCreatedFiles: [SalaryCreatedFile] = []
    @Published var salaryStateFilePath: String = ""
    @Published var salarySummaryText: String = ""

    var runningProcess: Process?
    var settingsOriginalRulesContent: String?

    func resetLog(_ text: String = "") {
        logText = LogParsing.limitedTail(appending: text, to: "", maxCharacters: Self.maxLogCharacters)
    }

    func appendLog(_ text: String) {
        logText = LogParsing.limitedTail(appending: text, to: logText, maxCharacters: Self.maxLogCharacters)
    }

    init() {
        self.outputFolder = AppPaths.defaultOutputFolder.path
        do {
            try AppPaths.ensureEditableRulesFile()
            try enforceRequiredOperationalRules()
        } catch {
            statusText = "Не удалось подготовить правила."
            resetLog("Ошибка подготовки правил: \(error.localizedDescription)\n")
        }
        loadOfficeList()
        loadSpecialRules()
    }

    var manualReviewReportURL: URL? {
        guard manualReviewCount > 0, !resultArchivePath.isEmpty else { return nil }
        let reportURL = URL(fileURLWithPath: resultArchivePath)
            .appendingPathComponent("Требует_ручной_проверки")
            .appendingPathComponent("_report.txt")
        return FileManager.default.fileExists(atPath: reportURL.path) ? reportURL : nil
    }

    func completionStatusText() -> String {
        var parts = ["Готово"]
        if unresolvedCount > 0 {
            parts.append("не распределено: \(unresolvedCount)")
        }
        if manualReviewCount > 0 {
            parts.append("ручная проверка: \(manualReviewCount)")
        }
        return parts.joined(separator: " · ")
    }
}
