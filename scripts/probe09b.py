import asyncio, aiohttp
from collections import Counter
from streetlevel import streetview as sv
cities={"仙台":(38.2600,140.8820),"名取":(38.1739,140.9329),"東京":(35.6812,139.7671),"月島":(35.6640,139.7840),"千葉":(35.6110,140.1170),"横浜":(35.4437,139.6380),"大阪":(34.7025,135.4959),"京都":(35.0116,135.7681),"神戸":(34.6901,135.1955),"札幌":(43.0687,141.3508),"函館":(41.7687,140.7288),"滋賀":(35.0045,135.8686)}
async def main():
    async with aiohttp.ClientSession() as s:
        sem=asyncio.Semaphore(32)
        async def get(pid):
            async with sem:
                try: return await sv.find_panorama_by_id_async(pid,s)
                except Exception: return None
        for name,(la,lo) in cities.items():
            tile=sv.get_coverage_tile_by_latlon(la,lo)
            ps=await asyncio.gather(*[get(p.id) for p in tile[:25]])
            hd=Counter(); ids09=set()
            for p in ps:
                if not p: continue
                for h in (p.historical or [])+[p]:
                    d=str(h.date); hd[d[:4]]+=1
                    if d.startswith("2009") or d.startswith("2008"): ids09.add(h.id)
            # follow links of 2008/2009 panos and record dates of linked panos
            p09=await asyncio.gather(*[get(i) for i in ids09])
            own={str(p.date) for p in p09 if p}
            lk=set(l.pano.id for p in p09 if p for l in (p.links or []))
            lp=await asyncio.gather(*[get(i) for i in list(lk)[:150]])
            ld=Counter(str(q.date) for q in lp if q)
            print(f"{name}: tile={len(tile)} years={dict(sorted(hd.items()))} 2008-09 months={sorted(own)} linked->{dict(sorted(ld.items()))}",flush=True)
asyncio.run(main())
