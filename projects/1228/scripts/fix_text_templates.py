"""Place the harvested caption/header templates for the authority style on a 9:16 canvas.
caption: chest level (~55% from top), header: '#N TITLE' (yellow number, white title) near the top safe zone.
Only position/scale values and style order change; every object is still the one CapCut wrote."""
import copy, json, sys

p = sys.argv[1]
T = json.load(open(p, encoding="utf-8"))
cap = T["caption"]
cap["segment"]["clip"]["transform"] = {"x": 0.0, "y": -0.1}
cap["segment"]["clip"]["scale"] = {"x": 0.78, "y": 0.78}
h = copy.deepcopy(cap)
h["styles"] = [copy.deepcopy(cap["hi_style"]), copy.deepcopy(cap["base_style"])]
h["segment"]["clip"]["transform"] = {"x": 0.0, "y": 0.70}
h["segment"]["clip"]["scale"] = {"x": 0.62, "y": 0.62}
T["header"] = h
json.dump(T, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("caption y=-0.10 scale .78; header y=0.70 scale .62")
