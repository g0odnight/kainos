import re, sys, json, pathlib
sys.path.insert(0, "scraper")
from playwright.sync_api import sync_playwright
import iki
from promo import ocr_lines
out = pathlib.Path("probe/out"); out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as pw:
    b = pw.chromium.launch(); ctx = b.new_context(locale="lt-LT"); p = ctx.new_page()
    p.goto("https://manoakcijos.lt/parduotuves/silas", wait_until="domcontentloaded", timeout=90000)
    try: p.wait_for_load_state("networkidle", timeout=15000)
    except Exception: pass
    imgs = p.eval_on_selector_all("img", "e=>e.map(x=>x.currentSrc||x.src||'')")
    ds = sorted({m.group(1) for x in imgs for m in [re.search(r"app\.manoakcijos\.lt/([^/]+_silas_\w+)/image00", x)] if m})
    print(ds)
    rep = []
    for d in ds:
        for k in range(1, 40):
            r = ctx.request.get(f"https://app.manoakcijos.lt/{d}/image{k:02d}.webp", timeout=60000)
            if r.status != 200: break
            body = r.body(); (out / f"{d}_{k:02d}.webp").write_bytes(body)
            res = iki.parse_image(body)
            lines = [l["t"] for l in ocr_lines(body)]
            rep.append({"page": f"{d}_{k:02d}", "items": res, "lines": lines})
            print(d, k, len(res))
    (out / "report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1))
