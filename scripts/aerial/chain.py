# Photos that could not be matched to today's ortho (tsunami-changed towns, sea) are matched to overlapping
# photos of the same era that are already solved: SIFT photo-to-photo homography, chained outwards.
import json, math
import numpy as np, cv2
from common import *
G = json.load(open(D + "georef.json", encoding="utf-8"))
C = {f'{x["reference_number"]}-{x["course_number"]}-{x["photo_number"]}': x for x in json.load(open(D + "chosen.json", encoding="utf-8"))}
solid = {k for k, r in G.items() if "H" in r and "fallback_from" not in r.get("info", {})}   # matched to the ortho
solid |= {k for k, r in G.items() if r.get("info", {}).get("fallback_from") and "src" in r}       # refined fallbacks
todo = [k for k in C if k not in solid]
print("solid", len(solid), "todo", len(todo))
S = 1100                                       # working width for photo-to-photo matching
sift = cv2.SIFT_create(6000)
feat = {}
def features(k):
    if k not in feat:
        ref, course, num = k.split("-"); P = photo(ref, course, int(num))
        h, w = P.shape[:2]; s = S / w
        g = cv2.cvtColor(cv2.resize(P, (S, int(h * s)), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
        mask = np.zeros_like(g); mask[int(g.shape[0]*.06):int(g.shape[0]*.94), int(g.shape[1]*.06):int(g.shape[1]*.94)] = 255
        kp, de = sift.detectAndCompute(g, mask)
        feat[k] = (np.float32([p.pt for p in kp]) / s, de, (h, w))
    return feat[k]
def centre(k): lon, lat = C[k]["geom_center_pos"]; return lat, lon
dist = lambda a, b: math.hypot((a[0]-b[0])*111, (a[1]-b[1])*87)
def match(a, b):
    pa, da, _ = features(a); pb, db, _ = features(b)
    if da is None or db is None or len(da) < 50 or len(db) < 50: return None, 0
    m = cv2.BFMatcher().knnMatch(da, db, k=2)
    good = [x for x, y in (p for p in m if len(p) == 2) if x.distance < 0.7 * y.distance]
    if len(good) < 30: return None, len(good)
    src = pa[[g.queryIdx for g in good]]; dst = pb[[g.trainIdx for g in good]]
    H, inl = cv2.findHomography(src, dst, cv2.RANSAC, 15.0)
    return (H, int(inl.sum())) if H is not None else (None, 0)
progress = True
while progress and todo:
    progress = False
    for k in list(todo):
        best = None
        for s in sorted(solid, key=lambda s: dist(centre(k), centre(s))):
            if dist(centre(k), centre(s)) > 0.23 * C[k]["scale"] / 1000 * 0.85: break
            Hks, n = match(k, s)
            if Hks is not None and n >= 60 and (best is None or n > best[1]): best = (s, n, Hks)
        if best:
            s, n, Hks = best
            H = np.array(G[s]["H"]) @ Hks
            G[k] = {"meta": G.get(k, {}).get("meta", {kk: C[k][kk] for kk in ("specification_id", "reference_number", "course_number", "photo_number", "search_date", "color_type_name", "scale", "city_name")}),
                    "size": list(features(k)[2]), "H": H.tolist(), "info": {"chained_from": s, "photo_inliers": n}}
            solid.add(k); todo.remove(k); progress = True
            print(k, "chained from", s, "inliers", n, flush=True)
print("still unsolved (keep neighbour estimate):", todo)
json.dump(G, open(D + "georef.json", "w", encoding="utf-8"), ensure_ascii=False)
