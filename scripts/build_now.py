# For every 2008 panorama, find the nearest *current* Google road panorama and write the
# mapping as per-area JSON chunks (../now/<z13x>_<z13y>.json: {"2008 id": "current id"}).
# Current panoramas come from Street View coverage tiles, which list road imagery only
# (no indoor/underground levels and no user-uploaded photospheres).
import asyncio, aiohttp, csv, json, math, os, sys, time
from streetlevel import streetview as sv

D = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/") + "/"
OUT = D + "../now/"
CACHE = D + "coverage_cache.jsonl"
MAXD = 30.0      # metres
CONC = 32

def tile(lat, lon, z):
    n = 2 ** z
    s = math.radians(lat)
    return int((lon + 180) / 360 * n), int((1 - math.log(math.tan(s) + 1 / math.cos(s)) / math.pi) / 2 * n)

pts = [(r[0], float(r[1]), float(r[2])) for r in csv.reader(open(D + "panos.csv", encoding="utf-8")) if r[3].startswith("2008")]
need = set()
for _, la, lo in pts:
    x, y = tile(la, lo, 17)
    need.update((x + i, y + j) for i in (-1, 0, 1) for j in (-1, 0, 1))

cov = {}
if os.path.exists(CACHE):
    for line in open(CACHE, encoding="utf-8"):
        k, v = json.loads(line)
        cov[tuple(k)] = v
todo = [t for t in need if t not in cov]
print(f"points {len(pts)}  tiles needed {len(need)}  cached {len(cov)}  to fetch {len(todo)}", flush=True)

async def fetch_all():
    sem = asyncio.Semaphore(CONC)
    out = open(CACHE, "a", encoding="utf-8")
    done = 0
    t0 = time.time()
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=CONC)) as s:
        async def one(t):
            nonlocal done
            async with sem:
                for attempt in range(5):
                    try:
                        ps = await sv.get_coverage_tile_async(t[0], t[1], s)
                        break
                    except Exception:
                        await asyncio.sleep(2 ** attempt)
                else:
                    return
            v = [[p.id, round(p.lat, 7), round(p.lon, 7)] for p in ps]
            cov[t] = v
            out.write(json.dumps([list(t), v]) + "\n")
            done += 1
            if done % 2000 == 0:
                out.flush()
                print(f"  {done}/{len(todo)} tiles {time.time() - t0:.0f}s", flush=True)
        await asyncio.gather(*[one(t) for t in todo])
    out.close()

if todo:
    asyncio.run(fetch_all())

chunks = {}
dist_hist = [0] * 4
miss = 0
for pid, la, lo in pts:
    x, y = tile(la, lo, 17)
    best, bd = None, MAXD
    for i in (-1, 0, 1):
        for j in (-1, 0, 1):
            for cid, cla, clo in cov.get((x + i, y + j), []):
                d = math.hypot((cla - la) * 111320, (clo - lo) * 111320 * math.cos(math.radians(la)))
                if d < bd:
                    best, bd = cid, d
    if best is None:
        miss += 1
        continue
    dist_hist[min(3, int(bd // 10))] += 1
    cx, cy = tile(la, lo, 13)
    chunks.setdefault(f"{cx}_{cy}", {})[pid] = best

os.makedirs(OUT, exist_ok=True)
for f in os.listdir(OUT):
    os.remove(OUT + f)
for k, v in chunks.items():
    with open(OUT + k + ".json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(v, f, separators=(",", ":"))
print(f"matched {len(pts) - miss}  unmatched {miss}  distance <10m {dist_hist[0]}  10-20m {dist_hist[1]}  20-30m {dist_hist[2]}  chunks {len(chunks)}")
