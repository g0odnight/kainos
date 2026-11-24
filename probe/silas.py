import json, pathlib, re, sys, datetime
sys.path.insert(0, "scraper")
from playwright.sync_api import sync_playwright
import scrape
out = pathlib.Path("probe/out"); out.mkdir(parents=True, exist_ok=True)
today = datetime.date.today().isoformat(); rep = {}
with sync_playwright() as pw:
    b = pw.chromium.launch(); ctx = b.new_context(locale="lt-LT")
    base = "https://www.akcijuseklys.lt"
    for slug in ("maxima", "rimi", "iki", "norfa", "promo", "silas", "vynoteka", "lidl"):
        h = ctx.request.get(f"{base}/parduotuve/{slug}", timeout=60000).text()
        links = list(dict.fromkeys(re.findall(r'href="(/parduotuve/' + slug + r'/br_[0-9a-f]+)"', h)))
        rows = []
        for ln in links[:40]:
            hh = ctx.request.get(base + ln, timeout=60000).text()
            t = re.search(r"<title>(.*?)</title>", hh, re.S)
            m = next((m for m in re.finditer(r"<script[^>]*>(\{\"pages\".*?)</script>", hh, re.S)), None)
            deals = json.loads(m.group(1))["deals"] if m else []
            to = max(((x.get("activeTo") or "")[:10] for x in deals), default="")
            fr = min(((x.get("activeFrom") or "9")[:10] for x in deals), default="")
            np = re.search(r">\s*1\s*/\s*(\d+)\s*<", hh)
            rows.append((ln, (t.group(1).strip()[:80] if t else ""), fr, to, len(deals), sum(1 for x in deals if x.get("promoPrice")), np.group(1) if np else "?"))
        rep[slug] = rows
    b.close()
(out / "leaflets.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1))
for s, rows in rep.items():
    print("=====", s, len(rows))
    for r in rows: print("  ", r[2], "→", r[3], "|", r[4], "pasiūl.,", r[5], "su kaina,", r[6], "psl. |", r[1])
