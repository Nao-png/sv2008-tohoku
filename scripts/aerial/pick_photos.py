# Pick the pre-quake colour photos needed to cover each town box: every ~250 m grid point takes the photo whose
# centre is nearest (only photos from one survey per box, preferring the newest), so the mosaic needs few frames.
import json, math, urllib.parse
from common import *
def search(lat0, lat1, lon0, lon1):
    out = {}
    la = lat0 - 0.03
    while la < lat1 + 0.03:
        lo = lon0 - 0.04
        while lo < lon1 + 0.04:
            q = urllib.parse.urlencode({"search_date_from": "2001", "search_date_to": "2011", "lon_min": f"{lo:.3f}", "lon_max": f"{lo+0.04:.3f}", "lat_min": f"{la:.3f}", "lat_max": f"{la+0.03:.3f}"})
            r = json.loads(get(API + q))["results"]
            for x in r:
                if x["search_date"] < "2011-03-11" and x["search_date"] >= "2001-01-01" and x["reference_number"] != "CTO20081":
                    out[x["specification_id"]] = x
            lo += 0.04
        la += 0.03
    return out
d = lambda a, b: math.hypot((a[0] - b[0]) * 111, (a[1] - b[1]) * 87)
chosen = {}
for name, (la0, la1, lo0, lo1) in BOXES.items():
    ph = search(la0, la1, lo0, lo1)
    surveys = sorted({x["reference_number"] for x in ph.values()}, key=lambda r: (any(x["color_type_name"] == "カラー" for x in ph.values() if x["reference_number"] == r), max(x["search_date"] for x in ph.values() if x["reference_number"] == r)), reverse=True)
    print(name, "photos", len(ph), "surveys", surveys)
    pick = set(); miss = 0
    la = la0
    while la <= la1:
        lo = lo0
        while lo <= lo1:
            best = None
            for ref in surveys:                         # newest survey first; fall back if it doesn't reach
                c = [x for x in ph.values() if x["reference_number"] == ref and d((la, lo), (x["geom_center_pos"][1], x["geom_center_pos"][0])) < 0.23 * x["scale"] / 1000 * 0.35]
                if c: best = min(c, key=lambda x: d((la, lo), (x["geom_center_pos"][1], x["geom_center_pos"][0]))); break
            if best: pick.add(best["specification_id"]); chosen[best["specification_id"]] = best
            else: miss += 1
            lo += 0.0029
        la += 0.00225
    print("  chosen", len(pick), "uncovered grid points", miss)
json.dump(list(chosen.values()), open(D + "chosen.json", "w", encoding="utf-8"), ensure_ascii=False)
print("total photos", len(chosen))
