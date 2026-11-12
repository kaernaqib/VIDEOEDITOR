import json, sys, wave, numpy as np
from faster_whisper import WhisperModel
names = sys.argv[1:]
m = WhisperModel(__import__("os").environ.get("WM","medium"), device="cpu", compute_type="int8")
for n in names:
    d = f"/home/user/reels/work/{n}"
    wf = wave.open(f"{d}/a16.wav"); a = np.frombuffer(wf.readframes(wf.getnframes()), np.int16).astype(np.float32)/32768
    hop=160; k=len(a)//hop; db=20*np.log10(np.sqrt((a[:k*hop].reshape(k,hop)**2).mean(1)+1e-12)); np.save(f"{d}/db10ms.npy", db)
    segs,_ = m.transcribe(a, language="ms", word_timestamps=True, condition_on_previous_text=False, beam_size=5, temperature=0,
        initial_prompt="Video trading forex syarikat Weby Markets dalam Bahasa Melayu bercampur English: lot size, stop loss, deposit bonus, broker, risk management, percent, account, margin call, MC, floating, Weby, kelebihan.")
    W=[]
    for s in segs:
        for w in s.words: W.append({"i":len(W),"w":w.word.strip(),"s":round(w.start,3),"e":round(w.end,3),"p":round(w.probability,2)})
    json.dump(W, open(f"{d}/words{__import__("os").environ.get("SUF","")}.json","w"), ensure_ascii=False)
    with open(f"{d}/phrases{__import__("os").environ.get("SUF","")}.txt","w") as f:
        line=[]
        for w in W+[None]:
            if line and (w is None or w["s"]-line[-1]["e"]>0.3):
                f.write(f"[{line[0]['i']:3d}-{line[-1]['i']:3d}] {line[0]['s']:6.2f}-{line[-1]['e']:6.2f} {' '.join(x['w'] for x in line)}\n"); line=[]
            if w: line.append(w)
    print("done", n, len(W), flush=True)
