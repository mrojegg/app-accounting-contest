import Foundation

struct SalaryExcelFile: Identifiable, Hashable {
    let url: URL

    var id: String { url.path }
    var name: String { url.lastPathComponent }
}

struct SalaryUnknownEmployee: Identifiable, Hashable, Codable {
    let employee: String
    let rows: Int
    let amount: String
    let files: [String]

    var id: String { employee }
}

struct SalaryCreatedFile: Identifiable, Hashable, Codable {
    let office: String
    let file: String
    let rows: Int
    let employees: Int
    let amount: String

    var id: String { file }
    var name: String { URL(fileURLWithPath: file).lastPathComponent }
}

struct SalaryExcelStatePayload: Codable {
    let rows: [SalaryRawRow]
    let unknown: [SalaryUnknownEmployee]
    let ambiguous: [SalaryAmbiguousEmployee]
    let created: [SalaryCreatedFile]?
    let outputDir: String?

    enum CodingKeys: String, CodingKey {
        case rows
        case unknown
        case ambiguous
        case created
        case outputDir = "output_dir"
    }
}

struct SalaryRawRow: Codable {
    let office: String?
}

struct SalaryAmbiguousEmployee: Codable, Hashable {
    let employee: String
    let file: String?
    let offices: [String]?
}
