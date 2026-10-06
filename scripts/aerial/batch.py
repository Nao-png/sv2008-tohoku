# Georeference every chosen photo; results go to georef.json (homography + inlier correspondences per photo).
import json, os, time, traceback
import numpy as np
from common import *
from georef import georef
from refine import refine
C = json.load(open(D + "chosen.json", encoding="utf-8"))
out = json.load(open(D + "georef.json", encoding="utf-8")) if os.path.exists(D + "georef.json") else {}
log = open(D + "batch.log", "a", encoding="utf-8")
def L(s): log.write(time.strftime("%H:%M:%S ") + s + "\n"); log.flush()
for i, x in enumerate(C):
    key = f'{x["reference_number"]}-{x["course_number"]}-{x["photo_number"]}'
    if key in out: continue
    lon, lat = x["geom_center_pos"]
    try:
        P = photo(x["reference_number"], x["course_number"], x["photo_number"])
        msgs = []
        H, info = georef(P, lat, lon, frame_m=0.23 * x["scale"], log=msgs.append)
        rec = {"meta": {k: x[k] for k in ("specification_id", "reference_number", "course_number", "photo_number", "search_date", "color_type_name", "scale", "city_name")}, "info": info, "log": msgs}
        if H is not None:
            H2, s, d, inf2 = refine(P, H, lat, lon, log=msgs.append)
            rec["info"].update(inf2); rec["H"] = H2.tolist()
            if s is not None: rec["src"] = s.tolist(); rec["dst"] = d.tolist()
            rec["size"] = list(P.shape[:2])
        out[key] = rec
        L(f"{i+1}/{len(C)} {key} {x['city_name']} {'OK' if 'H' in rec else 'FAIL'} {rec['info']} | {' / '.join(msgs)}")
    except Exception as e:
        out[key] = {"meta": {"reference_number": x["reference_number"]}, "error": repr(e)}
        L(f"{i+1}/{len(C)} {key} ERROR {traceback.format_exc()[-300:]}")
    json.dump(out, open(D + "georef.json", "w", encoding="utf-8"), ensure_ascii=False)
L("DONE")
