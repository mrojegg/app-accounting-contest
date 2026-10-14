import AppKit
import CoreImage
import CoreImage.CIFilterBuiltins
import CoreGraphics
import Foundation
import ImageIO
import PDFKit
import Vision

struct OCRConfig {
    let maxPages: Int
    let scales: [CGFloat]
    let forceOCR: Bool
}

enum ImageVariant: CaseIterable {
    case original
    case grayscale
    case boosted
    case threshold
    case invertedThreshold
}

enum OCRFailure: Error {
    case openFailed
    case renderFailed(Int)
}

let incompletePagePrefix = "__OCR_INCOMPLETE_PAGE__:"

func makeContext(width: Int, height: Int, grayscale: Bool = false) -> CGContext? {
    let colorSpace = grayscale ? CGColorSpaceCreateDeviceGray() : CGColorSpace(name: CGColorSpace.sRGB)
    guard let resolvedColorSpace = colorSpace else { return nil }
    let bitmapInfo = grayscale ? CGImageAlphaInfo.none.rawValue : CGImageAlphaInfo.premultipliedLast.rawValue
    guard let context = CGContext(
        data: nil,
        width: width,
        height: height,
        bitsPerComponent: 8,
        bytesPerRow: 0,
        space: resolvedColorSpace,
        bitmapInfo: bitmapInfo
    ) else {
        return nil
    }
    context.setFillColor(NSColor.white.cgColor)
    context.fill(CGRect(x: 0, y: 0, width: width, height: height))
    return context
}

func renderPDFKitPage(_ page: PDFPage, scale: CGFloat, grayscale: Bool = false) -> CGImage? {
    let box = page.bounds(for: .mediaBox)
    let width = max(Int(box.width * scale), 1)
    let height = max(Int(box.height * scale), 1)
    guard let context = makeContext(width: width, height: height, grayscale: grayscale) else { return nil }
    context.saveGState()
    context.scaleBy(x: scale, y: scale)
    page.draw(with: .mediaBox, to: context)
    context.restoreGState()
    return context.makeImage()
}

func renderCGPDFPage(_ page: CGPDFPage, scale: CGFloat, grayscale: Bool = false) -> CGImage? {
    let box = page.getBoxRect(.mediaBox)
    let width = max(Int(box.width * scale), 1)
    let height = max(Int(box.height * scale), 1)
    guard let context = makeContext(width: width, height: height, grayscale: grayscale) else { return nil }
    context.saveGState()
    context.concatenate(page.getDrawingTransform(.mediaBox, rect: CGRect(x: 0, y: 0, width: width, height: height), rotate: 0, preserveAspectRatio: true))
    context.drawPDFPage(page)
    context.restoreGState()
    return context.makeImage()
}

func normalizedText(_ text: String) -> String {
    text.replacingOccurrences(of: "\r", with: "\n")
        .components(separatedBy: .newlines)
        .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
        .filter { !$0.isEmpty }
        .joined(separator: "\n")
}

func ciImage(from image: CGImage) -> CIImage {
    CIImage(cgImage: image)
}

func renderedCGImage(from ciImage: CIImage) -> CGImage? {
    let context = CIContext(options: nil)
    return context.createCGImage(ciImage, from: ciImage.extent)
}

func cropToContent(_ image: CGImage, tolerance: UInt8 = 245, padding: Int = 24) -> CGImage? {
    guard
        let provider = image.dataProvider,
        let data = provider.data,
        let bytes = CFDataGetBytePtr(data)
    else {
        return nil
    }

    let width = image.width
    let height = image.height
    let bytesPerRow = image.bytesPerRow
    let bitsPerPixel = image.bitsPerPixel
    let componentsPerPixel = max(bitsPerPixel / 8, 1)
    guard componentsPerPixel >= 3 else { return nil }

    var minX = width
    var minY = height
    var maxX = -1
    var maxY = -1

    for y in 0..<height {
        let row = bytes + y * bytesPerRow
        for x in 0..<width {
            let pixel = row + x * componentsPerPixel
            let r = pixel[0]
            let g = pixel[1]
            let b = pixel[2]
            if r < tolerance || g < tolerance || b < tolerance {
                if x < minX { minX = x }
                if y < minY { minY = y }
                if x > maxX { maxX = x }
                if y > maxY { maxY = y }
            }
        }
    }

    guard maxX >= minX, maxY >= minY else { return nil }

    let left = max(minX - padding, 0)
    let top = max(minY - padding, 0)
    let right = min(maxX + padding, width - 1)
    let bottom = min(maxY + padding, height - 1)
    let rect = CGRect(x: left, y: top, width: max(right - left + 1, 1), height: max(bottom - top + 1, 1))
    return image.cropping(to: rect)
}

