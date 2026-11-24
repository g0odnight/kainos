"""manoakcijos.lt patikrinimas: IKI leidiniai, paveikslėliai, savininkas."""
import json, pathlib, re, subprocess
from playwright.sync_api import sync_playwright
OUT = pathlib.Path(__file__).parent / "probe"; OUT.mkdir(exist_ok=True)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
rep = {}
with sync_playwright() as pw:
    br = pw.chromium.launch(); ctx = br.new_context(user_agent=UA, locale="lt-LT"); pg = ctx.new_page()
    def grab(k, u):
        r = pg.goto(u, wait_until="domcontentloaded", timeout=60000)
        try: pg.wait_for_load_state("networkidle", timeout=15000)
        except Exception: pass
        links = sorted(set(pg.eval_on_selector_all("a[href]", "e=>e.map(x=>x.href+' | '+(x.innerText||'').trim().slice(0,60))")))
        imgs = pg.eval_on_selector_all("img", "e=>e.map(x=>[x.currentSrc||x.src,x.naturalWidth,x.naturalHeight])")
        rep[k] = {"url": u, "final": pg.url, "status": r.status if r else None, "title": pg.title(), "nlinks": len(links)}
        (OUT / f"{k}_links.txt").write_text("\n".join(links), encoding="utf-8")
        (OUT / f"{k}_imgs.txt").write_text("\n".join(map(str, imgs)), encoding="utf-8")
        (OUT / f"{k}_text.txt").write_text(pg.inner_text("body")[:40000], encoding="utf-8")
        (OUT / f"{k}_html.txt").write_text(pg.content()[:300000], encoding="utf-8")
        return links
    for k, u in (("leaf", "https://manoakcijos.lt/parduotuves/iki/iki-23-11-26-29-11-26-fiohy/1"), ("leaf2", "https://manoakcijos.lt/parduotuves/iki/iki-23-11-26-29-11-26-fiohy/2"), ("hitai", "https://manoakcijos.lt/dienos-hitai/puslapis/1")):
        try: grab(k, u)
        except Exception as e: rep[k] = {"err": str(e)[:300]}
    for name in ("image00.webp", "image01.webp", "image00.jpg"):
        try:
            r = ctx.request.get("https://app.manoakcijos.lt/261129_261123_iki_fiohy/" + name, timeout=60000); b = r.body()
            (OUT / ("iki_" + name + ".bin")).write_bytes(b)
            rep[name] = [r.status, r.headers.get("content-type"), len(b), subprocess.run(["identify", str(OUT / ("iki_" + name + ".bin"))], capture_output=True, text=True).stdout.strip()]
        except Exception as e: rep[name] = str(e)[:200]
    for k, u in (("terms", "https://manoakcijos.lt/taisykles-paslaugos"),):
        try: grab(k, u)
        except Exception as e: rep[k] = {"err": str(e)[:200]}
    br.close()
(OUT / "report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(rep, ensure_ascii=False, indent=1))
