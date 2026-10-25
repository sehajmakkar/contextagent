// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "ContextAgent",
    platforms: [.macOS(.v14)],
    targets: [
        .executableTarget(name: "ContextAgent", path: "Sources/ContextAgent"),
        .testTarget(name: "ContextAgentTests", dependencies: ["ContextAgent"], path: "Tests/ContextAgentTests",
                    resources: [.copy("Fixtures")]),
    ]
)
