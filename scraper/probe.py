"""Puslapių patikrinimas iš GitHub: HTML, JSON užklausos, nuorodos."""
import json, pathlib, re
from playwright.sync_api import sync_playwright
OUT = pathlib.Path(__file__).parent / "probe"; OUT.mkdir(exist_ok=True)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
URLS = {"rimi": "https://www.rimi.lt/e-parduotuve/lt/akcijos",
        "rimi2": "https://www.rimi.lt/e-parduotuve/lt/akcijos?page=2",
        "lidl": "https://www.lidl.lt/c/maistas-gerimai-ir-buities-prekes/s10068374",
        "lidl2": "https://www.lidl.lt/c/kepiniai/a10100507",
        "iki": "https://iki.lt/akcijos/savaites-akcijos/"}
rep = {}
with sync_playwright() as pw:
    br = pw.chromium.launch(); ctx = br.new_context(user_agent=UA, locale="lt-LT", viewport={"width": 1366, "height": 900})
    for k, u in URLS.items():
        pg = ctx.new_page(); js = []
        def on(r, js=js):
            try:
                if "json" in (r.headers.get("content-type") or "") and len(js) < 25:
                    js.append((r.url, r.text()[:25000]))
            except Exception: pass
        pg.on("response", on)
        try:
            resp = pg.goto(u, wait_until="domcontentloaded", timeout=60000)
            try: pg.wait_for_load_state("networkidle", timeout=15000)
            except Exception: pass
            for s in ("#onetrust-accept-btn-handler", "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll", "button:has-text('Sutinku')", "button:has-text('Priimti')"):
                try: pg.click(s, timeout=1500); break
                except Exception: pass
            for _ in range(10): pg.mouse.wheel(0, 3000); pg.wait_for_timeout(500)
            links = sorted(set(pg.eval_on_selector_all("a[href]", "e=>e.map(x=>x.href)")))
            rep[k] = {"status": resp.status if resp else None, "title": pg.title(), "links": len(links), "json": [x[0] for x in js]}
            (OUT / f"{k}_html.txt").write_text(pg.content()[:600000], encoding="utf-8")
            (OUT / f"{k}_text.txt").write_text(pg.inner_text("body")[:60000], encoding="utf-8")
            (OUT / f"{k}_links.txt").write_text("\n".join(links), encoding="utf-8")
            for i, (ju, jt) in enumerate(js): (OUT / f"{k}_json{i}.txt").write_text(ju + "\n\n" + jt, encoding="utf-8")
        except Exception as e:
            rep[k] = {"err": str(e)[:300]}
        pg.close()
    br.close()
(OUT / "report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(rep, ensure_ascii=False, indent=1))
