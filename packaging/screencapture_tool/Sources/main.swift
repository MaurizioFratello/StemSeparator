import Foundation
import ScreenCaptureKit
import AVFoundation

/// Simple ScreenCaptureKit-based audio recorder for system audio
/// This tool captures system audio without requiring BlackHole or other virtual audio drivers
@main
struct ScreenCaptureRecorder {
    static func main() async {
        let args = CommandLine.arguments

        // Print usage if no arguments
        guard args.count > 1 else {
            printUsage()
            exit(1)
        }

        let command = args[1]

        switch command {
        case "list-devices":
            await listDevices()

        case "record":
            await handleRecord(args: Array(args.dropFirst(2)))

        case "test":
            await testScreenCaptureKit()

        case "help", "--help", "-h":
            printUsage()

        default:
            print("Error: Unknown command '\(command)'")
            printUsage()
            exit(1)
        }
    }

    static func printUsage() {
        print("""
        ScreenCapture Audio Recorder

        Usage:
            screencapture-recorder <command> [options]

        Commands:
            list-devices           List available displays and applications
            record                 Record system audio
            test                   Test if ScreenCaptureKit is available
            help                   Show this help message

        Record Options:
            --output <path>        Output WAV file path (required)
            --duration <seconds>   Recording duration in seconds (default: 10)
            --display <id>         Display ID to record from (default: main display)

        Examples:
            # Test if ScreenCaptureKit works
            screencapture-recorder test

            # List available displays
            screencapture-recorder list-devices

            # Record 5 seconds of system audio
            screencapture-recorder record --output recording.wav --duration 5
        """)
    }

    // MARK: - Commands

    static func testScreenCaptureKit() async {
        print("Testing ScreenCaptureKit availability...")

        // Check macOS version
        if #available(macOS 13.0, *) {
            print("✓ macOS 13.0+ detected - ScreenCaptureKit is available")
        } else {
            print("✗ macOS 13.0+ required - ScreenCaptureKit is NOT available")
            exit(1)
        }

        // Try to get shareable content
        do {
            let content = try await SCShareableContent.excludingDesktopWindows(
                false,
                onScreenWindowsOnly: true
            )
            print("✓ Successfully accessed ScreenCaptureKit")
            print("  Found \(content.displays.count) display(s)")
            print("  Found \(content.applications.count) running application(s)")
        } catch {
            print("✗ Failed to access ScreenCaptureKit: \(error.localizedDescription)")
            print("  You may need to grant Screen Recording permission in System Settings")
            exit(1)
        }
    }

    static func listDevices() async {
        print("Fetching available displays and applications...")

        do {
            let content = try await SCShareableContent.excludingDesktopWindows(
                false,
                onScreenWindowsOnly: true
            )

            print("\n📺 Displays:")
            for (index, display) in content.displays.enumerated() {
                print("  [\(index)] \(display.displayID) - \(display.width)x\(display.height)")
            }

            print("\n📱 Applications (with windows):")
            for app in content.applications.prefix(10) {
                print("  - \(app.applicationName) (PID: \(app.processID))")
            }

            if content.applications.count > 10 {
                print("  ... and \(content.applications.count - 10) more")
            }

        } catch {
            print("Error: \(error.localizedDescription)")
            exit(1)
        }
    }

    static func handleRecord(args: [String]) async {
        var outputPath: String?
        var duration: Double = 10.0
        var displayID: CGDirectDisplayID?

        // Parse arguments
        var i = 0
        while i < args.count {
            switch args[i] {
            case "--output":
                guard i + 1 < args.count else {
                    print("Error: --output requires a path")
                    exit(1)
                }
                outputPath = args[i + 1]
                i += 2

            case "--duration":
                guard i + 1 < args.count else {
                    print("Error: --duration requires a value")
                    exit(1)
                }
                guard let d = Double(args[i + 1]) else {
                    print("Error: Invalid duration value")
                    exit(1)
                }
                duration = d
                i += 2

            case "--display":
                guard i + 1 < args.count else {
                    print("Error: --display requires an ID")
                    exit(1)
                }
                guard let id = UInt32(args[i + 1]) else {
                    print("Error: Invalid display ID")
                    exit(1)
                }
                displayID = id
                i += 2

            default:
                print("Error: Unknown option '\(args[i])'")
                exit(1)
            }
        }

        guard let output = outputPath else {
            print("Error: --output is required")
            printUsage()
            exit(1)
        }

        await record(outputPath: output, duration: duration, displayID: displayID)
    }

    static func record(outputPath: String, duration: Double, displayID: CGDirectDisplayID?) async {
        print("Starting ScreenCaptureKit audio recording...")
        print("  Output: \(outputPath)")
        print("  Duration: \(duration) seconds")

        do {
            // Get shareable content
            let content = try await SCShareableContent.excludingDesktopWindows(
                false,
                onScreenWindowsOnly: true
            )

            // Select display
            guard let display = content.displays.first else {
                print("Error: No displays found")
                exit(1)
            }

            print("  Recording from display: \(display.displayID)")

            // Create content filter (display only)
            let filter = SCContentFilter(display: display, excludingApplications: [], exceptingWindows: [])

            // Configure stream
            let streamConfig = SCStreamConfiguration()

            // Audio configuration
            streamConfig.capturesAudio = true
            streamConfig.excludesCurrentProcessAudio = true
            streamConfig.sampleRate = 48000  // 48kHz
            streamConfig.channelCount = 2     // Stereo

            // We don't need video for audio-only recording, but we need to configure it
            streamConfig.width = 1
            streamConfig.height = 1
            streamConfig.minimumFrameInterval = CMTime(value: 1, timescale: 1)

            // Create recorder delegate
            let recorder = AudioRecorder(outputPath: outputPath, duration: duration)

            // Create and start stream
            let stream = SCStream(filter: filter, configuration: streamConfig, delegate: nil)

            // Add audio output
            try stream.addStreamOutput(recorder, type: .audio, sampleHandlerQueue: .global(qos: .userInitiated))

            print("✓ Starting capture stream...")
            try await stream.startCapture()

            print("✓ Recording... (press Ctrl+C to stop early)")

            // Record for specified duration
            try await Task.sleep(nanoseconds: UInt64(duration * 1_000_000_000))

            // Stop capture
            print("\n✓ Stopping capture...")
            try await stream.stopCapture()

            // Finalize recording
            await recorder.finalize()

            print("✓ Recording saved to: \(outputPath)")

        } catch {
            print("✗ Recording failed: \(error.localizedDescription)")
            exit(1)
        }
    }
}

