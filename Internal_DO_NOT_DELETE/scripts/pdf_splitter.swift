import Foundation
import PDFKit

let args = CommandLine.arguments
if args.count < 3 {
    fputs("usage: pdf_splitter.swift <input.pdf> <output_dir>\n", stderr)
    exit(2)
}

let input = URL(fileURLWithPath: args[1])
let outputDir = URL(fileURLWithPath: args[2], isDirectory: true)
let fm = FileManager.default
try? fm.createDirectory(at: outputDir, withIntermediateDirectories: true)

guard let pdf = PDFDocument(url: input) else {
    fputs("failed to open pdf\n", stderr)
    exit(1)
}

let count = pdf.pageCount
let digits = max(3, String(count).count)
for index in 0..<count {
    guard let page = pdf.page(at: index) else { continue }
    let doc = PDFDocument()
    doc.insert(page, at: 0)
    let name = String(format: "%@_page_%0*d.pdf", input.deletingPathExtension().lastPathComponent, digits, index + 1)
    let out = outputDir.appendingPathComponent(name)
    _ = try? fm.removeItem(at: out)
    if doc.write(to: out) {
        print(out.path)
    }
}
