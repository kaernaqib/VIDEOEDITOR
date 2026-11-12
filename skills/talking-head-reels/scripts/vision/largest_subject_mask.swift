// largest_subject_mask: per-frame mask of the LARGEST foreground subject only, raw 8-bit gray WxH frames to stdout.
// usage: largest_subject_mask VIDEO W H > mask.raw
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
func area(_ pb: CVPixelBuffer) -> Int {
  CVPixelBufferLockBaseAddress(pb, .readOnly); defer { CVPixelBufferUnlockBaseAddress(pb, .readOnly) }
  let w = CVPixelBufferGetWidth(pb), h = CVPixelBufferGetHeight(pb), bpr = CVPixelBufferGetBytesPerRow(pb)
  let fmt = CVPixelBufferGetPixelFormatType(pb); let base = CVPixelBufferGetBaseAddress(pb)!; var n = 0
  for y in stride(from: 0, to: h, by: 4) { for x in stride(from: 0, to: w, by: 4) {
    if fmt == kCVPixelFormatType_OneComponent32Float { if base.advanced(by: y * bpr).assumingMemoryBound(to: Float32.self)[x] > 0.5 { n += 1 } }
    else { if base.advanced(by: y * bpr).assumingMemoryBound(to: UInt8.self)[x] > 128 { n += 1 } } } }
  return n }
while let sb = out.copyNextSampleBuffer() { autoreleasepool {
  guard let pb = CMSampleBufferGetImageBuffer(sb) else { return }
  let h = VNImageRequestHandler(cvPixelBuffer: pb, options: [:]); let req = VNGenerateForegroundInstanceMaskRequest()
  try? h.perform([req])
  CVPixelBufferLockBaseAddress(mb!, []); memset(CVPixelBufferGetBaseAddress(mb!)!, 0, CVPixelBufferGetBytesPerRow(mb!) * H); CVPixelBufferUnlockBaseAddress(mb!, [])
  if let r = req.results?.first {
    var best: CVPixelBuffer? = nil; var bestA = -1
    for inst in r.allInstances { if let m = try? r.generateScaledMaskForImage(forInstances: IndexSet(integer: inst), from: h) { let ar = area(m); if ar > bestA { bestA = ar; best = m } } }
    if let m = best { let mi = CIImage(cvPixelBuffer: m); ctx.render(mi.transformed(by: CGAffineTransform(scaleX: CGFloat(W) / mi.extent.width, y: CGFloat(H) / mi.extent.height)), to: mb!) } }
  CVPixelBufferLockBaseAddress(mb!, .readOnly); let base = CVPixelBufferGetBaseAddress(mb!)!; let bpr = CVPixelBufferGetBytesPerRow(mb!)
  var d = Data(capacity: W * H); for r in 0..<H { d.append(base.advanced(by: r * bpr).assumingMemoryBound(to: UInt8.self), count: W) }
  CVPixelBufferUnlockBaseAddress(mb!, .readOnly); so.write(d) } }
