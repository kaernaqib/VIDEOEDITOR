// person_track: per-frame face boxes (JSON lines to argv[2]) and an 8-bit person-segmentation matte (raw gray WxH frames to stdout).
// usage: person_track VIDEO FACES.jsonl W H > matte.raw
import Foundation
import AVFoundation
import Vision
import CoreImage
let a = CommandLine.arguments
let url = URL(fileURLWithPath: a[1]); let faceOut = a[2]; let W = Int(a[3])!, H = Int(a[4])!
let asset = AVURLAsset(url: url)
let sem = DispatchSemaphore(value: 0); var track: AVAssetTrack?
Task { track = try? await asset.loadTracks(withMediaType: .video).first; sem.signal() }; sem.wait()
guard let vt = track else { FileHandle.standardError.write("no track\n".data(using: .utf8)!); exit(1) }
let reader = try! AVAssetReader(asset: asset)
let out = AVAssetReaderTrackOutput(track: vt, outputSettings: [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA, kCVPixelBufferWidthKey as String: W, kCVPixelBufferHeightKey as String: H])
out.alwaysCopiesSampleData = false; reader.add(out); reader.startReading()
FileManager.default.createFile(atPath: faceOut, contents: nil); let fh = FileHandle(forWritingAtPath: faceOut)!
let ctx = CIContext(options: [.workingColorSpace: NSNull()])
var maskBuf: CVPixelBuffer?; CVPixelBufferCreate(nil, W, H, kCVPixelFormatType_OneComponent8, nil, &maskBuf)
let stdout = FileHandle.standardOutput; var n = 0
while let sb = out.copyNextSampleBuffer() {
  autoreleasepool {
    guard let pb = CMSampleBufferGetImageBuffer(sb) else { return }
    let h = VNImageRequestHandler(cvPixelBuffer: pb, options: [:])
    let face = VNDetectFaceRectanglesRequest()
    let seg = VNGeneratePersonSegmentationRequest(); seg.qualityLevel = .accurate; seg.outputPixelFormat = kCVPixelFormatType_OneComponent8
    try? h.perform([face, seg])
    var line = "{\"f\":\(n)"
    if let best = (face.results ?? []).max(by: { $0.boundingBox.width < $1.boundingBox.width }) {
      let b = best.boundingBox; line += ",\"x\":\(b.midX),\"y\":\(1 - b.midY),\"w\":\(b.width),\"h\":\(b.height),\"c\":\(best.confidence)"
    }
    line += "}\n"; fh.write(line.data(using: .utf8)!)
    if let m = seg.results?.first?.pixelBuffer {
      let mi = CIImage(cvPixelBuffer: m); let sx = CGFloat(W) / mi.extent.width, sy = CGFloat(H) / mi.extent.height
      ctx.render(mi.transformed(by: CGAffineTransform(scaleX: sx, y: sy)), to: maskBuf!)
    }
    CVPixelBufferLockBaseAddress(maskBuf!, .readOnly)
    let base = CVPixelBufferGetBaseAddress(maskBuf!)!; let bpr = CVPixelBufferGetBytesPerRow(maskBuf!)
    var data = Data(capacity: W * H)
    for r in 0..<H { data.append(base.advanced(by: r * bpr).assumingMemoryBound(to: UInt8.self), count: W) }
    CVPixelBufferUnlockBaseAddress(maskBuf!, .readOnly)
    stdout.write(data); n += 1
    if n % 100 == 0 { FileHandle.standardError.write("frame \(n)\n".data(using: .utf8)!) }
  }
}
FileHandle.standardError.write("done \(n)\n".data(using: .utf8)!)
