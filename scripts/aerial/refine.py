# Second pass: given H (photo px -> world px z17), match a dense grid of patches at z17 and return
# inlier correspondences (photo px, world px z17) for a residual-corrected warp.
import math, cv2, numpy as np
from common import *
from georef import edges
def refine(P, H, lat, lon, grid=17, ps=112, sr=40, log=print):
    h, w = P.shape[:2]
    G = cv2.cvtColor(P, cv2.COLOR_BGR2GRAY)
    # world bbox of the photo at z17
    corners = cv2.perspectiveTransform(np.float32([[[w*.06, h*.06]], [[w*.94, h*.06]], [[w*.94, h*.94]], [[w*.06, h*.94]]]), H)[:, 0]
    wx0, wy0 = corners.min(0) - 200; wx1, wy1 = corners.max(0) + 200
    clat, clon = latlon((wx0 + wx1) / 2, (wy0 + wy1) / 2, 17)
    half = max(wx1 - wx0, wy1 - wy0) / 2 * 156543.03 * math.cos(math.radians(clat)) / 2 ** 17
    R, rx0, ry0 = ref_mosaic(clat, clon, half, 17)
    Re = edges(cv2.cvtColor(R, cv2.COLOR_BGR2GRAY))
    Hr = np.array([[1, 0, -rx0], [0, 1, -ry0], [0, 0, 1]]) @ H          # photo px -> ref px
    W = edges(cv2.warpPerspective(G, Hr, (R.shape[1], R.shape[0])))   # photo warped into ref frame
    src, dst = [], []
    for fy in np.linspace(.1, .9, grid):
        for fx in np.linspace(.1, .9, grid):
            p = np.float32([[[w * fx, h * fy]]]); q = cv2.perspectiveTransform(p, Hr)[0, 0]
            x, y = int(q[0] - ps / 2), int(q[1] - ps / 2)
            if x - sr < 0 or y - sr < 0 or x + ps + sr > R.shape[1] or y + ps + sr > R.shape[0]: continue
            patch = W[y:y + ps, x:x + ps]
            if patch.std() < 0.04 or (patch == 0).mean() > .2: continue
            win = Re[y - sr:y + ps + sr, x - sr:x + ps + sr]
            res = cv2.matchTemplate(win, patch, cv2.TM_CCOEFF_NORMED)
            _, mx, _, l = cv2.minMaxLoc(res)
            if mx < 0.3: continue
            # peak must be distinct: second best outside a 6px radius
            r2 = res.copy(); cv2.circle(r2, l, 6, -1, -1)
            if mx - r2.max() < 0.04: continue
            dx, dy = l[0] - sr, l[1] - sr
            src.append(p[0, 0]); dst.append([q[0] + dx + rx0, q[1] + dy + ry0])
    src, dst = np.float32(src), np.float32(dst)
    if len(src) < 12: return H, None, None, {"refine_pts": len(src)}
    H2, inl = cv2.findHomography(src, dst, cv2.RANSAC, 12.0)
    inl = inl.ravel().astype(bool)
    pred = cv2.perspectiveTransform(src[inl][:, None], H2)[:, 0]
    resid = np.linalg.norm(pred - dst[inl], axis=1)
    log(f"refine pts {len(src)} inliers {inl.sum()} median resid {np.median(resid):.1f}px p90 {np.percentile(resid,90):.1f}px")
    return H2, src[inl], dst[inl], {"refine_pts": int(len(src)), "refine_inl": int(inl.sum()), "resid_med": float(np.median(resid))}
