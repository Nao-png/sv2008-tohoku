# Georeference one GSI single-frame aerial photo against the GSI latest ortho:
#  coarse: edge-image template matching over rotation x scale at ~8 m/px around the nominal footprint
#  fine:   a grid of patches matched at ~2 m/px, then a RANSAC homography photo-pixel -> world-pixel (zoom 17)
import math, cv2, numpy as np
from common import *
def edges(g):
    g = cv2.GaussianBlur(g, (0, 0), 1.0)
    m = cv2.magnitude(cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1))
    return cv2.normalize(np.sqrt(m), None, 0, 1, cv2.NORM_MINMAX)
def rot_scale(img, ang, s):
    h, w = img.shape[:2]; M = cv2.getRotationMatrix2D((w / 2, h / 2), ang, s)
    c, si = abs(M[0, 0]), abs(M[0, 1]); nw, nh = int(h * si + w * c), int(h * c + w * si)
    M[0, 2] += nw / 2 - w / 2; M[1, 2] += nh / 2 - h / 2
    return cv2.warpAffine(img, M, (nw, nh)), M
def georef(P, lat, lon, frame_m=4600, margin_m=2500, rots=(0, 90, 180, 270), log=print):
    """Returns (H, info) with H mapping photo pixels -> world pixels at zoom 17, or (None, info)."""
    h, w = P.shape[:2]
    crop = (int(h * .06), int(h * .94), int(w * .06), int(w * .94))       # drop film border / fiducials
    Pc = cv2.cvtColor(P[crop[0]:crop[1], crop[2]:crop[3]], cv2.COLOR_BGR2GRAY)
    # coarse
    zc = 14; mppc = 156543.03 * math.cos(math.radians(lat)) / 2 ** zc
    R, rx0, ry0 = ref_mosaic(lat, lon, frame_m / 2 + margin_m, zc)
    Re = edges(cv2.cvtColor(R, cv2.COLOR_BGR2GRAY))
    base = frame_m / w / mppc                                             # photo px -> coarse ref px
    Pe0 = edges(cv2.resize(Pc, None, fx=base, fy=base, interpolation=cv2.INTER_AREA))
    best = (-1,)
    for r0 in rots:
        for dr in range(-10, 11, 2):
            for s in (0.84, 0.9, 0.96, 1.02, 1.08, 1.14):
                T, M = rot_scale(Pe0, r0 + dr, s)
                ch, cw = T.shape[0] // 2, T.shape[1] // 2                 # inner 70% of the rotated frame
                ry, rx = int(ch * .7), int(cw * .7)
                Tm = T[ch - ry: ch + ry, cw - rx: cw + rx]
                if Tm.std() < 0.02: continue                              # all water / featureless
                if Tm.shape[0] >= Re.shape[0] or Tm.shape[1] >= Re.shape[1]: continue
                res = np.nan_to_num(cv2.matchTemplate(Re, Tm, cv2.TM_CCOEFF_NORMED), nan=-1.0)
                res[res > 0.999] = -1.0                                   # degenerate (flat) windows
                _, mx, _, loc = cv2.minMaxLoc(res)
                if mx > best[0]: best = (mx, r0 + dr, s, loc, M, (ch - ry, cw - rx))
    score, ang, s, loc, M, (oy, ox) = best
    # similarity: cropped-photo px -> coarse ref px
    A = np.vstack([M, [0, 0, 1]]) @ np.diag([base, base, 1])
    A = np.array([[1, 0, loc[0] - ox], [0, 1, loc[1] - oy], [0, 0, 1]]) @ A
    log(f"coarse score {score:.3f} rot {ang} scale {s}")
    if score < 0.12: return None, {"coarse": score}
    # fine at zoom 16 (~1.9 m/px)
    zf = 16; k = 2 ** (zf - zc)
    Rf, fx0, fy0 = ref_mosaic(lat, lon, frame_m / 2 + margin_m, zf)
    Rfe = edges(cv2.cvtColor(Rf, cv2.COLOR_BGR2GRAY))
    # world(zf) = k*(world(zc)) ; coarse ref px -> world zc = +rx0,ry0 ; fine ref px = world zf - fx0
    C2F = np.array([[k, 0, k * rx0 - fx0], [0, k, k * ry0 - fy0], [0, 0, 1]]) @ A   # cropped-photo px -> fine ref px
    sc = math.sqrt(abs(np.linalg.det(C2F[:2, :2])))                            # photo px per fine px (inverse)
    Pf = edges(cv2.resize(Pc, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA))
    # Pf px -> fine ref px:  C2F @ diag(1/sc)
    G = C2F @ np.diag([1 / sc, 1 / sc, 1])
    src, dst = [], []
    ps, sr = 96, 48
    for gy in np.linspace(ps, Pf.shape[0] - 2 * ps, 9):
        for gx in np.linspace(ps, Pf.shape[1] - 2 * ps, 9):
            gx, gy = int(gx), int(gy)
            patch = Pf[gy:gy + ps, gx:gx + ps]
            if patch.std() < 0.03: continue
            cxy = G @ np.array([gx + ps / 2, gy + ps / 2, 1]); cx, cy = cxy[0] / cxy[2], cxy[1] / cxy[2]
            # rotate patch into ref orientation using the coarse affine part
            Mloc = np.hstack([G[:2, :2], np.zeros((2, 1))])
            off = np.array([ps / 2, ps / 2]) - G[:2, :2] @ np.array([ps / 2, ps / 2]); Mloc[:, 2] = off
            pr = cv2.warpAffine(patch, Mloc, (ps, ps))
            x0, y0 = int(cx - ps / 2 - sr), int(cy - ps / 2 - sr)
            if x0 < 0 or y0 < 0 or x0 + ps + 2 * sr > Rfe.shape[1] or y0 + ps + 2 * sr > Rfe.shape[0]: continue
            win = Rfe[y0:y0 + ps + 2 * sr, x0:x0 + ps + 2 * sr]
            res = cv2.matchTemplate(win, pr[16:-16, 16:-16], cv2.TM_CCOEFF_NORMED)
            _, mx, _, l = cv2.minMaxLoc(res)
            if mx < 0.25: continue
            mx_x, mx_y = x0 + l[0] + 16 + ps / 2 - 16, y0 + l[1] + 16 + ps / 2 - 16
            src.append([gx + ps / 2, gy + ps / 2]); dst.append([mx_x, mx_y])
    if len(src) < 8: log(f"fine: only {len(src)} patches"); return None, {"coarse": score, "patches": len(src)}
    src, dst = np.float32(src), np.float32(dst)
    Hf, inl = cv2.findHomography(src, dst, cv2.RANSAC, 4.0)
    ni = int(inl.sum()) if inl is not None else 0
    log(f"fine patches {len(src)} inliers {ni}")
    if Hf is None or ni < 10: return None, {"coarse": score, "patches": len(src), "inliers": ni}
    # full photo px -> cropped px -> Pf px -> fine ref px -> world z16 -> world z17
    Tcrop = np.array([[1, 0, -crop[2]], [0, 1, -crop[0]], [0, 0, 1]])
    H = np.diag([2, 2, 1]) @ np.array([[1, 0, fx0], [0, 1, fy0], [0, 0, 1]]) @ Hf @ np.diag([sc, sc, 1]) @ Tcrop
    return H, {"coarse": score, "patches": len(src), "inliers": ni}
if __name__ == "__main__":
    import sys
    P = photo("CTO20061X", "C9", 17)
    H, info = georef(P, 38.3075, 141.016972)
    print(info)
    if H is not None:
        lat, lon = 38.3075, 141.016972
        R, x0, y0 = ref_mosaic(lat, lon, 3000, 16)
        Hr = np.array([[1, 0, -x0], [0, 1, -y0], [0, 0, 1]]) @ np.diag([.5, .5, 1]) @ H
        W = cv2.warpPerspective(P, Hr, (R.shape[1], R.shape[0]))
        cv2.imwrite(D + "proto_blend.jpg", cv2.addWeighted(R, .5, W, .5, 0)[::3, ::3])
