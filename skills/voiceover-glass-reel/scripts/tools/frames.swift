// frames <video> <out.jpg> <cols> <t1> <t2> ...   (times in seconds)
// Grabs exact frames (zero tolerance) and lays them out as one contact sheet, 640 px per cell. For checking a render.
import AVFoundation
import CoreGraphics
import Foundation
import ImageIO
import UniformTypeIdentifiers

let a = CommandLine.arguments
guard a.count >= 5 else { print("usage: frames <video> <out.jpg> <cols> <t...>"); exit(2) }
let asset = AVURLAsset(url: URL(fileURLWithPath: a[1]))
let gen = AVAssetImageGenerator(asset: asset)
gen.appliesPreferredTrackTransform = true
gen.requestedTimeToleranceBefore = .zero
gen.requestedTimeToleranceAfter = .zero
let cols = Int(a[3])!
let times = a[4...].compactMap { Double($0) }
var imgs: [CGImage] = []
for t in times {
  if let im = try? gen.copyCGImage(at: CMTime(seconds: t, preferredTimescale: 600), actualTime: nil) { imgs.append(im) }
  else { print("WARN no frame at", t) }
}
guard let first = imgs.first else { print("ERR no frames"); exit(3) }
let cw = 640, ch = cw * first.height / first.width
let rows = (imgs.count + cols - 1) / cols
let ctx = CGContext(data: nil, width: cols * cw, height: rows * ch, bitsPerComponent: 8, bytesPerRow: 0,
  space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
for (i, im) in imgs.enumerated() {
  let c = i % cols, r = i / cols
  ctx.draw(im, in: CGRect(x: c * cw, y: (rows - 1 - r) * ch, width: cw, height: ch))
}
let d = CGImageDestinationCreateWithURL(URL(fileURLWithPath: a[2]) as CFURL, UTType.jpeg.identifier as CFString, 1, nil)!
CGImageDestinationAddImage(d, ctx.makeImage()!, nil)
CGImageDestinationFinalize(d)
print("sheet", a[2], imgs.count, "frames")
