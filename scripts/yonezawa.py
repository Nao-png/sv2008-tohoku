import asyncio, aiohttp, csv
from collections import Counter
from streetlevel import streetview as sv
import os
D=os.path.dirname(os.path.abspath(__file__)).replace("\\","/")+"/"
rows={r[0]:r for r in csv.reader(open(D+"panos.csv",encoding="utf-8"))}
nov=[r for r in rows.values() if r[3]=="2008-11"]
print("2008-11 count",len(nov))
async def main():
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=32)) as s:
        sem=asyncio.Semaphore(32)
        async def get(pid):
            async with sem:
                try: return await sv.find_panorama_by_id_async(pid,s)
                except Exception: return None
        ps=await asyncio.gather(*[get(r[0]) for r in nov])
        deg=Counter(); bridge=[]; ends=[]; other=Counter(); hist=Counter()
        for p in ps:
            if not p: continue
            ls=p.links or []; deg[len(ls)]+=1
            for h in p.historical or []: hist[str(h.date)]+=1
            for l in ls:
                d=rows[l.pano.id][3] if l.pano.id in rows else "UNKNOWN"
                if d!="2008-11": bridge.append((p.id,p.lat,p.lon,l.pano.id,d)); other[d]+=1
            if len(ls)<=1: ends.append((round(p.lat,4),round(p.lon,4)))
        print("link-degree",dict(sorted(deg.items())),"historical",dict(hist))
        print("links leaving 2008-11:",dict(other))
        for b in bridge[:10]: print("  bridge",b)
        print("dead ends",len(ends),ends[:40])
        # what does today's time machine look like around Yonezawa?
        for name,(la,lo) in {"米沢駅":(37.9097,140.1290),"米沢中心":(37.9222,140.1167),"高畠":(37.9970,140.1890)}.items():
            t=sv.get_coverage_tile_by_latlon(la,lo)
            qs=await asyncio.gather(*[get(x.id) for x in t[:25]])
            ys=Counter(str(h.date)[:7] for q in qs if q for h in (q.historical or [])+[q])
            print(name,"oldest dates",sorted(ys)[:6],"tile",len(t))
asyncio.run(main())
