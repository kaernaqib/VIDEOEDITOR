// subject_mask: per-frame mask of all foreground subjects (Vision subject lifting), raw 8-bit gray WxH frames to stdout.
// usage: subject_mask VIDEO W H > mask.raw
import Foundation
import AVFoundation
import Vision
import CoreImage
let a = CommandLine.arguments; let W = Int(a[2])!, H = Int(a[3])!
let asset = AVURLAsset(url: URL(fileURLWithPath: a[1]))
let sem = DispatchSemaphore(value: 0); var track: AVAssetTrack?
Task { track = try? await asset.loadTracks(withMediaType: .video).first; sem.signal() }; sem.wait()
let reader = try! AVAssetReader(asset: asset)
let out = AVAssetReaderTrackOutput(track: track!, outputSettings: [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA])
reader.add(out); reader.startReading()
let ctx = CIContext(options: [.workingColorSpace: NSNull()])
var mb: CVPixelBuffer?; CVPixelBufferCreate(nil, W, H, kCVPixelFormatType_OneComponent8, nil, &mb)
let so = FileHandle.standardOutput
while let sb = out.copyNextSampleBuffer() { autoreleasepool {
  guard let pb = CMSampleBufferGetImageBuffer(sb) else { return }
  let h = VNImageRequestHandler(cvPixelBuffer: pb, options: [:]); let req = VNGenerateForegroundInstanceMaskRequest()
  try? h.perform([req])
  CVPixelBufferLockBaseAddress(mb!, []); memset(CVPixelBufferGetBaseAddress(mb!)!, 0, CVPixelBufferGetBytesPerRow(mb!) * H); CVPixelBufferUnlockBaseAddress(mb!, [])
  if let r = req.results?.first, let m = try? r.generateScaledMaskForImage(forInstances: r.allInstances, from: h) {
    let mi = CIImage(cvPixelBuffer: m); ctx.render(mi.transformed(by: CGAffineTransform(scaleX: CGFloat(W) / mi.extent.width, y: CGFloat(H) / mi.extent.height)), to: mb!) }
  CVPixelBufferLockBaseAddress(mb!, .readOnly); let base = CVPixelBufferGetBaseAddress(mb!)!; let bpr = CVPixelBufferGetBytesPerRow(mb!)
  var d = Data(capacity: W * H); for r in 0..<H { d.append(base.advanced(by: r * bpr).assumingMemoryBound(to: UInt8.self), count: W) }
  CVPixelBufferUnlockBaseAddress(mb!, .readOnly); so.write(d) } }
