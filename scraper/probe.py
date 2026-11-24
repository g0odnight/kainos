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
    for k, u in (("home", "https://manoakcijos.lt/"), ("iki", "https://manoakcijos.lt/parduotuves/iki")):
        try: grab(k, u)
        except Exception as e: rep[k] = {"err": str(e)[:300]}
    try:
        links = (OUT / "iki_links.txt").read_text().splitlines()
        lf = [l.split(" | ")[0] for l in links if re.search(r"iki", l, re.I) and re.search(r"leidin|/\d{4,}", l)]
        rep["iki_leaflet_links"] = lf[:20]
        if lf: grab("leaf", lf[0])
    except Exception as e: rep["leaf_err"] = str(e)[:300]
    for k, u in (("about", "https://manoakcijos.lt/apie-mus"), ("privacy", "https://manoakcijos.lt/privatumo-politika")):
        try: grab(k, u)
        except Exception as e: rep[k] = {"err": str(e)[:200]}
    br.close()
(OUT / "report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(rep, ensure_ascii=False, indent=1))
