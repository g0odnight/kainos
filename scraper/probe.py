"""Promo leidinio paveikslėlių OCR bandymas (akcijos.lt + issuu)."""
import json, pathlib, re, subprocess, tempfile
from playwright.sync_api import sync_playwright
OUT = pathlib.Path(__file__).parent / "probe"; OUT.mkdir(exist_ok=True)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
def sh(c, t=300): return subprocess.run(c, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=t).stdout
rep = {}
with sync_playwright() as pw:
    br = pw.chromium.launch(); ctx = br.new_context(user_agent=UA, locale="lt-LT"); pg = ctx.new_page()
    pg.goto("https://akcijos.lt/promo-cash-carry-akcijos", wait_until="domcontentloaded", timeout=60000)
    try: pg.wait_for_load_state("networkidle", timeout=15000)
    except Exception: pass
    links = sorted(set(x for x in pg.eval_on_selector_all("a[href]", "e=>e.map(x=>x.href)") if "promo" in x.lower()))
    rep["promo_links"] = links[:40]
    body = pg.inner_text("body"); rep["promo_text"] = body[:3000]
    # pirmas leidinio puslapis
    pub = next((l for l in links if re.search(r"leidin", l)), None); rep["pub"] = pub
    if pub:
        pg.goto(pub, wait_until="domcontentloaded", timeout=60000)
        try: pg.wait_for_load_state("networkidle", timeout=15000)
        except Exception: pass
        imgs = [x for x in pg.eval_on_selector_all("img", "e=>e.map(x=>x.currentSrc||x.src)") if "publications" in x]
        rep["imgs"] = imgs[:60]; rep["pub_text"] = pg.inner_text("body")[:2000]
        for k, im in enumerate(imgs[1:5]):
            b = ctx.request.get(im, timeout=60000).body()
            fn = str(OUT / f"p{k}.jpg"); open(fn, "wb").write(b)
            sh(["convert", fn, "-resize", "250%", "-colorspace", "Gray", "-sharpen", "0x1", fn + ".png"])
            (OUT / f"p{k}_ocr.txt").write_text(sh(["tesseract", fn + ".png", "stdout", "-l", "lit+eng", "--psm", "11"]), encoding="utf-8")
            (OUT / f"p{k}.tsv").write_text(sh(["tesseract", fn + ".png", "stdout", "-l", "lit+eng", "--psm", "11", "tsv"]), encoding="utf-8")
            rep[f"p{k}"] = sh(["identify", fn]).strip()
    br.close()
(OUT / "report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(rep, ensure_ascii=False, indent=1)[:4000])
