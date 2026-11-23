"""Vienkartinis šaltinių patikrinimas iš GitHub serverio: ar pasiekiami adresai ir kas juose yra."""
import json, pathlib, re
from playwright.sync_api import sync_playwright
OUT = pathlib.Path(__file__).parent / "probe"; OUT.mkdir(exist_ok=True)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
REQ = [
 "https://iki.lt/wp-json/wp/v2/media?mime_type=application/pdf&per_page=30&orderby=date&order=desc",
 "https://iki.lt/wp-json/wp/v2/media?search=palaikymas&per_page=30&orderby=date&order=desc",
 "https://iki.lt/wp-sitemap.xml", "https://iki.lt/sitemap_index.xml", "https://iki.lt/feed/",
 "https://iki.lt/wp-content/uploads/2026/11/",
 "https://iki.lt/wp-content/uploads/2026/06/19/A4-Lazdijai-Kedainiai-Kovo-11-palaikymas-W26.pdf",
 "https://www.norfa.lt/leidiniai/",
 "https://epromo.lt/lt/leidiniai", "https://epromo.lt/leidiniai",
 "https://akcijos.lt/iki-akcijos", "https://akcijos.lt/norfa-savaitinis-akciju-leidinys", "https://akcijos.lt/promo-cash-carry-akcijos",
 "https://tavoakcijos.lt/parduotuves/promo", "https://tavoakcijos.lt/parduotuves/iki", "https://tavoakcijos.lt/parduotuves/norfa",
 "https://www.raskakcija.lt/iki-leidinys.htm", "https://issuu.com/t/sanitex/epromo",
]
BROWSER = ["https://www.norfa.lt/leidiniai/", "https://akcijos.lt/iki-akcijos", "https://akcijos.lt/promo-cash-carry-akcijos", "https://tavoakcijos.lt/parduotuves/iki"]
rep = []
with sync_playwright() as pw:
    br = pw.chromium.launch(); ctx = br.new_context(user_agent=UA, locale="lt-LT")
    for u in REQ:
        try:
            r = ctx.request.get(u, timeout=60000); b = r.body(); ct = r.headers.get("content-type", "")
            t = b[:200000].decode("utf-8", "replace") if "pdf" not in ct else ""
            pdfs = sorted(set(re.findall(r"https?://[^\"'\s<>]+?\.pdf", t)))[:40]
            rep.append({"u": u, "status": r.status, "ct": ct, "len": len(b), "cf": "cf-chl" in t or "challenge-platform" in t, "pdfs": pdfs})
            (OUT / (re.sub(r"\W+", "_", u)[-70:] + ".txt")).write_text(t[:60000], encoding="utf-8")
        except Exception as e:
            rep.append({"u": u, "err": str(e)[:200]})
    pg = ctx.new_page()
    for u in BROWSER:
        try:
            pg.goto(u, wait_until="domcontentloaded", timeout=60000)
            try: pg.wait_for_load_state("networkidle", timeout=15000)
            except Exception: pass
            html = pg.content()
            imgs = pg.eval_on_selector_all("img", "e=>e.map(x=>x.currentSrc||x.src)")
            links = pg.eval_on_selector_all("a[href]", "e=>e.map(x=>x.href+' | '+(x.innerText||'').trim().slice(0,60))")
            (OUT / ("B_" + re.sub(r"\W+", "_", u)[-60:] + ".txt")).write_text(pg.title() + "\n\n" + "\n".join(links) + "\n\nIMGS\n" + "\n".join(imgs[:80]) + "\n\nHTML\n" + html[:150000], encoding="utf-8")
            rep.append({"browser": u, "title": pg.title(), "links": len(links), "imgs": len(imgs)})
        except Exception as e:
            rep.append({"browser": u, "err": str(e)[:200]})
    br.close()
(OUT / "report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(rep, ensure_ascii=False, indent=1))
