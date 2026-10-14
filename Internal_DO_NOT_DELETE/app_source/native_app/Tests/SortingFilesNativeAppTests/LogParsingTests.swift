import XCTest
@testable import SortingFilesNativeApp

final class LogParsingTests: XCTestCase {
    func testLimitedTailKeepsRecentContentWithinLimit() throws {
        let tail = LogParsing.limitedTail(
            appending: "line-1\nline-2\nline-3\n",
            to: "old\n",
            maxCharacters: 14
        )

        XCTAssertLessThanOrEqual(tail.count, 14)
        XCTAssertFalse(tail.contains("old"))
        XCTAssertTrue(tail.hasSuffix("line-3\n"))
    }

    func testLimitedTailTrimsHugeSingleChunk() throws {
        let tail = LogParsing.limitedTail(
            appending: String(repeating: "x", count: 20),
            to: "old\n",
            maxCharacters: 8
        )

        XCTAssertEqual(tail, "xxxxxxxx")
    }

    func testSummaryUpdatesReadManualReviewFromEventJson() throws {
        let chunk = """
        [event-json] {"type":"summary","archive_root":"/tmp/archive","manual_review":3,"unresolved":1}
        """

        let updates = LogParsing.summaryUpdates(from: chunk)

        XCTAssertEqual(updates.count, 3)
        XCTAssertTrue(updates.contains { update in
            if case .manualReview(3) = update { return true }
            return false
        })
        XCTAssertTrue(updates.contains { update in
            if case .unresolved(1) = update { return true }
            return false
        })
        XCTAssertTrue(updates.contains { update in
            if case .archiveRoot("/tmp/archive") = update { return true }
            return false
        })
    }
}
