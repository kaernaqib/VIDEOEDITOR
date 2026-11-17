"""Proofread fixes on every part's words.json (keeps timings; extra slots become empty words)."""
import glob, json, sys

work = sys.argv[1]
SEQ = [
    (["isi", "Malaysia"], ["di", "Malaysia"]),
    (["baru", "ajar"], ["baru", "aja"]),
    (["key"], ["okey"]),
    (["tambah", "air", "gitu"], ["tambah", "air", "lagi"]),
    (["jangan", "nak", "kencang", "kencang", "kan"], ["takkan", "nak", "makan", "chicken", "chop"]),
    (["prince"], ["Queen"]), (["queens"], ["Queen"]), (["market"], ["Market"]),
    (["twelve"], ["12"]),
    (["Nasional", "galeri"], ["National", "Gallery"]), (["gallery"], ["Gallery"]),
    (["shrine", "of", "remembrance"], ["Shrine", "of", "Remembrance"]),
    (["Saint", "kilda"], ["St", "Kilda"]), (["Saint", "Kilda"], ["St", "Kilda"]),
    (["state", "library"], ["State", "Library"]),
    (["brighton"], ["Brighton"]), (["elwood"], ["Elwood"]),
    (["A"], ["a"]),
    (["but", "here"], ["butts", "here"]),
    (["jadikan"], ["jadi ke"]),
]
n = 0
for f in glob.glob(f"{work}/r??/p*/words.json"):
    W = json.load(open(f, encoding="utf-8"))
    toks = [w["w"].strip() for w in W]
    for old, new in SEQ:
        L = len(old)
        for i in range(len(W) - L + 1):
            if toks[i:i + L] == old:
                for k in range(L):
                    W[i + k]["w"] = " " + new[k]
                    toks[i + k] = new[k]
                n += 1
    json.dump(W, open(f, "w", encoding="utf-8"), ensure_ascii=False)
print(n, "fixes")
