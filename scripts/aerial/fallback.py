# 1) sanity-check every solved photo: its centre must land near the API's recorded centre
# 2) photos that failed (mostly sea) borrow the transform of the nearest solved photo on the same flight course,
#    shifted by the difference of the recorded centres, then get one refinement pass if there is enough land.
import json, math
import numpy as np, cv2
from common import *
from refine import refine
G = json.load(open(D + "georef.json", encoding="utf-8"))
C = {f'{x["reference_number"]}-{x["course_number"]}-{x["photo_number"]}': x for f in ("chosen_v1.json", "chosen.json") for x in json.load(open(D + f, encoding="utf-8"))}   # earlier and current selections
mpp17 = lambda lat: 156543.03 * math.cos(math.radians(lat)) / 2 ** 17
def centre_err(k, H, size):
    x = C[k]; lon, lat = x["geom_center_pos"]; h, w = size
    c = cv2.perspectiveTransform(np.float32([[[w / 2, h / 2]]]), np.array(H))[0, 0]
    ax, ay = world(lat, lon, 17)
    return math.hypot(c[0] - ax, c[1] - ay) * mpp17(lat)
errs = {}
for k, r in G.items():
    if "H" in r:
        e = centre_err(k, r["H"], r["size"]); errs[k] = e
        if e > 600: print("suspicious", k, f"{e:.0f} m"); r["bad"] = True
print("centre error of solved photos: median", f"{np.median(list(errs.values())):.0f} m", "max", f"{max(errs.values()):.0f} m")
good = {k: r for k, r in G.items() if "H" in r and not r.get("bad")}
for k, x in C.items():
    if k in good: continue
    ref, course, num = k.split("-"); num = int(num)
    same = [(abs(int(g.split("-")[2]) - num), g) for g in good if g.split("-")[0] == ref and g.split("-")[1] == course]
    if not same:
        print("no neighbour on course for", k); continue
    nb = min(same)[1]; xn = C[nb]
    lon, lat = x["geom_center_pos"]; lonn, latn = xn["geom_center_pos"]
    dx, dy = np.subtract(world(lat, lon, 17), world(latn, lonn, 17))
    Hp = np.array([[1, 0, dx], [0, 1, dy], [0, 0, 1]]) @ np.array(good[nb]["H"])
    P = photo(ref, course, num)
    msgs = []
    H2, s, d, inf = refine(P, Hp, lat, lon, log=msgs.append)
    rec = {"meta": {kk: x[kk] for kk in ("specification_id", "reference_number", "course_number", "photo_number", "search_date", "color_type_name", "scale", "city_name")},
           "size": list(P.shape[:2]), "info": {"fallback_from": nb, **inf}, "log": msgs}
    if s is not None and inf.get("refine_inl", 0) >= 12 and inf.get("resid_med", 99) < 6 and centre_err(k, H2, P.shape[:2]) < 600:
        rec["H"] = H2.tolist(); rec["src"] = s.tolist(); rec["dst"] = d.tolist(); how = "refined"
    else:
        rec["H"] = Hp.tolist(); how = "neighbour only"
    G[k] = rec
    print(k, "from", nb, how, inf)
for k, r in G.items():
    if r.get("bad"): r.pop("H", None)
json.dump(G, open(D + "georef.json", "w", encoding="utf-8"), ensure_ascii=False)
