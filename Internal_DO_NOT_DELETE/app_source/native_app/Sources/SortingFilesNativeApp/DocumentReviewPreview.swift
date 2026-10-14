import AppKit
import PDFKit
import SwiftUI

struct DocumentReviewPreview: NSViewRepresentable {
    let url: URL

    final class Coordinator {
        var loadedURL: URL?
    }

    func makeCoordinator() -> Coordinator { Coordinator() }

    func makeNSView(context: Context) -> PDFView {
        let view = PDFView()
        view.autoScales = true
        view.displayMode = .singlePageContinuous
        view.backgroundColor = .controlBackgroundColor
        return view
    }

    func updateNSView(_ view: PDFView, context: Context) {
        if context.coordinator.loadedURL == url { return }
        context.coordinator.loadedURL = url
        if url.pathExtension.lowercased() == "pdf" {
            view.document = PDFDocument(url: url)
        } else if let image = NSImage(contentsOf: url), let page = PDFPage(image: image) {
            let document = PDFDocument()
            document.insert(page, at: 0)
            view.document = document
        } else {
            view.document = nil
        }
    }
}
