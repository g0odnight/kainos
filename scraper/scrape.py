#!/usr/bin/env python3
"""Pilnas kainų surinkimas -> prices.json.
  python scraper/scrape.py                      # viskas
  python scraper/scrape.py --store Rimi         # viena parduotuvė (kitų duomenys paliekami)
  python scraper/scrape.py --probe URL [--store Rimi]   # ką randa viename puslapyje (+ PDF nuorodos)
  python scraper/scrape.py --pdf failas.pdf     # kaip išparsintų leidinį
"""
import argparse, datetime, json, os, pathlib, re, tempfile, time
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from playwright.sync_api import sync_playwright
import leaflets
from common import HERE, UA, scrape_page

ROOT = HERE.parent
DEBUG = os.environ.get("DEBUG") == "1"

def with_page(url, param, n):
    u = urlparse(url); q = dict(parse_qsl(u.query)); q[param] = n
    return urlunparse(u._replace(query=urlencode(q)))

def crawl_catalog(page, store, c, budget_s=1500):
    t0, cats = time.time(), set(c.get("category_urls", []))
    d = c.get("discover")
    if d:
        try:
            page.goto(d["url"], wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(2500)
            hrefs = page.eval_on_selector_all("a[href]", "e=>e.map(x=>x.href.split('#')[0].split('?')[0])")
            cats |= {h for h in hrefs if re.search(d["regex"], h)}
        except Exception as e:
            print(store, "kategorijų paieška nepavyko:", e)
    print(f"{store}: {len(cats)} kategorijų")
    items, dbg = {}, 0
    for cat in sorted(cats):
        for pg in range(1, c.get("max_pages", 30) + 1):
            if time.time() - t0 > budget_s: print(store, "laiko limitas"); return items
            url = cat if pg == 1 else with_page(cat, c.get("page_param", "page"), pg)
            tag = None
            if DEBUG and dbg < 3: tag = f"{store}_cat{dbg}"; dbg += 1
            res = scrape_page(page, url, c.get("selectors"), tag)
            new = [r for r in res if r not in items]
            if not new: break
            for r in new: items[r] = ""
            time.sleep(1.0)
    return items

def find_pdfs(page, url):
    pdfs = set()
    def on_resp(r):
        if "pdf" in (r.headers.get("content-type") or "").lower(): pdfs.add(r.url)
    page.on("response", on_resp)
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        try: page.wait_for_load_state("networkidle", timeout=12000)
        except Exception: pass
        hrefs = page.eval_on_selector_all("a[href]", "e=>e.map(x=>x.href)")
        pdfs |= {h for h in hrefs if re.search(r"\.pdf($|\?)", h, re.I)}
    except Exception as e:
        print("   leidinių puslapis nepavyko:", url, e)
    finally:
        page.remove_listener("response", on_resp)
    return pdfs

def crawl_leaflets(ctx, page, store, c):
    year = datetime.date.today().year
    pdfs = set(c.get("pdfs", []))
    for u in c.get("pages", []): pdfs |= find_pdfs(page, u)
    print(f"{store}: rasta {len(pdfs)} PDF")
    items = {}
    for u in sorted(pdfs)[:12]:
        try:
            body = ctx.request.get(u, timeout=120000).body()
            with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
                f.write(body); f.flush()
                res, mode = leaflets.parse_pdf(f.name, year)
            print(f"   {u[-60:]}: {len(res)} prekių ({mode})")
            for n, p, until in res: items[(n, p)] = until
        except Exception as e:
            print("   PDF klaida:", u, e)
    return items

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store"); ap.add_argument("--probe"); ap.add_argument("--pdf")
    a = ap.parse_args()
    if a.pdf:
        res, mode = leaflets.parse_pdf(a.pdf, datetime.date.today().year)
        print(mode, len(res))
        for r in res[:40]: print(r)
        return
    cfg = {k: v for k, v in json.load(open(HERE / "stores.json", encoding="utf-8")).items() if not k.startswith("_")}
    with sync_playwright() as pw:
        br = pw.chromium.launch(headless=True)
        ctx = br.new_context(user_agent=UA, locale="lt-LT")
        page = ctx.new_page()
        if a.probe:
            sel = cfg.get(a.store, {}).get("catalog", {}).get("selectors")
            res = scrape_page(page, a.probe, sel, "probe")
            print(f"Rasta {len(res)} prekių:")
            for n, p in res[:15]: print("  ", p, n)
            print("PDF nuorodos:", sorted(find_pdfs(page, a.probe))[:10])
            print("Žr. scraper/debug/probe.*"); return
        try: old = json.load(open(ROOT / "prices.json", encoding="utf-8"))
        except Exception: old = {"stores": [], "items": []}
        oldmap = {}
        for i in old["items"]:
            s, n, p, k = old["stores"][i[0]], i[1], i[2], i[3]; u = i[4] if len(i) > 4 else ""
            oldmap.setdefault((s, k), {})[(n, p)] = u
        stores = list(cfg)
        new, status = {}, {}
        for store, c in cfg.items():
            if a.store and store != a.store: continue
            st = {}
            for kind, key, fn in (("e", "catalog", lambda: crawl_catalog(page, store, c["catalog"])),
                                  ("l", "leaflets", lambda: crawl_leaflets(ctx, page, store, c["leaflets"]))):
                if not c.get(key, {}).get("enabled"): continue
                try: got = fn()
                except Exception as e: got = {}; print(store, key, "klaida:", e)
                prev = oldmap.get((store, kind), {})
                if prev and len(got) < 0.3 * len(prev):
                    st[key] = f"įspėjimas: rasta {len(got)} (buvo {len(prev)}), palikti seni"; got = prev
                else:
                    st[key] = len(got)
                new[(store, kind)] = got
            status[store] = st
        br.close()
    out_items = []
    for store in stores:
        for kind in ("e", "l"):
            d = new.get((store, kind), oldmap.get((store, kind), {}))
            for (n, p), u in d.items(): out_items.append([stores.index(store), n, p, kind, u])
    out_items.sort(key=lambda x: (x[1], x[2]))
    out = {"updated": datetime.datetime.now(datetime.timezone.utc).isoformat(), "stores": stores, "status": status, "items": out_items}
    (ROOT / "prices.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False, indent=1), "iš viso:", len(out_items))

if __name__ == "__main__":
    main()
