// swift-tools-version: 6.0
// The swift-tools-version declares the minimum version of Swift required to build this package.

import PackageDescription

let package = Package(
    name: "screencapture-recorder",
    platforms: [
        .macOS(.v13)  // ScreenCaptureKit requires macOS 13.0 (Ventura) or later
    ],
    targets: [
        // Main executable target
        .executableTarget(
            name: "screencapture-recorder",
            path: "Sources"
        )
    ]
)