func segmentedImages(from image: CGImage) -> [[CGImage]] {
    var results: [[CGImage]] = [[image]]
    if let cropped = cropToContent(image) {
        results.append([cropped])
        let width = cropped.width
        let height = cropped.height
        let split = max(height / 2, 1)
        let bandRects = [
            CGRect(x: 0, y: 0, width: width, height: split),
            CGRect(x: 0, y: split, width: width, height: height - split),
        ]
        var bands: [CGImage] = []
        for rect in bandRects {
            let clamped = CGRect(
                x: max(rect.minX, 0),
                y: max(rect.minY, 0),
                width: min(rect.width, CGFloat(width) - max(rect.minX, 0)),
                height: min(rect.height, CGFloat(height) - max(rect.minY, 0))
            )
            if clamped.width > 0, clamped.height > 0, let tile = cropped.cropping(to: clamped) {
                bands.append(tile)
            }
        }
        if bands.count == 2 { results.append(bands) }
    }
    return results
}

func preparedImage(_ image: CGImage, variant: ImageVariant) -> CGImage? {
    let input = ciImage(from: image)
    switch variant {
    case .original:
        return image
    case .grayscale:
        let filter = CIFilter.colorControls()
        filter.inputImage = input
        filter.saturation = 0
        filter.contrast = 1.25
        filter.brightness = 0.02
        guard let output = filter.outputImage else { return nil }
        return renderedCGImage(from: output)
    case .boosted:
        let controls = CIFilter.colorControls()
        controls.inputImage = input
        controls.saturation = 0
        controls.contrast = 1.7
        controls.brightness = 0.06
        guard let boosted = controls.outputImage else { return nil }
        let sharpen = CIFilter.sharpenLuminance()
        sharpen.inputImage = boosted
        sharpen.sharpness = 0.65
        guard let output = sharpen.outputImage else { return nil }
        return renderedCGImage(from: output)
    case .threshold:
        let mono = CIFilter.colorControls()
        mono.inputImage = input
        mono.saturation = 0
        mono.contrast = 2.1
        mono.brightness = 0.08
        guard let monoOutput = mono.outputImage else { return nil }
        let exposure = CIFilter.exposureAdjust()
        exposure.inputImage = monoOutput
        exposure.ev = 0.9
        guard let output = exposure.outputImage else { return nil }
        return renderedCGImage(from: output)
    case .invertedThreshold:
        let mono = CIFilter.colorControls()
        mono.inputImage = input
        mono.saturation = 0
        mono.contrast = 2.3
        mono.brightness = 0.1
        guard let monoOutput = mono.outputImage else { return nil }
        let invert = CIFilter.colorInvert()
        invert.inputImage = monoOutput
        guard let inverted = invert.outputImage else { return nil }
        return renderedCGImage(from: inverted)
    }
}

func textScore(_ text: String) -> Int {
    if text.isEmpty { return -10_000 }
    let normalized = text.lowercased()
    var score = min(text.count, 8000)
    for (token, weight) in [
        ("платежное поручение", 700),
        ("банковский ордер", 700),
        ("получатель", 450),
        ("назначение платежа", 450),
        ("выплата заработной платы", 600),
        ("ндфл", 350),
        ("енп", 350),
        ("единый налоговый платеж", 400),
        ("взносы", 300),
        ("счет", 250),
        ("всего к оплате", 300),
        ("комиссия", 250),
        ("инн", 180),
        ("кпп", 180)
    ] {
        score += max(0, normalized.components(separatedBy: token).count - 1) * weight
    }
    score += text.filter { $0.isLetter || $0.isNumber }.count
    return score
}

