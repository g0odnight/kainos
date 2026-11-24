import json, pathlib, re, sys, types, datetime, collections
sys.path.insert(0, "scraper")
from playwright.sync_api import sync_playwright
import scrape
out = pathlib.Path("probe/out"); out.mkdir(parents=True, exist_ok=True)
rep = {}
with sync_playwright() as pw:
    b = pw.chromium.launch(); ctx = b.new_context(locale="lt-LT", user_agent=scrape.UA)
    base = "https://www.akcijuseklys.lt"
    for slug in ("maxima", "lidl", "iki", "rimi", "norfa", "promo"):
        r = ctx.request.get(f"{base}/parduotuve/{slug}", timeout=60000)
        links = list(dict.fromkeys(re.findall(r'href="(/parduotuve/' + slug + r'/br_[0-9a-f]+)"', r.text())))
        rep[slug] = {"status": r.status, "links": len(links), "leaflets": []}
        today = datetime.date.today().isoformat()
        for ln in links[:25]:
            h = ctx.request.get(base + ln, timeout=60000).text()
            t = re.search(r'id="viewer-title"[^>]*>(.*?)<', h)
            d = scrape.ak_leaflet(h) or []
            m = next((m for m in re.finditer(r"<script[^>]*>(\{\"pages\".*?)</script>", h, re.S)), None)
            raw = json.loads(m.group(1))["deals"] if m else []
            live = [x for x in d if not x[3] or x[3] >= today]
            rep[slug]["leaflets"].append({"ln": ln, "title": t.group(1) if t else "", "deals": len(raw), "priced": len(d), "live": len(live),
                "dates": collections.Counter((x[2], x[3]) for x in d).most_common(2), "sample": live[:8]})
    b.close()
(out / "ak.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1))
for s, v in rep.items():
    print(s, v["status"], v["links"], [(l["title"][:40], l["deals"], l["live"]) for l in v["leaflets"]])
