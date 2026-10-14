// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "ocr_package",
    platforms: [
        .macOS(.v13),
    ],
    products: [
        .executable(name: "pdf_ocr_pkg", targets: ["pdf_ocr_pkg"]),
    ],
    targets: [
        .executableTarget(
            name: "pdf_ocr_pkg",
            path: "Sources/pdf_ocr_pkg"
        ),
    ]
)
