import sys, os, json
sys.path.insert(0, "scraper")
os.makedirs("probe/out", exist_ok=True)
import scrape
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); ctx = b.new_context(locale="lt-LT")
    pdfs, imgs, jsons, txt = scrape.crawl_viewer(ctx, "https://www.maxima.lt/leidiniai/kaledu_menuo", "Maxima", 0)
    open("probe/out/mx.txt", "w").write(txt)
    import leaflets
    res = leaflets.parse_maxima(txt, 2026)
    open("probe/out/mx_res.json", "w").write(json.dumps(res, ensure_ascii=False, indent=0))
