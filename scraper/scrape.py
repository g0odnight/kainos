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
            for r in new: items[r] = ("", "")
            time.sleep(1.0)
        print(f"   {cat[-50:]}: viso {len(items)}")
    return items

def click_discover(page, url, limit=8):
    """Kortelės be <a href>: paspaudžiam ir žiūrim, į kokį URL nuvedė."""
    found = set()
    try:
        cards = page.evaluate("""()=>[...document.querySelectorAll('[class*=card],[class*=leaflet],[class*=leidin],[class*=flyer],[role=link],[onclick],article,li')]
          .filter(e=>{const t=(e.innerText||'').trim();return t.length>8&&t.length<160&&/leidin|katalog|akcij|20\\d\\d/i.test(t)}).length""")
        dump("click_cards_" + re.sub(r"\W+", "_", url)[-40:] + ".txt", f"kandidatų: {cards}")
        for i in range(min(cards, limit)):
            page.goto(url, wait_until="domcontentloaded", timeout=60000); page.wait_for_timeout(1500)
            ok = page.evaluate("""(i)=>{const c=[...document.querySelectorAll('[class*=card],[class*=leaflet],[class*=leidin],[class*=flyer],[role=link],[onclick],article,li')]
              .filter(e=>{const t=(e.innerText||'').trim();return t.length>8&&t.length<160&&/leidin|katalog|akcij|20\\d\\d/i.test(t)});if(!c[i])return false;c[i].click();return true}""", i)
            page.wait_for_timeout(3000)
            if ok and page.url.split("?")[0] != url.split("?")[0]: found.add(page.url)
    except Exception as e:
        print("   click_discover klaida:", e)
    return found

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
        viewers |= {h for h in hrefs if re.search(r"ipaper\.io|issuu\.com/|publitas\.com|leaflets\.schwarz|flippingbook|yumpu|/leidinys/|/leidiniai/[\w-]+", h)
                    and "cookie" not in h and "privacy" not in h}
        if viewer_re and not viewers and not pdfs:
            viewers |= click_discover(page, url)
    except Exception as e:
        print("   leidinių puslapis nepavyko:", url, e)
    finally:
        page.remove_listener("response", on_resp)
    return pdfs, viewers

def ocr_image(body):
    with tempfile.NamedTemporaryFile(suffix=".img") as f:
        f.write(body); f.flush()
        return leaflets._run(["tesseract", f.name, "stdout", "-l", "lit+eng", "--psm", "6"], 120)

PDF_DATES = {}

def page_text(pg):
    parts = []
    for f in pg.frames:
        try:
            parts.append(f.inner_text("body"))
            parts += f.eval_on_selector_all("noscript", "e=>e.map(x=>x.textContent)")
        except Exception: pass
    return "\n".join(p for p in parts if p)

def crawl_viewer(ctx, url, store, idx):
    """Atidaro leidinio peržiūros puslapį ir renka: PDF, JSON su prekėmis, puslapių paveikslėlius (OCR)."""
    pg = ctx.new_page(); pdfs, imgs, jsons = set(), {}, []; viewer_text = ""; bodies = []
    def on_resp(r):
        try:
            ct = (r.headers.get("content-type") or "").lower()
            if "pdf" in ct: pdfs.add(r.url)
            elif ct.startswith("image/") and "svg" not in ct:
                b = r.body()
                if len(b) > 40000: imgs[r.url] = b
            elif "json" in ct:
                from common import walk, walk_loose
                data = r.json(); it = []
                if re.search(r"schwarz|ipaper|enrich|flyer", r.url): walk_loose(data, it)
                else: walk(data, it)
                if it: jsons.extend(it)
                fl = data.get("flyer") if isinstance(data, dict) else None
                if isinstance(fl, dict) and fl.get("pdfUrl"):
                    pdfs.add(fl["pdfUrl"])
                    PDF_DATES[fl["pdfUrl"]] = (fl.get("offerStartDate") or fl.get("startDate") or "", fl.get("offerEndDate") or fl.get("endDate") or "")
                if re.search(r"schwarz|ipaper|enrich|flyer", r.url) and "Statistics" not in r.url and len(bodies) < 8:
                    bodies.append((r.url, json.dumps(data, ensure_ascii=False)[:15000]))
        except Exception: pass
    netlog = []
    pg.on("response", lambda r: netlog.append(f"{r.status} {(r.headers.get('content-type') or '')[:30]} {r.url[:220]}"))
    pg.on("response", on_resp)
    try:
        pg.goto(url, wait_until="domcontentloaded", timeout=90000)
        try: pg.wait_for_load_state("networkidle", timeout=15000)
        except Exception: pass
        texts = [page_text(pg)]
        hrefs = pg.eval_on_selector_all("a[href]", "e=>e.map(x=>x.href)")
        pdfs |= {h for h in hrefs if re.search(r"\.pdf($|\?)|download|atsisiust", h, re.I) and not h.startswith("javascript")}
        if re.search(r"ipaper|leidiniai\.rimi", url + " " + " ".join(f.url for f in pg.frames)):
            base = (url if re.search(r"ipaper|leidiniai\.rimi", url) else next((f.url for f in pg.frames if "viewer.ipaper.io" in f.url), url)).split("?")[0]
            for n in range(2, 90):   # ipaper: tekstas kiekviename puslapyje per ?Page=N
                try:
                    pg.goto(f"{base}?Page={n}", wait_until="domcontentloaded", timeout=60000)
                    t = page_text(pg)
                except Exception: break
                if not t.strip() or t == texts[-1]: break
                texts.append(t)
        for _ in range(40 if len(texts) < 3 else 0):  # varto puslapius
            pg.keyboard.press("ArrowRight"); pg.wait_for_timeout(600)
        viewer_text = "\n".join(dict.fromkeys("\n".join(texts).splitlines()))
        if DEBUG:
            frames = [f.url for f in pg.frames]
            dump(f"viewer_{store}_{idx}.txt", f"{url}\nframes={frames}\npdf={sorted(pdfs)}\nimgs={list(imgs)[:60]}\njson_items={len(jsons)}")
            dump(f"net_{store}_{idx}.txt", "\n".join(netlog[:400]))
            for bi, (bu, bt) in enumerate(bodies): dump(f"json_{store}_{idx}_{bi}.txt", bu + "\n\n" + bt)
            try: dump(f"links_{store}_{idx}.txt", "\n".join(sorted(set(hrefs))))
            except Exception: pass
    except Exception as e:
        print("   peržiūra nepavyko:", url, e)
    finally:
        pg.close()
    return pdfs, imgs, jsons, viewer_text

