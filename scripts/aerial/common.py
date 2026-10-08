# Shared helpers for georeferencing GSI single-frame aerial photos onto Web Mercator.
import io, math, os, urllib.parse, urllib.request
import numpy as np, cv2
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"}
D = os.path.dirname(os.path.abspath(__file__)) + "/"
API = "https://service.gsi.go.jp/map-photos/app/api/photo?"
IMG = "https://service.gsi.go.jp/map-photos/contents/screen/mapphoto/img/"
def get(url, tries=4):
    for a in range(tries):
        try: return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()
        except Exception:
            if a == tries - 1: raise
def world(lat, lon, z):           # Web Mercator pixel coordinates at zoom z
    s = math.sin(math.radians(lat)); n = 256 * 2 ** z
    return (lon + 180) / 360 * n, (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n
def latlon(x, y, z):
    n = 256 * 2 ** z
    return math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n)))), x / n * 360 - 180
def ref_mosaic(lat, lon, half_m, z=15):
    """GSI latest ortho around a point: returns (BGR image, x0, y0) with x0/y0 the world pixel of the top-left corner."""
    cx, cy = world(lat, lon, z); mpp = 156543.03 * math.cos(math.radians(lat)) / 2 ** z; h = half_m / mpp
    tx0, ty0, tx1, ty1 = int((cx - h) // 256), int((cy - h) // 256), int((cx + h) // 256), int((cy + h) // 256)
    img = np.zeros(((ty1 - ty0 + 1) * 256, (tx1 - tx0 + 1) * 256, 3), np.uint8)
    for tx in range(tx0, tx1 + 1):
        for ty in range(ty0, ty1 + 1):
            p = D + f"ref/{z}_{tx}_{ty}.jpg"
            if not os.path.exists(p):
                os.makedirs(D + "ref", exist_ok=True)
                try: open(p, "wb").write(get(f"https://cyberjapandata.gsi.go.jp/xyz/seamlessphoto/{z}/{tx}/{ty}.jpg"))
                except Exception: continue
            t = cv2.imread(p)
            if t is not None: img[(ty - ty0) * 256:(ty - ty0 + 1) * 256, (tx - tx0) * 256:(tx - tx0 + 1) * 256] = t
    return img, tx0 * 256, ty0 * 256
def photo(ref_no, course, num, kind="standard"):
    p = D + f"photos/{ref_no}-{course}-{num}.jpg"
    if not os.path.exists(p):
        os.makedirs(D + "photos", exist_ok=True)
        open(p, "wb").write(get(IMG + urllib.parse.quote(f"aerialphotograph/空中写真/{ref_no}/{kind}/{course}/{ref_no}-{course}-{num}.jpg")))
    return cv2.imread(p)
BOXES = {   # coastal Miyagi boxes covered by the pre-quake photo layer: name -> (lat0, lat1, lon0, lon1)
    "気仙沼": (38.870, 38.940, 141.540, 141.640),
    "本吉": (38.770, 38.815, 141.485, 141.535),
    "歌津": (38.700, 38.730, 141.500, 141.540),
    "南三陸": (38.640, 38.700, 141.410, 141.480),
    "北上川河口": (38.540, 38.590, 141.380, 141.480),
    "女川": (38.420, 38.470, 141.420, 141.480),
    "石巻": (38.390, 38.460, 141.200, 141.400),
    "東松島": (38.350, 38.430, 141.100, 141.230),
    "松島": (38.355, 38.385, 141.040, 141.110),
    "塩竈・七ヶ浜・蒲生": (38.240, 38.335, 140.995, 141.100),
    "岩沼・亘理・山元": (37.890, 38.160, 140.875, 140.960),
}