// MARK: - Audio Recorder

/// Handles audio sample buffers and writes them to a WAV file
class AudioRecorder: NSObject, SCStreamOutput {
    private let outputPath: String
    private let duration: Double
    private var audioFile: AVAudioFile?
    private var audioFormat: AVAudioFormat?
    private var samplesWritten: Int64 = 0

    init(outputPath: String, duration: Double) {
        self.outputPath = outputPath
        self.duration = duration
        super.init()
    }

    func stream(_ stream: SCStream, didOutputSampleBuffer sampleBuffer: CMSampleBuffer, of outputType: SCStreamOutputType) {
        // Only handle audio samples
        guard outputType == .audio else { return }

        // Initialize audio file on first sample
        if audioFile == nil {
            setupAudioFile(from: sampleBuffer)
        }

        // Write audio samples
        writeAudioSamples(from: sampleBuffer)
    }

    private func setupAudioFile(from sampleBuffer: CMSampleBuffer) {
        guard let formatDescription = CMSampleBufferGetFormatDescription(sampleBuffer) else {
            print("Error: Failed to get audio format description")
            return
        }

        guard let streamBasicDescription = CMAudioFormatDescriptionGetStreamBasicDescription(formatDescription) else {
            print("Error: Failed to get stream basic description")
            return
        }

        // Create AVAudioFormat from stream description
        guard let format = AVAudioFormat(
            standardFormatWithSampleRate: streamBasicDescription.pointee.mSampleRate,
            channels: AVAudioChannelCount(streamBasicDescription.pointee.mChannelsPerFrame)
        ) else {
            print("Error: Failed to create audio format")
            return
        }

        self.audioFormat = format

        // Create output file
        let fileURL = URL(fileURLWithPath: outputPath)

        do {
            audioFile = try AVAudioFile(
                forWriting: fileURL,
                settings: format.settings,
                commonFormat: .pcmFormatFloat32,
                interleaved: false
            )
            print("✓ Audio file initialized: \(format.sampleRate)Hz, \(format.channelCount) channels")
        } catch {
            print("Error creating audio file: \(error.localizedDescription)")
        }
    }

    private func writeAudioSamples(from sampleBuffer: CMSampleBuffer) {
        guard let audioFile = audioFile,
              let format = audioFormat else {
            return
        }

        // Get audio buffer list
        var audioBufferList = AudioBufferList()
        var blockBuffer: CMBlockBuffer?

        CMSampleBufferGetAudioBufferListWithRetainedBlockBuffer(
            sampleBuffer,
            bufferListSizeNeededOut: nil,
            bufferListOut: &audioBufferList,
            bufferListSize: MemoryLayout<AudioBufferList>.size,
            blockBufferAllocator: nil,
            blockBufferMemoryAllocator: nil,
            flags: 0,
            blockBufferOut: &blockBuffer
        )

        // Get frame count
        let frameCount = CMSampleBufferGetNumSamples(sampleBuffer)

        // Create PCM buffer
        guard let pcmBuffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: AVAudioFrameCount(frameCount)) else {
            return
        }

        pcmBuffer.frameLength = AVAudioFrameCount(frameCount)

        // Copy audio data to PCM buffer
        let channels = Int(format.channelCount)
        for channel in 0..<channels {
            if let channelData = pcmBuffer.floatChannelData?[channel],
               let sourceData = audioBufferList.mBuffers.mData?.assumingMemoryBound(to: Float.self) {
                channelData.update(from: sourceData, count: frameCount)
            }
        }

        // Write to file
        do {
            try audioFile.write(from: pcmBuffer)
            samplesWritten += Int64(frameCount)
        } catch {
            print("Error writing audio samples: \(error.localizedDescription)")
        }
    }

    func finalize() async {
        if audioFile != nil {
            print("✓ Wrote \(samplesWritten) audio samples (\(Double(samplesWritten) / audioFormat!.sampleRate) seconds)")
        }
    }
}
