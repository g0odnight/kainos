"""Šaltinių patikrinimas iš GitHub: Norfa PDF per /leidiniai/download/N, IKI/Promo per akcijos.lt paveikslėlius + OCR."""
import json, pathlib, re, subprocess, tempfile
from playwright.sync_api import sync_playwright
OUT = pathlib.Path(__file__).parent / "probe"; OUT.mkdir(exist_ok=True)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
def sh(c, t=300): return subprocess.run(c, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=t).stdout
rep = []
with sync_playwright() as pw:
    br = pw.chromium.launch(); ctx = br.new_context(user_agent=UA, locale="lt-LT"); pg = ctx.new_page()
    # --- Norfa
    pg.goto("https://www.norfa.lt/leidiniai/", wait_until="domcontentloaded", timeout=60000)
    leaf = pg.evaluate("""()=>[...document.querySelectorAll('[href*="/leidiniai/download/"]')].map(e=>{const c=e.closest('[class*=leaflet]')||e.parentElement.parentElement;return [e.getAttribute('href'),(c.innerText||'').replace(/\\s+/g,' ').slice(0,200)]})""")
    rep.append({"norfa_leaflets": leaf})
    for i, (href, txt) in enumerate(leaf[:3]):
        r = ctx.request.get("https://www.norfa.lt" + href, timeout=120000)
        b = r.body(); rep.append({"norfa_dl": href, "status": r.status, "ct": r.headers.get("content-type"), "url": r.url, "len": len(b)})
        if b[:4] == b"%PDF":
            p = OUT / f"norfa{i}.pdf"; p.write_bytes(b)
            (OUT / f"norfa{i}_raw.txt").write_text(sh(["pdftotext", "-raw", "-l", "6", str(p), "-"])[:40000], encoding="utf-8")
            (OUT / f"norfa{i}_bbox.xml").write_text(sh(["pdftotext", "-bbox-layout", "-l", "6", str(p), "-"])[:3000000], encoding="utf-8")
            p.unlink()
    # --- akcijos.lt (IKI, Promo): paveikslėliai + OCR 3 puslapių
    for name, u in (("iki", "https://akcijos.lt/iki-savaitele-akciju-leidinys"), ("iki2", "https://akcijos.lt/iki-kainu-leidinys-nr-47"), ("promo", "https://akcijos.lt/promo-cash-carry-akcijos")):
        try:
            pg.goto(u, wait_until="domcontentloaded", timeout=60000)
            try: pg.wait_for_load_state("networkidle", timeout=15000)
            except Exception: pass
            imgs = [x for x in pg.eval_on_selector_all("img", "e=>e.map(x=>x.currentSrc||x.src)") if "publications" in x]
            links = [x for x in pg.eval_on_selector_all("a[href]", "e=>e.map(x=>x.href+' | '+(x.innerText||'').trim().slice(0,80))") if "leidin" in x.lower()]
            body = pg.inner_text("body")
            rep.append({"site": u, "title": pg.title(), "imgs": imgs[:40], "links": links[:30], "dates": re.findall(r"20\d\d-\d\d-\d\d\s*-\s*20\d\d-\d\d-\d\d", body)[:5]})
            for k, im in enumerate(imgs[:3]):
                b = ctx.request.get(im, timeout=60000).body()
                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f: f.write(b); fn = f.name
                (OUT / f"{name}_p{k}_ocr.txt").write_text(sh(["tesseract", fn, "stdout", "-l", "lit+eng", "--psm", "11"]), encoding="utf-8")
                (OUT / f"{name}_p{k}.tsv").write_text(sh(["tesseract", fn, "stdout", "-l", "lit+eng", "--psm", "11", "tsv"]), encoding="utf-8")
                rep.append({"img": im, "bytes": len(b), "size": sh(["identify", fn]).strip()})
        except Exception as e:
            rep.append({"site": u, "err": str(e)[:300]})
    br.close()
(OUT / "report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(rep, ensure_ascii=False, indent=1)[:6000])
