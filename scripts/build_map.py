import json
import os
exec(open(os.path.dirname(os.path.abspath(__file__))+"/mcrawl.py").read().split("CONC=int")[0])
W=D+"../"
import csv
allp=[dict(id=r[0],lat=float(r[1]),lon=float(r[2]),date=r[3]) for r in csv.reader(open(D+"panos.csv",encoding="utf-8"))]
seen=set(); d=[]; outside=0
for o in allp:
    if not o["date"].startswith("2008") or o["id"] in seen: continue
    seen.add(o["id"])
    d.append(o)
months=sorted({o["date"] for o in d}); ml={m:f"{m[:4]}年{int(m[5:])}月" for m in months}
blat=round(min(o["lat"] for o in d),3); blon=round(min(o["lon"] for o in d),3)
J=lambda x: json.dumps(x,separators=(",",":"))
rep={"__IDS__":J([o["id"] for o in d]),"__LAT__":J([round((o["lat"]-blat)*1e6) for o in d]),
 "__LON__":J([round((o["lon"]-blon)*1e6) for o in d]),"__MON__":J([months.index(o["date"]) for o in d]),
 "__MONTHS__":json.dumps([ml[m] for m in months],ensure_ascii=False),"__BLAT__":str(blat),"__BLON__":str(blon),
 "__N__":f"{len(d):,}","__OUTLINE__":J(g),"__PROBES__":open(D+"probes.json",encoding="utf-8").read(),
 "__PREQ_BOXES__":open(D+"prequake_boxes.json",encoding="utf-8").read() if os.path.exists(D+"prequake_boxes.json") else "[]"}
h=open(D+"map_template.html",encoding="utf-8").read().replace("2008年のストリートビュー（","2008年のストリートビュー 宮城・山形・福島・岩手・茨城（")
for k,v in rep.items(): h=h.replace(k,v)
open(W+"index.html","w",encoding="utf-8").write(h)
with open(W+"sv2008_panoids.csv","w",encoding="utf-8",newline="\n") as z:
    z.write("panoid,lat,lon,date,url\n")
    for o in d:
        z.write(f'{o["id"]},{o["lat"]},{o["lon"]},{o["date"]},https://www.google.com/maps/@{o["lat"]},{o["lon"]},3a,75y,0h,90t/data=!3m4!1e1!3m2!1s{o["id"]}!2e0\n')
print("points",len(d),{ml[m]:sum(o["date"]==m for o in d) for m in months})
