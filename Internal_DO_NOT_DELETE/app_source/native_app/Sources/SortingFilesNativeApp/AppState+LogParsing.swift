import Foundation

extension AppState {
    func consumeLogChunk(_ chunk: String) {
        if let progress = LogParsing.progressSnapshot(from: chunk) {
            progressValue = progress.value
            progressText = progress.text
        }

        for update in LogParsing.summaryUpdates(from: chunk) {
            switch update {
            case .manualReview(let count):
                manualReviewCount = count
            case .unresolved(let count):
                unresolvedCount = count
            case .archiveRoot(let path):
                resultArchivePath = path
            }
        }

        if let phase = LogParsing.phaseText(from: chunk) {
            currentPhaseText = phase
        }
    }
}
