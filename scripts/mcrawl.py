# Miyagi-wide BFS over 2008 panorama links; resumable (state saved periodically)
import asyncio, json, os, time, sys
from collections import Counter
import aiohttp
from streetlevel import streetview as sv
import os
D=os.path.dirname(os.path.abspath(__file__)).replace("\\","/")+"/"
g=json.load(open(D+"miyagi.json"))[0]["geojson"]
POLYS=[g["coordinates"]] if g["type"]=="Polygon" else g["coordinates"]
def inring(x,y,r):
    c=False; j=len(r)-1
    for i in range(len(r)):
        xi,yi=r[i]; xj,yj=r[j]
        if (yi>y)!=(yj>y) and x<(xj-xi)*(y-yi)/(yj-yi)+xi: c=not c
        j=i
    return c
def inside(lat,lon): return any(inring(lon,lat,p[0]) and not any(inring(lon,lat,h) for h in p[1:]) for p in POLYS)
CONC=int(sys.argv[1]); LIMIT=int(sys.argv[2])
ST=D+"mstate.json"
if os.path.exists(ST):
    s=json.load(open(ST)); out=s["out"]; pending=s["queue"]
else:
    out=[]; pending=["_i_CSkGo_5OjNRInnuK_jw"]
seen={o["id"] for o in out}|set(pending)
q=asyncio.Queue()
for p in pending: q.put_nowait(p)
inflight=set(); ERR=[]; t0=time.time(); n0=len(out)
log=open(D+"mcrawl.log","a",encoding="utf-8")
def save():
    tmp=ST+".tmp"; json.dump({"out":out,"queue":list(q._queue)+list(inflight)},open(tmp,"w")); os.replace(tmp,ST)
async def worker(session):
    while True:
        pid=await q.get(); inflight.add(pid)
        try:
            if len(out)>=LIMIT: continue
            p=None
            for attempt in range(6):
                try: p=await sv.find_panorama_by_id_async(pid,session); break
                except Exception as e:
                    ERR.append(repr(e)[:100]); await asyncio.sleep(min(60,2**attempt*2))
            if p is None:
                if attempt==5: log.write(f"giveup {pid}\n")
                continue
            d=str(p.date)
            out.append(dict(id=p.id,lat=p.lat,lon=p.lon,date=d))
            if d.startswith("2008") and inside(p.lat,p.lon):
                for l in (p.links or []):
                    if l.pano.id not in seen:
                        seen.add(l.pano.id); q.put_nowait(l.pano.id)
            if len(out)%20000==0:
                save(); el=time.time()-t0
                log.write(f"{len(out)} queue {q.qsize()} errors {len(ERR)} {el:.0f}s {(len(out)-n0)/el:.0f}/s\n"); log.flush()
        finally:
            inflight.discard(pid); q.task_done()
async def main():
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=CONC)) as s:
        ws=[asyncio.create_task(worker(s)) for _ in range(CONC)]
        await q.join()
        for w in ws: w.cancel()
asyncio.run(main()); save()
log.write(f"DONE {len(out)} {dict(Counter(o['date'] for o in out))} errors {len(ERR)} {Counter(ERR).most_common(3)} {time.time()-t0:.0f}s\n"); log.close()
print("DONE", len(out))
