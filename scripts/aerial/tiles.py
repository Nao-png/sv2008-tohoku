# Build Web Mercator tiles from the georeferenced photos: each output pixel takes the photo whose centre is nearest
# (colour photos preferred over monochrome), mapped through the homography plus a smooth residual correction.
import json, math, os, sys
import numpy as np, cv2
from scipy.interpolate import RBFInterpolator
from common import *

ZMAX = int(sys.argv[1]) if len(sys.argv) > 1 else 17
OUT = sys.argv[2] if len(sys.argv) > 2 else D + "tiles"
QUALITY = 70
G = json.load(open(D + "georef.json", encoding="utf-8"))
ph = []
for key, r in G.items():
    if "H" not in r: continue
    H = np.array(r["H"]); h, w = r["size"]
    rbf = None
    if r.get("src") and len(r["src"]) >= 12:
        s = np.float32(r["src"]); dd = np.float32(r["dst"])
        pred = cv2.perspectiveTransform(s[:, None], H)[:, 0]
        rbf = RBFInterpolator(pred.astype(np.float64), (dd - pred).astype(np.float64), kernel="thin_plate_spline", smoothing=50.0)
    c = cv2.perspectiveTransform(np.float32([[[w / 2, h / 2]]]), H)[0, 0]
    corners = cv2.perspectiveTransform(np.float32([[[w*.085, h*.085]], [[w*.915, h*.085]], [[w*.915, h*.915]], [[w*.085, h*.915]]]), H)[:, 0]
    ph.append(dict(key=key, H=H, Hi=np.linalg.inv(H), rbf=rbf, size=(h, w), c=c, bb=(*corners.min(0), *corners.max(0)),
                   mono=r["meta"].get("color_type_name") == "モノクロ", img=None))
print("photos usable", len(ph), "of", len(G), flush=True)
def img(p):
    if p["img"] is None:
        m = p["key"].split("-"); p["img"] = photo(m[0], m[1], int(m[2]))
    return p["img"]
def tile17(tx, ty):
    x0, y0 = tx * 256, ty * 256
    cand = [p for p in ph if p["bb"][0] < x0 + 256 and p["bb"][2] > x0 and p["bb"][1] < y0 + 256 and p["bb"][3] > y0]
    if not cand: return None
    yy, xx = np.mgrid[0:256, 0:256].astype(np.float64)
    W = np.stack([xx.ravel() + x0 + .5, yy.ravel() + y0 + .5], 1)
    best = np.full(65536, np.inf); out = np.zeros((65536, 3), np.uint8); have = np.zeros(65536, bool)
    for p in cand:
        q = W - p["rbf"](W) if p["rbf"] is not None else W
        pp = cv2.perspectiveTransform(q[:, None].astype(np.float32), p["Hi"])[:, 0]
        h, w = p["size"]
        ok = (pp[:, 0] > w * .085) & (pp[:, 0] < w * .915) & (pp[:, 1] > h * .085) & (pp[:, 1] < h * .915)   # skip film border, fiducials and data strip
        if not ok.any(): continue
        dist = np.hypot(W[:, 0] - p["c"][0], W[:, 1] - p["c"][1]) + (4000 if p["mono"] else 0)
        if not (ok & (dist < best)).any(): continue
        mx = pp[:, 0].reshape(256, 256).astype(np.float32); my = pp[:, 1].reshape(256, 256).astype(np.float32)
        t = cv2.remap(img(p), mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT).reshape(-1, 3)
        ok &= t.astype(np.int32).sum(1) > 45                      # black data strips / masked corners are not imagery
        take = ok & (dist < best)
        if not take.any(): continue
        out[take] = t[take]; best[take] = dist[take]; have |= take
    if not have.any(): return None
    a = np.where(have, 255, 0).astype(np.uint8)
    return np.dstack([out.reshape(256, 256, 3), a.reshape(256, 256)])
def save(z, x, y, im):
    p = f"{OUT}/{z}/{x}"; os.makedirs(p, exist_ok=True)
    if im[:, :, 3].min() == 255: cv2.imwrite(f"{p}/{y}.webp", im[:, :, :3], [cv2.IMWRITE_WEBP_QUALITY, QUALITY])
    else: cv2.imwrite(f"{p}/{y}.webp", im, [cv2.IMWRITE_WEBP_QUALITY, QUALITY])
done = {}
for name, (la0, la1, lo0, lo1) in BOXES.items():
    ax0, ay1 = world(la0, lo0, 17); ax1, ay0 = world(la1, lo1, 17)
    tx0, tx1, ty0, ty1 = int(ax0 // 256), int(ax1 // 256), int(ay0 // 256), int(ay1 // 256)
    n = 0
    for tx in range(tx0, tx1 + 1):
        for ty in range(ty0, ty1 + 1):
            if (tx, ty) in done: continue
            im = tile17(tx, ty); done[(tx, ty)] = im is not None
            if im is not None: save(17, tx, ty, im); n += 1
    print(name, "z17 tiles", n, flush=True)
    for p in ph: p["img"] = None          # free photo memory between towns
# pyramid
level = {k for k, v in done.items() if v}
for z in range(16, 11, -1):
    parents = {(x // 2, y // 2) for x, y in level}
    for px, py in parents:
        canvas = np.zeros((512, 512, 4), np.uint8)
        for dx in (0, 1):
            for dy in (0, 1):
                f = f"{OUT}/{z+1}/{px*2+dx}/{py*2+dy}.webp"
                if os.path.exists(f):
                    t = cv2.imread(f, cv2.IMREAD_UNCHANGED)
                    if t.shape[2] == 3: t = np.dstack([t, np.full(t.shape[:2], 255, np.uint8)])
                    canvas[dy*256:(dy+1)*256, dx*256:(dx+1)*256] = t
        small = cv2.resize(canvas, (256, 256), interpolation=cv2.INTER_AREA)
        small[:, :, 3] = np.where(small[:, :, 3] > 128, 255, 0)
        if small[:, :, 3].any(): save(z, px, py, small)
    level = parents
    if z <= ZMAX: pass
print("done", flush=True)
