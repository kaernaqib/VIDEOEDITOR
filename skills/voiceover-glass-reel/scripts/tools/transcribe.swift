// transcribe <in.wav> <out.json> [locale=en-US] [--legacy]
// On-device transcription with word times. Nothing leaves the Mac.
//   macOS 26+: SpeechAnalyzer + SpeechTranscriber (best timing).
//   older macOS or --legacy: SFSpeechRecognizer with requiresOnDeviceRecognition.
// Writes {"engine": ..., "words": [{"w", "start", "end"}]} (seconds from the start of the file).
import AVFoundation
import Foundation
import Speech

let args = CommandLine.arguments.filter { $0 != "--legacy" }
let forceLegacy = CommandLine.arguments.contains("--legacy")
guard args.count >= 3 else { print("usage: transcribe <in.wav> <out.json> [locale] [--legacy]"); exit(2) }
let inURL = URL(fileURLWithPath: args[1])
let outURL = URL(fileURLWithPath: args[2])
let localeId = args.count > 3 ? args[3] : "en-US"
setvbuf(stdout, nil, _IONBF, 0)

func write(_ words: [[String: Any]], _ engine: String) {
  let obj: [String: Any] = ["engine": engine, "locale": localeId, "words": words]
  let data = try! JSONSerialization.data(withJSONObject: obj, options: [.prettyPrinted])
  try! data.write(to: outURL)
  print("done, words:", words.count, "->", outURL.path)
}

// split a run of text with one time range into words, sharing the range by character count
func splitRun(_ s: String, _ t0: Double, _ t1: Double) -> [[String: Any]] {
  let parts = s.split(whereSeparator: { $0 == " " || $0 == "\n" || $0 == "\t" }).map(String.init)
  if parts.isEmpty { return [] }
  if parts.count == 1 { return [["w": parts[0], "start": t0, "end": t1]] }
  let total = Double(parts.reduce(0) { $0 + $1.count })
  var out: [[String: Any]] = []
  var t = t0
  for p in parts {
    let d = (t1 - t0) * Double(p.count) / max(1, total)
    out.append(["w": p, "start": t, "end": t + d]); t += d
  }
  return out
}

func legacy() {
  let sem = DispatchSemaphore(value: 0)
  SFSpeechRecognizer.requestAuthorization { _ in sem.signal() }
  sem.wait()
  guard let rec = SFSpeechRecognizer(locale: Locale(identifier: localeId)) else { print("ERR no recognizer for", localeId); exit(3) }
  let req = SFSpeechURLRecognitionRequest(url: inURL)
  req.requiresOnDeviceRecognition = rec.supportsOnDeviceRecognition
  req.shouldReportPartialResults = false
  if #available(macOS 13, *) { req.addsPunctuation = true }
  var words: [[String: Any]] = []
  let done = DispatchSemaphore(value: 0)
  rec.recognitionTask(with: req) { result, error in
    if let r = result, r.isFinal {
      for s in r.bestTranscription.segments {
        words.append(["w": s.substring, "start": s.timestamp, "end": s.timestamp + s.duration])
      }
      done.signal()
    } else if let e = error { print("ERR", e); done.signal() }
  }
  done.wait()
  write(words, "SFSpeechRecognizer (on-device: \(rec.supportsOnDeviceRecognition))")
  exit(0)
}

if forceLegacy { legacy() }
if #available(macOS 26, *) {
  let sem = DispatchSemaphore(value: 0)
  Task {
    do {
      let transcriber = SpeechTranscriber(locale: Locale(identifier: localeId), transcriptionOptions: [], reportingOptions: [], attributeOptions: [.audioTimeRange])
      if let req = try await AssetInventory.assetInstallationRequest(supporting: [transcriber]) {
        print("downloading the on-device speech model...")
        try await req.downloadAndInstall()
      }
      let analyzer = SpeechAnalyzer(modules: [transcriber])
      let file = try AVAudioFile(forReading: inURL)
      let collector = Task { () -> [[String: Any]] in
        var out: [[String: Any]] = []
        for try await r in transcriber.results {
          for run in r.text.runs {
            let s = String(r.text[run.range].characters)
            if let tr = run.audioTimeRange {
              out += splitRun(s, CMTimeGetSeconds(tr.start), CMTimeGetSeconds(tr.end))
            }
          }
        }
        return out
      }
      if let last = try await analyzer.analyzeSequence(from: file) {
        try await analyzer.finalizeAndFinish(through: last)
      } else { await analyzer.cancelAndFinishNow() }
      let words = try await collector.value
      write(words, "SpeechAnalyzer + SpeechTranscriber (on-device)")
    } catch { print("ERR", error); exit(2) }
    sem.signal()
  }
  sem.wait()
} else {
  legacy()
}
