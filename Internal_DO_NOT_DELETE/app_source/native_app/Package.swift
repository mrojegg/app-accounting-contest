// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "SortingFilesNativeApp",
    platforms: [
        .macOS(.v13),
    ],
    products: [
        .executable(name: "SortingFilesNativeApp", targets: ["SortingFilesNativeApp"]),
        .executable(name: "PDFMergeHelper", targets: ["PDFMergeHelper"]),
    ],
    targets: [
        .executableTarget(
            name: "SortingFilesNativeApp",
            path: "Sources/SortingFilesNativeApp"
        ),
        .testTarget(
            name: "SortingFilesNativeAppTests",
            dependencies: ["SortingFilesNativeApp"],
            path: "Tests/SortingFilesNativeAppTests"
        ),
        .executableTarget(
            name: "PDFMergeHelper",
            path: "Sources/PDFMergeHelper"
        ),
    ]
)
