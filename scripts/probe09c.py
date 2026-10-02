import asyncio, aiohttp, sys, time
from collections import Counter
from streetlevel import streetview as sv
la,lo,LIMIT=float(sys.argv[1]),float(sys.argv[2]),int(sys.argv[3])
async def main():
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=32)) as s:
        seeds=[]
        for p in sv.get_coverage_tile_by_latlon(la,lo)[:30]:
            q=await sv.find_panorama_by_id_async(p.id,s)
            for h in (q.historical or [])+[q]:
                if str(h.date).startswith("2009"): seeds.append(h.id)
        seen=set(seeds); Q=asyncio.Queue(); [Q.put_nowait(x) for x in seeds]
        dates=Counter(); early=[]; n=[0]; t0=time.time()
        async def w():
            while True:
                pid=await Q.get()
                try:
                    if n[0]>=LIMIT: continue
                    try: p=await sv.find_panorama_by_id_async(pid,s)
                    except Exception: p=None
                    if not p: continue
                    n[0]+=1; d=str(p.date); dates[d]+=1
                    if d<"2009-08" and not early: print("EARLY FOUND",p.id,d,p.lat,p.lon,flush=True)
                    if d<"2009-08": early.append(p.id)
                    if d.startswith("2009"):
                        for l in (p.links or []):
                            if l.pano.id not in seen: seen.add(l.pano.id); Q.put_nowait(l.pano.id)
                finally: Q.task_done()
        ws=[asyncio.create_task(w()) for _ in range(32)]
        await Q.join(); [x.cancel() for x in ws]
        print(f"visited {n[0]} in {time.time()-t0:.0f}s dates={dict(sorted(dates.items()))} early={len(early)}")
asyncio.run(main())
