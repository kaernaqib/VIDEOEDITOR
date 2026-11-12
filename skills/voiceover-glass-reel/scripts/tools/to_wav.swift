// to_wav <media> <out.wav>
// Writes the audio of any audio/video file (wav, mp3, m4a, mov, mp4...) as 48 kHz 16-bit stereo PCM WAV.
// Runs locally with AVFoundation.
import AVFoundation
import Foundation

let a = CommandLine.arguments
guard a.count == 3 else { print("usage: to_wav <media> <out.wav>"); exit(2) }
let asset = AVURLAsset(url: URL(fileURLWithPath: a[1]))
guard let tr = asset.tracks(withMediaType: .audio).first else { print("ERR no audio track in \(a[1])"); exit(3) }
let reader = try! AVAssetReader(asset: asset)
let set: [String: Any] = [AVFormatIDKey: kAudioFormatLinearPCM, AVSampleRateKey: 48000, AVNumberOfChannelsKey: 2,
  AVLinearPCMBitDepthKey: 16, AVLinearPCMIsFloatKey: false, AVLinearPCMIsBigEndianKey: false, AVLinearPCMIsNonInterleaved: false]
let out = AVAssetReaderTrackOutput(track: tr, outputSettings: set)
reader.add(out)
reader.startReading()
var data = Data()
while let sb = out.copyNextSampleBuffer(), let bb = CMSampleBufferGetDataBuffer(sb) {
  var len = 0
  var ptr: UnsafeMutablePointer<Int8>? = nil
  CMBlockBufferGetDataPointer(bb, atOffset: 0, lengthAtOffsetOut: nil, totalLengthOut: &len, dataPointerOut: &ptr)
  data.append(UnsafeBufferPointer(start: UnsafeRawPointer(ptr!).assumingMemoryBound(to: UInt8.self), count: len))
}
func le32(_ v: UInt32) -> Data { var x = v.littleEndian; return Data(bytes: &x, count: 4) }
func le16(_ v: UInt16) -> Data { var x = v.littleEndian; return Data(bytes: &x, count: 2) }
var h = Data("RIFF".utf8); h += le32(UInt32(36 + data.count)); h += Data("WAVEfmt ".utf8); h += le32(16); h += le16(1); h += le16(2)
h += le32(48000); h += le32(48000 * 4); h += le16(4); h += le16(16); h += Data("data".utf8); h += le32(UInt32(data.count))
try! (h + data).write(to: URL(fileURLWithPath: a[2]))
print(String(format: "wrote %@ %.2f s", a[2], Double(data.count) / 4 / 48000))
