import asyncio, csv, random, aiohttp
from collections import Counter
from streetlevel import streetview as sv
import os
D=os.path.dirname(os.path.abspath(__file__)).replace("\\","/")+"/"
rows=list(csv.reader(open(D+"panos.csv",encoding="utf-8")))
known={r[0] for r in rows}
random.seed(7); sample=random.sample(rows,600)
foreign=Counter(); hist=Counter(); found={}
async def main():
    async with aiohttp.ClientSession() as s:
        sem=asyncio.Semaphore(32)
        async def get(pid):
            async with sem:
                try: return await sv.find_panorama_by_id_async(pid,s)
                except Exception: return None
        ps=await asyncio.gather(*[get(r[0]) for r in sample])
        cand=set()
        for p in ps:
            if not p: continue
            for h in (p.historical or []): hist[str(h.date)]+=1; cand.add(h.id)
            for n in (p.neighbors or [])+[l.pano for l in (p.links or [])]:
                if n.id not in known: cand.add(n.id)
        print("panos ok",sum(1 for p in ps if p),"historical dates",dict(hist),"unknown ids",len(cand))
        qs=await asyncio.gather(*[get(c) for c in cand])
        print("unknown id dates",Counter(str(q.date) for q in qs if q).most_common(20))
asyncio.run(main())
