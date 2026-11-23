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

def dump(tag, text):
    d = HERE / "debug"; d.mkdir(exist_ok=True)
    (d / tag).write_text(text, encoding="utf-8")

def crawl_catalog(page, store, c, budget_s=1500):
    t0, cats = time.time(), set(c.get("category_urls", []))
    d = c.get("discover")
    if d:
        try:
            page.goto(d["url"], wait_until="domcontentloaded", timeout=90000)
            try: page.wait_for_load_state("networkidle", timeout=15000)
            except Exception: pass
            page.wait_for_timeout(2500)
            hrefs = sorted(set(page.eval_on_selector_all("a[href]", "e=>e.map(x=>x.href.split('#')[0].split('?')[0])")))
            cats |= {h for h in hrefs if re.search(d["regex"], h)}
            dump(f"{store}_discover.txt", f"{page.url}\n{page.title()}\n\n" + "\n".join(hrefs))
            dump(f"{store}_discover.html", page.content()[:200000])
        except Exception as e:
            print(store, "kategorijų paieška nepavyko:", e)
    print(f"{store}: {len(cats)} kategorijų")
    items, dbg = {}, 0
    for cat in sorted(cats)[:c.get("max_categories", 60)]:
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
        print(f"   {cat[-50:]}: viso {len(items)}")
    return items

def find_pdfs(page, url, viewer_re=None):
    """Grąžina (pdf nuorodos, leidinių peržiūros puslapių nuorodos)."""
    pdfs, viewers = set(), set()
    def on_resp(r):
        if "pdf" in (r.headers.get("content-type") or "").lower(): pdfs.add(r.url)
    page.on("response", on_resp)
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=90000)
        try: page.wait_for_load_state("networkidle", timeout=12000)
        except Exception: pass
        hrefs = sorted(set(page.eval_on_selector_all("a[href]", "e=>e.map(x=>x.href)")))
        dump("leaflet_" + re.sub(r"\W+", "_", url)[-60:] + ".txt", "\n".join(hrefs))
        pdfs |= {h for h in hrefs if re.search(r"\.pdf($|\?)", h, re.I)}
        if viewer_re: viewers |= {h for h in hrefs if re.search(viewer_re, h)}
    except Exception as e:
        print("   leidinių puslapis nepavyko:", url, e)
    finally:
        page.remove_listener("response", on_resp)
    return pdfs, viewers

def ocr_image(body):
    with tempfile.NamedTemporaryFile(suffix=".img") as f:
        f.write(body); f.flush()
        return leaflets._run(["tesseract", f.name, "stdout", "-l", "lit+eng", "--psm", "6"], 120)

def crawl_viewer(ctx, url, store, idx):
    """Atidaro leidinio peržiūros puslapį ir renka: PDF, JSON su prekėmis, puslapių paveikslėlius (OCR)."""
    pg = ctx.new_page(); pdfs, imgs, jsons = set(), {}, []
    def on_resp(r):
        try:
            ct = (r.headers.get("content-type") or "").lower()
            if "pdf" in ct: pdfs.add(r.url)
            elif ct.startswith("image/") and "svg" not in ct:
                b = r.body()
                if len(b) > 120000: imgs[r.url] = b
            elif "json" in ct:
                it = []; from common import walk; walk(r.json(), it)
                if it: jsons.extend(it)
        except Exception: pass
    pg.on("response", on_resp)
    try:
        pg.goto(url, wait_until="domcontentloaded", timeout=90000)
        try: pg.wait_for_load_state("networkidle", timeout=15000)
        except Exception: pass
        for _ in range(12):  # varto puslapius
            pg.keyboard.press("ArrowRight"); pg.wait_for_timeout(700)
        if DEBUG: dump(f"viewer_{store}_{idx}.txt", f"{url}\npdf={sorted(pdfs)}\nimgs={list(imgs)[:40]}\njson_items={len(jsons)}")
    except Exception as e:
        print("   peržiūra nepavyko:", url, e)
    finally:
        pg.close()
    return pdfs, imgs, jsons

def crawl_leaflets(ctx, page, store, c):
    year = datetime.date.today().year
    pdfs = set(c.get("pdfs", [])); viewers = set(c.get("viewers", []))
    for u in c.get("pages", []):
        p, v = find_pdfs(page, u, c.get("viewer_regex")); pdfs |= p; viewers |= v
    items, texts = {}, []
    for k, v in enumerate(sorted(viewers)[:c.get("max_viewers", 6)]):
        p, imgs, jsons = crawl_viewer(ctx, v, store, k)
        pdfs |= p
        print(f"   peržiūra {v[-50:]}: pdf {len(p)}, paveikslėlių {len(imgs)}, json prekių {len(jsons)}")
        for n, pr in jsons: items[(n, pr)] = ""
        if not p:
            txt = "\n".join(ocr_image(b) for u2, b in list(imgs.items())[:40])
            if txt.strip():
                res = leaflets.parse_text(txt, year)
                print(f"      OCR: {len(res)} prekių")
                for n, pr, until in res: items[(n, pr)] = until
    print(f"{store}: rasta {len(pdfs)} PDF, {len(viewers)} peržiūros nuorodų")
    for u in sorted(pdfs)[:12]:
        try:
            body = ctx.request.get(u, timeout=120000).body()
            with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
                f.write(body); f.flush()
                res, mode = leaflets.parse_pdf(f.name)
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
        res, mode = leaflets.parse_pdf(a.pdf)
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
            pp, vv = find_pdfs(page, a.probe, ".*"); print("PDF:", sorted(pp)[:10]); print("Nuorodos:", sorted(vv)[:40])
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