def crawl_leaflets(ctx, page, store, c):
    year = datetime.date.today().year
    pdfs = set(c.get("pdfs", [])); viewers = set(c.get("viewers", []))
    for u in c.get("pages", []):
        p, v = find_pdfs(page, u, c.get("viewer_regex")); pdfs |= p; viewers |= v
    if not viewers and not pdfs:   # nieko neradom - bandom pačius puslapius kaip peržiūrą
        viewers = set(c.get("pages", []))
        print(f"   {store}: nuorodų nerasta, bandom pačius puslapius")
    items, texts = {}, []
    for k, v in enumerate(sorted(viewers)[:c.get("max_viewers", 6)]):
        p, imgs, jsons, vtext = crawl_viewer(ctx, v, store, k)
        pdfs |= p
        print(f"   peržiūra {v[-50:]}: pdf {len(p)}, paveikslėlių {len(imgs)}, json prekių {len(jsons)}")
        jr = leaflets.valid_range(vtext, year) if vtext else ("", "")
        for n, pr in jsons: items[(n, pr)] = (jr[1], jr[0])
        if vtext.strip() and not jsons:
            if DEBUG: dump(f"text_{store}_{k}.txt", vtext[:30000])
            res = (leaflets.parse_maxima(vtext, year) if leaflets.is_maxima_text(vtext) else leaflets.parse_ipaper(vtext, year) if leaflets.is_ipaper_text(vtext) else leaflets.parse_text(vtext, year))
            print(f"      tekstas: {len(res)} prekių")
            for n, pr, until, frm in res: items[(n, pr)] = (until, frm)
        if not p and not items:
            txt = "\n".join(ocr_image(b) for u2, b in list(imgs.items())[:60])
            if DEBUG: dump(f"ocr_{store}_{k}.txt", txt[:20000])
            if txt.strip():
                res = leaflets.parse_text(txt, year)
                print(f"      OCR: {len(res)} prekių")
                for n, pr, until, frm in res: items[(n, pr)] = (until, frm)
    print(f"{store}: rasta {len(pdfs)} PDF, {len(viewers)} peržiūros nuorodų")
    pdfs = {u for u in pdfs if not re.search(r"NE-MAISTO|Zaislu|Tapk-LIDL", u, re.I)}
    for u in sorted(pdfs)[:12]:
        try:
            body = ctx.request.get(u, timeout=400000).body()
            with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
                f.write(body); f.flush()
                res, mode = leaflets.parse_pdf(f.name)
                if DEBUG: dump("pdftext_" + re.sub(r"\W+", "_", u)[-40:] + ".txt", leaflets.pdf_text(f.name)[0][:15000])
            print(f"   {u[-60:]}: {len(res)} prekių ({mode})")
            d0 = PDF_DATES.get(u, ("", ""))
            for n, p, until, frm in res: items[(n, p)] = (until or d0[1], frm or d0[0])
        except Exception as e:
            print("   PDF klaida:", u, e)
    today = datetime.date.today().isoformat()
    items = {k: u for k, u in items.items() if not u[0] or u[0] >= today}
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
        if old.get("v") != 10: old = {"stores": [], "items": []}   # seni (šlamštiniai) duomenys nebelaikomi
        oldmap = {}
        for i in old["items"]:
            s, n, p, k = old["stores"][i[0]], i[1], i[2], i[3]; u = (i[4] if len(i) > 4 else "", i[5] if len(i) > 5 else "")
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
        for kind in ("l",):
            d = new.get((store, kind), oldmap.get((store, kind), {}))
            for (n, p), u in d.items(): out_items.append([stores.index(store), n, p, kind, u[0], u[1]])
    out_items.sort(key=lambda x: (x[1], x[2]))
    out = {"v": 10, "updated": datetime.datetime.now(datetime.timezone.utc).isoformat(), "stores": stores, "status": status, "items": out_items}
    (ROOT / "prices.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False, indent=1), "iš viso:", len(out_items))

if __name__ == "__main__":
    main()
