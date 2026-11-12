// facebox <in.png> <out.png> [maxFaceH=0.2] [pad=0.35]
// Black-boxes every SMALL face (full-body panels of a character sheet); the large close-up face stays. Local Apple Vision only.
import Foundation
import Vision
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers
let a = CommandLine.arguments
guard a.count >= 3 else { print("usage: facebox in out [maxFaceH] [pad]"); exit(2) }
let maxH = a.count > 3 ? Double(a[3])! : 0.2
let pad = a.count > 4 ? Double(a[4])! : 0.35
let src = CGImageSourceCreateWithURL(URL(fileURLWithPath: a[1]) as CFURL, nil)!
let img = CGImageSourceCreateImageAtIndex(src, 0, nil)!
let W = img.width, H = img.height
let req = VNDetectFaceRectanglesRequest()
try VNImageRequestHandler(cgImage: img, options: [:]).perform([req])
let faces = (req.results ?? []).map { $0.boundingBox }
let ctx = CGContext(data: nil, width: W, height: H, bitsPerComponent: 8, bytesPerRow: 0, space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
ctx.draw(img, in: CGRect(x: 0, y: 0, width: W, height: H))
ctx.setFillColor(CGColor(red: 0, green: 0, blue: 0, alpha: 1))
var n = 0
for b in faces {
  print(String(format: "face x %.3f y %.3f w %.3f h %.3f", b.minX, b.minY, b.width, b.height))
  if b.height >= maxH { continue }
  let px = b.width * pad, py = b.height * pad
  // vision box: normalized, origin bottom-left = CGContext origin
  let r = CGRect(x: (b.minX - px) * Double(W), y: (b.minY - py) * Double(H), width: (b.width + 2 * px) * Double(W), height: (b.height + 2 * py * 1.15) * Double(H))
  let side = max(r.width, r.height)
  let sq = CGRect(x: r.midX - side / 2, y: r.midY - side / 2, width: side, height: side)
  ctx.fill(sq); n += 1
}
let out = ctx.makeImage()!
let d = CGImageDestinationCreateWithURL(URL(fileURLWithPath: a[2]) as CFURL, UTType.png.identifier as CFString, 1, nil)!
CGImageDestinationAddImage(d, out, nil); CGImageDestinationFinalize(d)
print("boxed \(n) of \(faces.count) faces -> \(a[2])")
