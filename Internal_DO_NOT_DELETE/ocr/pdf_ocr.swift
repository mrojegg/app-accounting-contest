import AppKit
import CoreGraphics
import Foundation
import PDFKit
import UniformTypeIdentifiers
import Vision

struct OCRConfig {
    let maxPages: Int
    let scale: CGFloat
}

enum OCRFailure: Error {
    case openFailed
    case renderFailed(Int)
}

func makeContext(width: Int, height: Int) -> CGContext? {
    guard let colorSpace = CGColorSpace(name: CGColorSpace.sRGB) else {
        return nil
    }

    guard let context = CGContext(
        data: nil,
        width: width,
        height: height,
        bitsPerComponent: 8,
        bytesPerRow: 0,
        space: colorSpace,
        bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
    ) else {
        return nil
    }

    context.setFillColor(NSColor.white.cgColor)
    context.fill(CGRect(x: 0, y: 0, width: width, height: height))
    return context
}

func renderPDFKitPage(_ page: PDFPage, scale: CGFloat) -> CGImage? {
    let box = page.bounds(for: .mediaBox)
    let width = max(Int(box.width * scale), 1)
    let height = max(Int(box.height * scale), 1)

    guard let context = makeContext(width: width, height: height) else {
        return nil
    }

    context.saveGState()
    context.translateBy(x: 0, y: CGFloat(height))
    context.scaleBy(x: scale, y: -scale)
    page.draw(with: .mediaBox, to: context)
    context.restoreGState()
    return context.makeImage()
}

func renderCGPDFPage(_ page: CGPDFPage, scale: CGFloat) -> CGImage? {
    let box = page.getBoxRect(.mediaBox)
    let width = max(Int(box.width * scale), 1)
    let height = max(Int(box.height * scale), 1)

    guard let context = makeContext(width: width, height: height) else {
        return nil
    }

    context.saveGState()
    context.translateBy(x: 0, y: CGFloat(height))
    context.scaleBy(x: scale, y: -scale)
    context.scaleBy(x: scale, y: scale)
    context.drawPDFPage(page)
    context.restoreGState()
    return context.makeImage()
}

func recognizeText(from image: CGImage) throws -> String {
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.recognitionLanguages = ["ru-RU", "en-US"]
    request.usesLanguageCorrection = true

    let handler = VNImageRequestHandler(cgImage: image, options: [:])
    try handler.perform([request])

    let observations = request.results ?? []
    return observations.compactMap { $0.topCandidates(1).first?.string }.joined(separator: "\n")
}

func extractWithPDFKit(url: URL, config: OCRConfig) throws -> String {
    guard let document = PDFDocument(url: url), document.pageCount > 0 else {
        throw OCRFailure.openFailed
    }

    let pageCount = min(document.pageCount, config.maxPages)
    var chunks: [String] = []
    chunks.reserveCapacity(pageCount)

    for index in 0..<pageCount {
        guard let page = document.page(at: index), let image = renderPDFKitPage(page, scale: config.scale) else {
            throw OCRFailure.renderFailed(index)
        }
        let text = try recognizeText(from: image)
        chunks.append(text)
    }

    return chunks.joined(separator: "\n")
}

func extractWithCGPDF(url: URL, config: OCRConfig) throws -> String {
    guard
        let provider = CGDataProvider(url: url as CFURL),
        let document = CGPDFDocument(provider)
    else {
        throw OCRFailure.openFailed
    }

    let pageCount = min(document.numberOfPages, config.maxPages)
    guard pageCount > 0 else {
        throw OCRFailure.openFailed
    }

    var chunks: [String] = []
    chunks.reserveCapacity(pageCount)

    for index in 1...pageCount {
        guard let page = document.page(at: index), let image = renderCGPDFPage(page, scale: config.scale) else {
            throw OCRFailure.renderFailed(index - 1)
        }
        let text = try recognizeText(from: image)
        chunks.append(text)
    }

    return chunks.joined(separator: "\n")
}

func extractText(url: URL, config: OCRConfig) throws -> String {
    if let text = try? extractWithPDFKit(url: url, config: config), !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
        return text
    }
    return try extractWithCGPDF(url: url, config: config)
}

func main() -> Int32 {
    let args = CommandLine.arguments
    guard args.count >= 2 else {
        fputs("usage: pdf_ocr.swift <pdf-path> [max-pages]\n", stderr)
        return 2
    }

    let url = URL(fileURLWithPath: args[1])
    let maxPages = args.count >= 3 ? (Int(args[2]) ?? 2) : 2
    let config = OCRConfig(maxPages: max(1, maxPages), scale: 2.0)

    do {
        let text = try extractText(url: url, config: config)
        print(text)
        return 0
    } catch {
        fputs("ocr failed: \(error)\n", stderr)
        return 1
    }
}

exit(main())
