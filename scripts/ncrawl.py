# Nationwide BFS over 2008 panorama links. Streams results to panos.csv; resumable via frontier.json.
import asyncio, json, os, time, sys
from collections import Counter
import aiohttp
from streetlevel import streetview as sv
import os
D=os.path.dirname(os.path.abspath(__file__)).replace("\\","/")+"/"
CSV=D+"panos.csv"; FR=D+"frontier.json"; LOG=D+"ncrawl.log"
CONC=int(sys.argv[1]) if len(sys.argv)>1 else 32
log=open(LOG,"a",encoding="utf-8")
def L(s): log.write(time.strftime("%H:%M:%S ")+s+"\n"); log.flush()
seen=set(); pending=[]
if not os.path.exists(CSV):
    # bootstrap from the Miyagi crawl: everything known is seen; out-of-Miyagi 2008 points are the frontier
    exec(open(D+"mcrawl.py").read().split("CONC=int")[0])
    allp=json.load(open(D+"mstate.json"))["out"]
    with open(CSV,"w",encoding="utf-8") as f:
        for o in allp:
            if o["id"] in seen: continue
            seen.add(o["id"])
            if o["date"].startswith("2008") and not inside(o["lat"],o["lon"]): pending.append(o["id"])
            else: f.write(f'{o["id"]},{o["lat"]},{o["lon"]},{o["date"]}\n')
    del allp
else:
    with open(CSV,encoding="utf-8") as f:
        for line in f: seen.add(line.split(",",1)[0])
    pending=json.load(open(FR)) if os.path.exists(FR) else []
    seen.update(pending)
L(f"start seen={len(seen)} frontier={len(pending)} conc={CONC}")
q=asyncio.Queue()
for p in pending: q.put_nowait(p)
inflight=set(); out=open(CSV,"a",encoding="utf-8")
st=dict(n=0,err=0,giveup=0,months=Counter()); t0=time.time()
def save_frontier():
    out.flush(); tmp=FR+".tmp"; json.dump(list(q._queue)+list(inflight),open(tmp,"w")); os.replace(tmp,FR)
async def worker(session):
    while True:
        pid=await q.get(); inflight.add(pid)
        try:
            p=None
            for attempt in range(8):
                try: p=await sv.find_panorama_by_id_async(pid,session); break
                except Exception as e:
                    st["err"]+=1
                    if st["err"]%50==1: L(f"error #{st['err']}: {repr(e)[:120]}")
                    await asyncio.sleep(min(120,2**attempt*2))
            if p is None:
                st["giveup"]+=1; L(f"giveup {pid}"); continue
            d=str(p.date)
            if not d.startswith("2008"):
                continue   # a searched seed can turn out to be newer imagery; keep panos.csv 2008-only
            out.write(f"{p.id},{p.lat},{p.lon},{d}\n")
            st["n"]+=1; st["months"][d]+=1
            for l in (p.links or []):
                if l.pano.id not in seen:
                    seen.add(l.pano.id); q.put_nowait(l.pano.id)
            if st["n"]%20000==0:
                save_frontier(); el=time.time()-t0
                L(f"new {st['n']} total {len(seen)} queue {q.qsize()} errors {st['err']} {st['n']/el:.0f}/s last=({p.lat:.3f},{p.lon:.3f})")
        finally:
            inflight.discard(pid); q.task_done()
async def main():
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=CONC)) as s:
        ws=[asyncio.create_task(worker(s)) for _ in range(CONC)]
        await q.join()
        for w in ws: w.cancel()
asyncio.run(main()); save_frontier(); out.close()
L(f"DONE new {st['n']} total {len(seen)} months {dict(st['months'])} errors {st['err']} giveup {st['giveup']} {time.time()-t0:.0f}s")
