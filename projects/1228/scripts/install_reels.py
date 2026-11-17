"""Create one new CapCut project per reel (never touches existing projects except appending to root_meta_info.json,
which is backed up first). Refuses to run while CapCut is open.

usage: python install_reels.py WORK_DIR SKELETON_PROJECT_DIR [ids...]
"""
import copy, hashlib, json, os, shutil, subprocess, sys, time, uuid

work, skel = sys.argv[1], sys.argv[2]
only = set(sys.argv[3:])
root = os.path.join(os.environ["LOCALAPPDATA"], "CapCut", "User Data", "Projects", "com.lveditor.draft")
root_fwd = root.replace("\\", "/")
REELS = json.load(open(f"{work}/reels.json", encoding="utf-8"))
U = lambda: str(uuid.uuid4()).upper()
now = lambda: int(time.time() * 1e6)

ps = subprocess.run(["tasklist", "/FI", "IMAGENAME eq CapCut.exe"], capture_output=True, text=True).stdout
assert "CapCut.exe" not in ps, "CapCut is still running: quit it first"

rm_path = os.path.join(root, "root_meta_info.json")
RM = json.load(open(rm_path, encoding="utf-8"))
stamp = time.strftime("%Y%m%d-%H%M")
shutil.copy2(rm_path, os.path.join(root, f"root_meta_info.json.before_reels_{stamp}"))
tmpl_entry = next(e for e in RM["all_draft_store"] if e["draft_name"] == "1229")
skel_tl = json.load(open(f"{skel}/Timelines/project.json", encoding="utf-8"))["main_timeline_id"]
report = []

for r in REELS:
    if only and r["id"] not in only:
        continue
    name = f"1228 Reel {r['id']} - {r['title']}".replace("?", "").replace(",", "").replace("&", "dan")
    dst = os.path.join(root, name)
    assert not os.path.exists(dst), f"exists already: {dst}"
    shutil.copytree(skel, dst)
    blob = open(f"{work}/r{r['id']}/build/draft_content.json", encoding="utf-8").read()
    D = json.loads(blob)
    md5 = hashlib.md5(blob.encode("utf-8")).hexdigest()
    # timelines: give this project its own main timeline id
    new_tl = U()
    os.rename(os.path.join(dst, "Timelines", skel_tl), os.path.join(dst, "Timelines", new_tl))
    pj = json.load(open(f"{dst}/Timelines/project.json", encoding="utf-8"))
    pj.update(id=U(), main_timeline_id=new_tl, create_time=now(), update_time=now())
    pj["timelines"] = [dict(pj["timelines"][0], id=new_tl, create_time=now(), update_time=now())]
    for n in ("project.json", "project.json.bak"):
        json.dump(pj, open(f"{dst}/Timelines/{n}", "w", encoding="utf-8"), separators=(",", ":"))
    patch = os.path.join(dst, "Timelines", new_tl, "attachment", "patch")
    if os.path.isdir(patch):
        shutil.rmtree(patch)                 # the skeleton's cached mini draft must not override ours
    targets = []
    for d in (dst, os.path.join(dst, "Timelines", new_tl)):
        for n in ("draft_content.json", "draft_content.json.bak", "template-2.tmp"):
            p = os.path.join(d, n)
            open(p, "w", encoding="utf-8").write(blob)
            targets.append(p)
    for d in (dst, os.path.join(dst, "Timelines", new_tl)):
        shutil.copy2(f"{work}/thumbs/thumb_{r['id']}.jpg", os.path.join(d, "draft_cover.jpg"))
    meta = json.load(open(f"{work}/r{r['id']}/build/draft_meta_info.json", encoding="utf-8"))
    did = U()
    for g in meta.get("draft_materials", []):
        g["value"] = []
    meta.update(draft_id=did, draft_name=name, draft_fold_path=f"{root_fwd}/{name}", draft_root_path=root,
                draft_cover="draft_cover.jpg", tm_draft_create=now(), tm_draft_modified=now(), tm_duration=D["duration"])
    json.dump(meta, open(f"{dst}/draft_meta_info.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    e = copy.deepcopy(tmpl_entry)
    e.update(draft_cover=f"{root_fwd}/{name}\\draft_cover.jpg", draft_fold_path=f"{root_fwd}/{name}", draft_id=did,
             draft_json_file=f"{root_fwd}/{name}\\draft_content.json", draft_name=name,
             tm_draft_create=now(), tm_draft_modified=now(), draft_timeline_materials_size=0)
    RM["all_draft_store"].insert(0, e)
    RM["draft_ids"] = RM.get("draft_ids", 0) + 1
    # verify
    sums = {hashlib.md5(open(p, "rb").read()).hexdigest() for p in targets}
    mats = [o.get("path") for k in ("videos", "audios") for o in D["materials"].get(k, [])]
    missing = sorted({p for p in mats if p and not os.path.exists(p)})
    report.append({"name": name, "md5_ok": sums == {md5}, "missing": missing})
    print(f"{name}: md5 {'ok' if sums == {md5} else 'MISMATCH'}, missing media {len(missing)}")

json.dump(RM, open(rm_path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
json.dump(report, open(f"{work}/install_report.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("root_meta_info.json updated (backup: root_meta_info.json.before_reels_%s)" % stamp)