func textIsUsable(_ text: String) -> Bool {
    let normalized = text.lowercased()
    guard !text.contains(incompletePagePrefix) else { return false }
    guard text.count >= 60, text.filter({ $0.isLetter }).count >= 25 else { return false }
    let damaged = text.filter { $0 == "\u{FFFD}" || $0 == "\u{0}" }.count
    guard damaged < max(text.count / 100, 1) else { return false }
    if normalized.contains("платежное поручение") || normalized.contains("банковский ордер") ||
        (normalized.contains("получател") && normalized.contains("назначение платеж")) {
        let hasRecipient = normalized.contains("получател") || normalized.contains("40817")
        let hasPurpose = normalized.contains("назначение платеж") || normalized.contains("рез. поле")
        let hasAmount = normalized.range(
            of: #"(?:сумма|руб\w*)[^\n]*\d[,.\-]\d{2}(?:\s|$)"#,
            options: .regularExpression
        ) != nil
        let hasEntity = normalized.range(of: #"\b(?:ооо|ooo|ип|инн)\b|4070281\d+"#, options: .regularExpression) != nil
        return hasRecipient && hasPurpose && hasAmount && hasEntity
    }
    return text.count >= 160
}

func recognizeTextVariants(from image: CGImage) -> String {
    let configs: [(VNRequestTextRecognitionLevel, Bool, Float)] = [
        (.accurate, true, 0),
        (.accurate, false, 0),
    ]
    var best = ""
    var bestScore = -10_000
    var attempts = 0

    let groups = segmentedImages(from: image)
    // Try every region before spending the bounded budget on alternative settings.
    for (level, correction, minHeight) in configs {
        for variant in ImageVariant.allCases {
            for group in groups {
                if attempts + group.count > 20 { return best }
                var chunks: [String] = []
                var confident = true
                for candidate in group {
                    guard let prepared = preparedImage(candidate, variant: variant) else {
                        confident = false
                        continue
                    }
                    attempts += 1
                    let request = VNRecognizeTextRequest()
                    request.recognitionLevel = level
                    request.recognitionLanguages = ["ru-RU", "en-US"]
                    request.usesLanguageCorrection = correction
                    request.minimumTextHeight = minHeight
                    let handler = VNImageRequestHandler(cgImage: prepared, options: [:])
                    do {
                        try handler.perform([request])
                        let observations = request.results ?? []
                        let candidates = observations.compactMap { $0.topCandidates(1).first }
                        chunks.append(candidates.map(\.string).joined(separator: "\n"))
                        confident = confident && !candidates.isEmpty && candidates.allSatisfy({ $0.confidence >= 0.85 })
                    } catch {
                        confident = false
                    }
                }
                // Bands are complementary, so only their combined text can win.
                let text = normalizedText(chunks.joined(separator: "\n"))
                let score = textScore(text)
                if (textIsUsable(text) && !textIsUsable(best)) ||
                    (textIsUsable(text) == textIsUsable(best) && score > bestScore) {
                    bestScore = score
                    best = text
                }
                if textIsUsable(text) && confident { return text }
            }
        }
    }
    return best
}

func loadImage(at url: URL) -> CGImage? {
    guard let source = CGImageSourceCreateWithURL(url as CFURL, nil), CGImageSourceGetCount(source) > 0 else { return nil }
    return CGImageSourceCreateImageAtIndex(source, 0, nil)
}

func extractTextFromImage(url: URL) throws -> String {
    guard let image = loadImage(at: url) else { throw OCRFailure.openFailed }
    return recognizeTextVariants(from: image)
}

func extractPDFTextLayer(url: URL, maxPages: Int) -> String {
    guard let document = PDFDocument(url: url), document.pageCount > 0 else { return "" }
    let pageCount = min(document.pageCount, maxPages)
    var parts: [String] = []
    for index in 0..<pageCount {
        if let page = document.page(at: index), let text = page.string {
            let cleaned = normalizedText(text)
            if !cleaned.isEmpty { parts.append(cleaned) }
        }
    }
    return parts.joined(separator: "\n")
}

func extractWithPDFKit(url: URL, config: OCRConfig) throws -> String {
    guard let document = PDFDocument(url: url), document.pageCount > 0 else { throw OCRFailure.openFailed }
    let pageCount = min(document.pageCount, config.maxPages)
    var chunks: [String] = []

    for index in 0..<pageCount {
        guard let page = document.page(at: index) else { throw OCRFailure.renderFailed(index) }
        let direct = normalizedText(page.string ?? "")
        if textIsUsable(direct) {
            chunks.append(direct)
            continue
        }
        var bestPage = ""
        var bestScore = -10_000
        for scale in config.scales {
            for grayscale in [false] {
                guard let image = renderPDFKitPage(page, scale: scale, grayscale: grayscale) else { continue }
                let text = recognizeTextVariants(from: image)
                let score = textScore(text)
                if score > bestScore {
                    bestScore = score
                    bestPage = text
                }
                if textIsUsable(bestPage) { break }
            }
            if textIsUsable(bestPage) { break }
        }
        chunks.append(textIsUsable(bestPage) ? bestPage : "\(incompletePagePrefix)\(index + 1)\n\(bestPage)")
    }

    return normalizedText(chunks.joined(separator: "\n"))
}

func extractWithCGPDF(url: URL, config: OCRConfig) throws -> String {
    guard let provider = CGDataProvider(url: url as CFURL), let document = CGPDFDocument(provider) else { throw OCRFailure.openFailed }
    let pageCount = min(document.numberOfPages, config.maxPages)
    guard pageCount > 0 else { throw OCRFailure.openFailed }
    var chunks: [String] = []

    for index in 1...pageCount {
        guard let page = document.page(at: index) else { throw OCRFailure.renderFailed(index - 1) }
        var bestPage = ""
        var bestScore = -10_000
        for scale in config.scales {
            for grayscale in [false] {
                guard let image = renderCGPDFPage(page, scale: scale, grayscale: grayscale) else { continue }
                let text = recognizeTextVariants(from: image)
                let score = textScore(text)
                if score > bestScore {
                    bestScore = score
                    bestPage = text
                }
                if textIsUsable(bestPage) { break }
            }
            if textIsUsable(bestPage) { break }
        }
        chunks.append(textIsUsable(bestPage) ? bestPage : "\(incompletePagePrefix)\(index)\n\(bestPage)")
    }

    return normalizedText(chunks.joined(separator: "\n"))
}

func extractText(url: URL, config: OCRConfig) throws -> String {
    if url.pathExtension.lowercased() != "pdf" {
        return try extractTextFromImage(url: url)
    }

    let direct = extractPDFTextLayer(url: url, maxPages: config.maxPages)
    if !config.forceOCR && textIsUsable(direct) { return direct }
    let ocrPDFKit = (try? extractWithPDFKit(url: url, config: config)) ?? ""
    if textIsUsable(ocrPDFKit) { return ocrPDFKit }
    let ocrCG = (try? extractWithCGPDF(url: url, config: config)) ?? ""
    let variants = (config.forceOCR ? [ocrPDFKit, ocrCG] : [direct, ocrPDFKit, ocrCG]).map(normalizedText)
    return variants.max(by: { textScore($0) < textScore($1) }) ?? ""
}

func main() -> Int32 {
    let args = CommandLine.arguments
    guard args.count >= 2 else {
        fputs("usage: pdf_ocr_pkg <pdf-path> [max-pages] [--force-ocr]\n", stderr)
        return 2
    }

    let url = URL(fileURLWithPath: args[1])
    let maxPages = args.count >= 3 ? (Int(args[2]) ?? 4) : 4
    let config = OCRConfig(maxPages: max(1, maxPages), scales: [2.0, 3.0], forceOCR: args.contains("--force-ocr"))

    do {
        let text = try extractText(url: url, config: config)
        let lines = text.components(separatedBy: .newlines)
        let incompletePages = lines.filter { $0.hasPrefix(incompletePagePrefix) }.compactMap {
            Int($0.dropFirst(incompletePagePrefix.count))
        }
        let cleaned = lines.filter { !$0.hasPrefix(incompletePagePrefix) }.joined(separator: "\n")
        if args.contains("--quality-json") {
            let payload: [String: Any] = ["text": cleaned, "incomplete_pages": incompletePages]
            let data = try JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys])
            print(String(decoding: data, as: UTF8.self))
        } else {
            print(cleaned)
        }
        return 0
    } catch {
        fputs("ocr failed: \(error)\n", stderr)
        return 1
    }
}

exit(main())
