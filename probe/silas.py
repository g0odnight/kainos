import os, re, json
os.makedirs("probe/out", exist_ok=True)
from playwright.sync_api import sync_playwright
out = {}
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(locale="lt-LT")
    def go(u, n):
        try:
            pg.goto(u, wait_until="domcontentloaded", timeout=60000)
            try: pg.wait_for_load_state("networkidle", timeout=10000)
            except Exception: pass
            open(f"probe/out/{n}.txt", "w").write(pg.inner_text("body"))
            open(f"probe/out/{n}.html", "w").write(pg.content())
            links = pg.evaluate("()=>[...document.querySelectorAll('a[href]')].map(a=>a.href+' | '+(a.innerText||'').replace(/\\s+/g,' ').slice(0,80))")
            open(f"probe/out/{n}_links.txt", "w").write("\n".join(links))
        except Exception as e:
            open(f"probe/out/{n}.err", "w").write(str(e))
    go("https://www.akcijuseklys.lt/parduotuve/silas", "ak")
    go("https://www.silas.lt/", "silas")
    go("https://www.silas.lt/akcijos", "silas_akc")
    go("https://www.silas.lt/leidiniai", "silas_leid")
