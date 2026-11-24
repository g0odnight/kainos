#!/usr/bin/env python3
"""Pilnas kainų surinkimas -> prices.json.
  python scraper/scrape.py                      # viskas
  python scraper/scrape.py --store Rimi         # viena parduotuvė (kitų duomenys paliekami)
  python scraper/scrape.py --probe URL [--store Rimi]   # ką randa viename puslapyje (+ PDF nuorodos)
  python scraper/scrape.py --pdf failas.pdf     # kaip išparsintų leidinį
"""
from html import unescape
import argparse, datetime, json, os, pathlib, re, tempfile, time
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from playwright.sync_api import sync_playwright
import leaflets, categories, fixnames
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
            for r in new: items[r] = ("", "", None)
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
        try:
            dl = page.evaluate("""()=>[...document.querySelectorAll('a,button,[data-href],[data-url],[download]')].filter(e=>/atsisi|download|pdf/i.test((e.innerText||'')+' '+e.outerHTML)).slice(0,20).map(e=>e.outerHTML.slice(0,600))""")
            dump("dl_" + re.sub(r"\W+", "_", url)[-60:] + ".txt", "\n\n".join(dl))
            for h in page.evaluate("""()=>[...document.querySelectorAll('[data-href],[data-url],[data-file],[download]')].map(e=>e.getAttribute('data-href')||e.getAttribute('data-url')||e.getAttribute('data-file')||e.href).filter(Boolean)"""):
                if re.search(r"\.pdf($|\?)", h, re.I): pdfs.add(h)
        except Exception: pass
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
STATS, CUR = {}, {"store": ""}

def note(source=None, **counts):
    """Statistika programėlės „Informacija“ puslapiui: šaltiniai ir kiekiai."""
    st = STATS.setdefault(CUR["store"], {"sources": [], "found": 0, "parsed": 0})
    if source and source not in st["sources"]: st["sources"].append(source)
    for k, v in counts.items(): st[k] = st.get(k, 0) + v

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

def crawl_norfa(ctx, page, url):
    """Norfa: sąrašo puslapyje kortelės su data ir „Atsisiųsti leidinį“ (/leidiniai/download/N -> PDF)."""
    import norfa
    page.goto(url, wait_until="domcontentloaded", timeout=90000)
    cards = page.evaluate("""()=>[...document.querySelectorAll('[href*="/leidiniai/download/"]')].map(e=>{let c=e;for(let i=0;i<8&&c;i++){if(/\\d{4}\\.\\d\\d\\.\\d\\d\\s*-\\s*\\d{4}\\.\\d\\d\\.\\d\\d/.test(c.innerText||''))break;c=c.parentElement}
      const m=((c&&c.innerText)||'').match(/(\\d{4})\\.(\\d\\d)\\.(\\d\\d)\\s*-\\s*(\\d{4})\\.(\\d\\d)\\.(\\d\\d)/);
      return [e.getAttribute('href'), m?m[1]+'-'+m[2]+'-'+m[3]:'', m?m[4]+'-'+m[5]+'-'+m[6]:'']})""")
    items, seen = {}, set()
    for href, frm, until in cards:
        if href in seen: continue
        seen.add(href)
        try:
            r = ctx.request.get("https://www.norfa.lt" + href, timeout=400000); b = r.body()
            if b[:4] != b"%PDF": print("   Norfa: ne PDF", href); continue
            with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
                f.write(b); f.flush()
                res = norfa.parse(f.name, until, frm)
            print(f"   Norfa {href} ({frm}–{until}): {len(res)} prekių")
            note("norfa.lt leidiniai (PDF)", parsed=len(res), pubs=1)
            for x in res: items[(x[0], x[1])] = (x[2], x[3], x[4])
        except Exception as e:
            print("   Norfa klaida:", href, e)
    return items

MX_CARDS_JS = """()=>[...document.querySelectorAll('.offer-card')].map(c=>{const t=s=>{const e=c.querySelector(s);return e?(e.textContent||'').replace(/\\s+/g,' ').trim():''};
  const all=(c.textContent||'').replace(/\\s+/g,' ').trim();
  return {name:t('h4')||t('h3'),int:t('.offer-price-tag__price-integer'),frac:t('.offer-price-tag__price-fraction'),old:t('.offer-price-tag__old-price'),
          off:t('.offer-price-tag__bottom-discount'),meta:[...c.querySelectorAll('.offer-price-tag__meta-line, .offer-price-tag__bottom')].map(e=>(e.textContent||'').replace(/\\s+/g,' ').trim()).join(' | '),
          card:(c.querySelector('.offer-price-tag__icon img')||{}).alt||'',all}})"""

def parse_maxima_card(c, year):
    """c – struktūrizuota .offer-card informacija iš maxima.lt/pasiulymai."""
    name = (c.get("name") or "").replace("*", "").strip()
    if not name or not c.get("int"): return None
    try: price = int(re.sub(r"\D", "", c["int"])) + int(re.sub(r"\D", "", c.get("frac") or "0") or 0) / 100
    except ValueError: return None
    flat = c.get("all", "") + " " + c.get("meta", "")
    deal = ""
    k = re.search(r"(\d+)\s*vnt\.?\s*už", flat, re.I)
    if k:
        deal = f"{k.group(1)} vnt. už " + f"{price:.2f}".replace(".", ",") + " €"
        price = price / int(k.group(1))
    old = None
    om = re.search(r"(\d{1,3}),(\d{2})", c.get("old") or "")
    if om:
        v = float(om.group(1) + "." + om.group(2))
        if v > price + 0.004: old = v
    until = ""
    u = re.search(r"Iki\s*(\d{1,2})\.(\d{2})", flat)
    if u:
        mo, d = int(u.group(1)), int(u.group(2)); y = year + (1 if mo < datetime.date.today().month - 6 else 0)
        until = "%04d-%02d-%02d" % (y, mo, d)
    if c.get("card") and "kortel" in c["card"].lower() and not deal: deal = "su AČIŪ kortele"
    return name[:120], (round(price, 3) if k else round(price, 2)), until, "", old, deal

def crawl_maxima_offers(page, url):
    year = datetime.date.today().year
    page.goto(url, wait_until="domcontentloaded", timeout=90000)
    try: page.wait_for_load_state("networkidle", timeout=20000)
    except Exception: pass
    for sel in ("#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll", "#CybotCookiebotDialogBodyButtonDecline", "text=Leisti visus slapukus"):
        try: page.click(sel, timeout=2000); break
        except Exception: pass
    last = -1
    for _ in range(80):
        page.mouse.wheel(0, 4000); page.wait_for_timeout(700)
        for b in page.query_selector_all("button:has-text('daugiau'), a:has-text('Rodyti daugiau')"):
            try: b.click(timeout=1000); page.wait_for_timeout(800)
            except Exception: pass
        n = len(page.evaluate(MX_CARDS_JS))
        if n == last: break
        last = n
    n0 = len(page.evaluate(MX_CARDS_JS))
    for txt in ("Žiūrėti visus", "Rodyti visus", "Visi pasiūlymai", "Žiūrėti daugiau"):
        for b in page.query_selector_all(f"text={txt}"):
            try: b.click(timeout=1500); page.wait_for_timeout(1500)
            except Exception: pass
    for _ in range(10): page.mouse.wheel(0, 4000); page.wait_for_timeout(500)
    cards = page.evaluate(MX_CARDS_JS)
    print(f"   Maxima .offer-card: prieš {n0}, po paspaudimų {len(cards)}")
    if DEBUG:
        dump("maxima_offers_cards.json", json.dumps(cards[:600], ensure_ascii=False, indent=1))
    items = {}
    for t in cards:
        r = parse_maxima_card(t, year)
        if r: items[(r[0], r[1])] = (r[2], r[3], r[4], r[5])
    print(f"   Maxima pasiūlymai: {len(cards)} kortelių, {len(items)} prekių")
    note("maxima.lt/pasiulymai", found=len(cards), parsed=len(items))
    return items

RIMI_JS = """()=>[...document.querySelectorAll('.js-product-container')].map(e=>{
  let g={};try{g=JSON.parse(e.getAttribute('data-gtm-eec-product')||'{}')}catch(x){}
  const tx=el=>el?(el.textContent||'').replace(/\\s+/g,' ').trim():'';
  const lab=e.querySelector('.price-label__price');
  let label=null;if(lab){const M=tx(lab.querySelector('.major')),C=tx(lab.querySelector('.cents'));if(M!=='')label=parseFloat(M+'.'+(C||'00'))}
  const sr=tx(e.querySelector('.card__price .sr-only'));const pm=sr.match(/(\\d+[.,]\\d+)/);
  return {id:g.id||e.getAttribute('data-gtms-product-id'),name:g.name||e.getAttribute('data-gtms-click-name')||'',gtm:g.price,cat:g.category||'',label,
          price:pm?parseFloat(pm[1].replace(',','.')):null,unit:sr,per:tx(e.querySelector('.card__price-per [aria-hidden]'))}})"""

def rimi_tree(page):
    """SH kodas -> skyrių pavadinimų kelias (iš Rimi kategorijų medžio)."""
    out = {}
    try:
        tree = page.evaluate("()=>fetch('/e-parduotuve/api/v1/content/category-tree?locale=lt').then(r=>r.json())")
        def walk(nodes, path):
            for n in nodes:
                m = re.search(r"/c/(SH-?[\d-]+)", n.get("url") or "")
                p = path + [n.get("name") or ""]
                if m: out[m.group(1).replace("SH", "SH-").replace("SH--", "SH-")] = p
                walk(n.get("descendants") or [], p)
        walk(tree.get("categories") or [], [])
    except Exception as e:
        print("   Rimi kategorijų medis:", e)
    return out

def crawl_rimi_offers(page, url):
    items, seen = {}, set()
    tree = None
    for n in range(0, 90):
        u = f"{url}?currentPage={n + 1}&pageSize=100" if n else f"{url}?pageSize=100"
        try:
            page.goto(u, wait_until="domcontentloaded", timeout=90000)
            try: page.wait_for_load_state("networkidle", timeout=12000)
            except Exception: pass
            cards = page.evaluate(RIMI_JS)
        except Exception as e:
            print("   Rimi akcijų klaida:", e); break
        new = [c for c in cards if c["id"] not in seen]
        if DEBUG and n < 2: dump(f"rimi_offers_{n}.json", json.dumps(cards[:60], ensure_ascii=False, indent=1))
        if not new and n and len(cards) < 5:   # tuščias puslapis – gal laikina klaida, bandom dar kartą
            page.wait_for_timeout(5000)
            try:
                page.goto(u, wait_until="domcontentloaded", timeout=90000); page.wait_for_timeout(3000)
                cards = page.evaluate(RIMI_JS); new = [c for c in cards if c["id"] not in seen]
            except Exception: pass
        if not new: print(f"   Rimi akcijos: pabaiga ties psl. {n + 1} (kortelių {len(cards)})"); break
        for c in new:
            seen.add(c["id"])
            name = (c["name"] or "").strip()
            reg = c["price"] or c["gtm"]
            price = c["label"] or reg
            if not name or not price: continue
            old = reg if c["label"] and reg and reg > price + 0.004 else None
            if tree is None: tree = rimi_tree(page)
            code = (c.get("cat") or "").replace("SH", "SH-").replace("SH--", "SH-")
            items[(name[:120], round(price, 2))] = ("", "", old, "", tree.get(code, []))
        print(f"   Rimi akcijos psl. {n + 1}: +{len(new)} (viso {len(items)})")
    note("rimi.lt e. parduotuvės akcijos", found=len(seen), parsed=len(items))
    return items

def crawl_promo(ctx, page, url, max_pages=60):
    """Promo: akcijos.lt leidinių puslapių paveikslėliai -> OCR (promo.py), tik patikrintos poros."""
    import promo
    page.goto(url, wait_until="domcontentloaded", timeout=90000)
    try: page.wait_for_load_state("networkidle", timeout=15000)
    except Exception: pass
    today = datetime.date.today().strftime("%Y%m%d")
    pubs = {}
    for h in page.eval_on_selector_all("a[href]", "e=>e.map(x=>x.href)"):
        m = re.search(r"akcijos\.lt/promo-cash-carry[\w-]*?-(\d{8})-(\d{8})/?$", h)
        if m and m.group(2) >= today: pubs[h.rstrip("/")] = (m.group(1), m.group(2))
    print(f"   Promo leidiniai: {len(pubs)}")
    items, done = {}, 0
    for pub, (a, b) in sorted(pubs.items(), key=lambda x: "indu" in x[0]):   # indų katalogas – paskutinis
        frm, until = f"{a[:4]}-{a[4:6]}-{a[6:]}", f"{b[:4]}-{b[4:6]}-{b[6:]}"
        try:
            page.goto(pub, wait_until="domcontentloaded", timeout=90000)
            try: page.wait_for_load_state("networkidle", timeout=15000)
            except Exception: pass
            imgs = page.eval_on_selector_all("img", "e=>e.map(x=>x.currentSrc||x.src||x.getAttribute('data-src')||'')")
            ids = [m.group(1) for x in imgs for m in [re.search(r"/publications/img/promo-cash-carry/(\d+)/page-\d+", x)] if m]
            if not ids: continue
            pid = max(set(ids), key=ids.count)
            nm = re.search(r"(\d+)\s*puslapi", page.inner_text("body")); n = int(nm.group(1)) if nm else 30
        except Exception as e:
            print("   Promo klaida:", pub, e); continue
        got = 0
        for k in range(1, n + 1):
            if done >= max_pages: break
            try:
                r = ctx.request.get(f"https://cdn.akcijos.lt/publications/img/promo-cash-carry/{pid}/page-{k}.jpg", timeout=60000)
                if r.status != 200: break
                res = promo.parse_image(r.body()); done += 1
            except Exception as e:
                print("   Promo OCR klaida:", e); continue
            for name, price, _ in res:
                items[(name, price)] = (until, frm, None); got += 1
        print(f"   Promo {pub.split('/')[-1]}: {n} psl., {got} prekių")
        note("akcijos.lt Promo leidiniai (OCR)", pubs=1, pages=min(n, max_pages), parsed=got)
    return items

def crawl_manoakcijos(ctx, page, slug, max_pages=60, parser="iki"):
    """manoakcijos.lt (Moja Gazetka) leidinių paveikslėliai -> OCR (iki.py): kaina = kiekis × kaina už kg/l."""
    import importlib
    mod = importlib.import_module(parser)
    page.goto(f"https://manoakcijos.lt/parduotuves/{slug}", wait_until="domcontentloaded", timeout=90000)
    try: page.wait_for_load_state("networkidle", timeout=15000)
    except Exception: pass
    imgs = page.eval_on_selector_all("img", "e=>e.map(x=>x.currentSrc||x.src||'')")
    dirs = {}
    for x in imgs:
        m = re.search(r"app\.manoakcijos\.lt/((\d{6})_(\d{6})_" + re.escape(slug) + r"_(\w+))/image00", x)
        if m: dirs[m.group(1)] = ("20" + m.group(3)[:2] + "-" + m.group(3)[2:4] + "-" + m.group(3)[4:], "20" + m.group(2)[:2] + "-" + m.group(2)[2:4] + "-" + m.group(2)[4:])
    today = datetime.date.today().isoformat()
    dirs = {d: v for d, v in dirs.items() if v[1] >= today}
    print(f"   manoakcijos {slug}: {len(dirs)} leidiniai")
    items, done = {}, 0
    for d, (frm, until) in dirs.items():
        got = 0
        for k in range(1, 40):
            if done >= max_pages: break
            try:
                r = ctx.request.get(f"https://app.manoakcijos.lt/{d}/image{k:02d}.webp", timeout=60000)
                if r.status != 200: break
                res = mod.parse_image(r.body()); done += 1
            except Exception as e:
                print("   OCR klaida:", e); continue
            for name, price in res: items[(name, price)] = (until, frm, None); got += 1
        print(f"   {d}: {k - 1} psl., {got} prekių")
        note("manoakcijos.lt leidiniai (OCR)", pubs=1, pages=k - 1, parsed=got)
    return items

def ak_leaflet(html):
    """akcijuseklys.lt leidinio puslapyje įdėtas JSON su visomis leidinio prekėmis -> [(pavadinimas, kaina, nuo, iki, sena, žymė)]."""
    m = next((m for m in re.finditer(r"<script[^>]*>(\{\"pages\".*?)</script>", html, re.S)), None)
    if not m: return None
    d = json.loads(m.group(1)); out = []
    for x in d.get("deals", []):
        if not x.get("promoPrice") or not x.get("title"): continue   # grupinė nuolaida be kainos („-25 % gėrimams“) – nerodom
        price = float(x["promoPrice"]); old = float(x["regularPrice"]) if x.get("regularPrice") else None
        det = re.sub(r"^(įvairių (spalvų|rūšių|dydžių|dizainų)[,;]?\s*)", "", (x.get("details") or "")).strip(" ,;")
        if re.search(r"kainos parduotuvėse|nurodytos su nuolaida", det, re.I): det = ""
        det = re.sub(r"[,;]?\s*1\s*(kg|l)\s*(grynosios masės\s*)?(kaina\s*)?[-–—]\s*\d+[,.]\d{2}\s*€?", "", det).strip(" ,;")   # kaina už kg – programėlė skaičiuoja pati
        title = re.sub(r"\s+", " ", x["title"]).strip()
        name = f"{title}, {det}" if det and det.lower() not in title.lower() else title
        deal = "su kortele" if x.get("loyaltyCardRequired") else ""
        frm, until = (x.get("activeFrom") or "")[:10], (x.get("activeTo") or "")[:10]
        if 0.05 < price < 2000: out.append((name[:140], round(price, 2), frm, until, old if old and old > price else None, deal))
    return out

def crawl_akcijuseklys(ctx, slug):
    """akcijuseklys.lt: kiekvieno leidinio puslapyje – visų prekių JSON (pavadinimas, kaina, sena kaina, galiojimas)."""
    base = "https://www.akcijuseklys.lt"
    get = lambda u: ctx.request.get(u, timeout=60000, headers={"Accept-Language": "lt-LT,lt;q=0.9"})
    r = get(f"{base}/parduotuve/{slug}")
    if r.status != 200: print("   akcijuseklys:", r.status); return {}
    links = list(dict.fromkeys(re.findall(r'href="(/parduotuve/' + re.escape(slug) + r'/br_[0-9a-f]+)"', r.text())))
    today = datetime.date.today().isoformat(); items = {}
    for ln in links[:6]:
        r = get(base + ln)
        if r.status != 200: continue
        deals = ak_leaflet(r.text()) or []
        live = [d for d in deals if not d[3] or d[3] >= today]
        if deals and not live: continue   # pasibaigęs leidinys
        for name, price, frm, until, old, deal in live: items[(name, price)] = (until, frm, old, deal)
        print(f"   akcijuseklys {ln}: {len(live)} prekių su kaina")
        note("akcijuseklys.lt leidiniai", pubs=1, found=len(live), parsed=len(live))
        time.sleep(0.5)
    return items

def crawl_leaflets(ctx, page, store, c):
    if c.get("akcijuseklys"):
        try:
            items = crawl_akcijuseklys(ctx, c["akcijuseklys"])
            if items: return items
        except Exception as e:
            print("   akcijuseklys klaida:", e)
    if c.get("manoakcijos"):
        try: return crawl_manoakcijos(ctx, page, c["manoakcijos"], parser=c.get("parser", "iki"))
        except Exception as e:
            print("   manoakcijos klaida:", e); return {}
    if c.get("promo_akcijos"):
        try: return crawl_promo(ctx, page, c["promo_akcijos"])
        except Exception as e:
            print("   Promo klaida:", e); return {}
    pre = {}
    if c.get("rimi_offers"):   # e. parduotuvės akcijos + toliau savaitinis leidinys (sujungiama)
        try: pre = crawl_rimi_offers(page, c["rimi_offers"])
        except Exception as e: print("   Rimi akcijų klaida:", e)
    if c.get("offers_url"):
        try:
            items = crawl_maxima_offers(page, c["offers_url"])
            if len(items) >= 30:
                today = datetime.date.today().isoformat()
                return {k: u for k, u in items.items() if not u[0] or u[0] >= today}
        except Exception as e:
            print("   Maxima pasiūlymų klaida:", e)
    if c.get("norfa"):
        items = crawl_norfa(ctx, page, c["pages"][0])
        today = datetime.date.today().isoformat()
        return {k: u for k, u in items.items() if not u[0] or u[0] >= today}
    year = datetime.date.today().year
    pdfs = set(c.get("pdfs", [])); viewers = set(c.get("viewers", []))
    for u in c.get("pages", []):
        p, v = find_pdfs(page, u, c.get("viewer_regex")); pdfs |= p; viewers |= v
    for v in list(viewers):   # Rimi: naujas savaitinis leidinys kartais pasirodo anksčiau nei nuoroda puslapyje
        m = re.search(r"(savaitinis-leidinys-nr-)(\d+)", v)
        if m: viewers.add(v.replace(m.group(0), m.group(1) + str(int(m.group(2)) + 1)))
    if not viewers and not pdfs:   # nieko neradom - bandom pačius puslapius kaip peržiūrą
        viewers = set(c.get("pages", []))
        print(f"   {store}: nuorodų nerasta, bandom pačius puslapius")
    items, texts = {}, []
    for k, v in enumerate(sorted(viewers)[:c.get("max_viewers", 6)]):
        p, imgs, jsons, vtext = crawl_viewer(ctx, v, store, k)
        pdfs |= p
        print(f"   peržiūra {v[-50:]}: pdf {len(p)}, paveikslėlių {len(imgs)}, json prekių {len(jsons)}")
        jr = leaflets.valid_range(vtext, year) if vtext else ("", "")
        for n, pr in jsons: items[(n, pr)] = (jr[1], jr[0], None)
        if vtext.strip() and not jsons:
            if DEBUG: dump(f"text_{store}_{k}.txt", vtext[:30000])
            res = (leaflets.parse_maxima(vtext, year) if leaflets.is_maxima_text(vtext) else leaflets.parse_ipaper(vtext, year) if leaflets.is_ipaper_text(vtext) else leaflets.parse_text(vtext, year))
            print(f"      tekstas: {len(res)} prekių")
            note("leidinys (iPaper tekstas)", pubs=1, parsed=len(res))
            for r in res: items[(r[0], r[1])] = (r[2], r[3], r[4] if len(r) > 4 else None)
        if not p and not items:
            txt = "\n".join(ocr_image(b) for u2, b in list(imgs.items())[:60])
            if DEBUG: dump(f"ocr_{store}_{k}.txt", txt[:20000])
            if txt.strip():
                res = leaflets.parse_text(txt, year)
                print(f"      OCR: {len(res)} prekių")
                for r in res: items[(r[0], r[1])] = (r[2], r[3], r[4] if len(r) > 4 else None)
    print(f"{store}: rasta {len(pdfs)} PDF, {len(viewers)} peržiūros nuorodų")
    pdfs = {u for u in pdfs if not re.search(r"NE-MAISTO|Zaislu|Tapk-LIDL", u, re.I)}
    for u in sorted(pdfs)[:12]:
        try:
            body = ctx.request.get(u, timeout=400000).body()
            with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
                f.write(body); f.flush()
                res, mode = leaflets.parse_pdf(f.name, store=store)
                if DEBUG: dump("pdftext_" + re.sub(r"\W+", "_", u)[-40:] + ".txt", leaflets.pdf_text(f.name)[0][:15000]);
            print(f"   {u[-60:]}: {len(res)} prekių ({mode})")
            note("leidinių PDF", pubs=1, parsed=len(res))
            d0 = PDF_DATES.get(u, ("", ""))
            for r in res: items[(r[0], r[1])] = (r[2] or d0[1], r[3] or d0[0], r[4] if len(r) > 4 else None)
        except Exception as e:
            print("   PDF klaida:", u, e)
    today = datetime.date.today().isoformat()
    items = {k: u for k, u in items.items() if not u[0] or u[0] >= today}
    if pre: print(f"   {store}: leidinys {len(items)} + e. parduotuvės akcijos {len(pre)}")
    for k, u in pre.items(): items.setdefault(k, u)
    return items

def _clean_score(n):
    """Kuo „švaresnis“ pavadinimas: lietuviškos raidės +, keisti simboliai -."""
    return len(re.findall(r"[ąčęėįšųūžĄČĘĖĮŠŲŪŽ]", n)) - 3 * len(re.findall(r"[\"'|<>{}\[\]~^]", n)) - 0.01 * len(n)

def dedupe(items, only=()):
    """Ta pati prekė iš kelių leidinio versijų (OCR pavadinimas šiek tiek skiriasi): ta pati parduotuvė, kaina,
    kiekis ir pirmi žodžiai -> paliekam švariausią pavadinimą."""
    best, rest = {}, []
    for it in items:
        if it[0] not in only: rest.append(it); continue
        n = categories.norm(it[1])
        words = [w for w in re.findall(r"[a-z]{3,}", n.replace("y", "u"))][:2]
        size = re.findall(r"\d+(?:[.,]\d+)?\s*(?:kg|g|ml|l|vnt)\b", n)
        k = (it[0], it[2], " ".join(words), size[-1].replace(" ", "") if size else "")
        if k not in best or _clean_score(it[1]) > _clean_score(best[k][1]): best[k] = it
    return rest + list(best.values())

def cat_of(n, u):
    c = categories.classify(n)
    if c == "kita" and len(u) > 4 and u[4]: c = categories.classify_hint(u[4])
    return c

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store"); ap.add_argument("--probe"); ap.add_argument("--pdf")
    ap.add_argument("--local", action="store_true", help="tavo kompiuteryje: tikras Chrome langas")
    a = ap.parse_args()
    if a.pdf:
        res, mode = leaflets.parse_pdf(a.pdf)
        print(mode, len(res))
        for r in res[:40]: print(r)
        return
    cfg = {k: v for k, v in json.load(open(HERE / "stores.json", encoding="utf-8")).items() if not k.startswith("_")}
    with sync_playwright() as pw:
        if a.local:
            try: br = pw.chromium.launch(channel="chrome", headless=False)
            except Exception: br = pw.chromium.launch(headless=False)
        else:
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
        if old.get("v") not in (10, 11): old = {"stores": [], "items": []}   # seni (šlamštiniai) duomenys nebelaikomi
        oldmap = {}
        for i in old["items"]:
            s, n, p, k = old["stores"][i[0]], i[1], i[2], i[3]; u = (i[4] if len(i) > 4 else "", i[5] if len(i) > 5 else "", i[6] if len(i) > 6 else None, i[8] if len(i) > 8 else "")
            oldmap.setdefault((s, k), {})[(n, p)] = u
        stores = list(cfg)
        new, status = {}, {}
        for store, c in cfg.items():
            if a.store and store not in a.store.split(","): continue
            st = {}; CUR["store"] = store; t0 = time.time()
            for kind, key, fn in (("e", "catalog", lambda: crawl_catalog(page, store, c["catalog"])),
                                  ("l", "leaflets", lambda: crawl_leaflets(ctx, page, store, c["leaflets"]))):
                if not c.get(key, {}).get("enabled"): continue
                try: got = fn()
                except Exception as e: got = {}; print(store, key, "klaida:", e)
                prev = oldmap.get((store, kind), {})
                if prev and len(got) < 0.3 * len(prev):
                    st["warn"] = f"rasta tik {len(got)} (anksčiau {len(prev)}) – palikti ankstesni duomenys"; st[key] = len(prev); got = prev
                else:
                    st[key] = len(got)
                new[(store, kind)] = got
            st.update(STATS.get(store, {})); st["seconds"] = round(time.time() - t0)
            if c.get("info"): st["info"] = c["info"]
            status[store] = st
        br.close()
    out_items = []
    OCR = {"IKI", "Promo"}
    vocab = fixnames.build_vocab([n for st in stores if st not in OCR for (n, _p) in new.get((st, "l"), oldmap.get((st, "l"), {}))])
    for store in stores:
        for kind in ("l",):
            d = new.get((store, kind), oldmap.get((store, kind), {}))
            for (n, p), u in d.items():
                if store in OCR:
                    n = re.sub(r"\s[\"'|~^]+[^\W\d_]{0,2}(?=\s)", "", fixnames.restore(n, vocab))
                if fixnames.is_fragment(n): continue
                out_items.append([stores.index(store), n, p, kind, u[0], u[1], u[2] if len(u) > 2 else None, categories.IDS.index(cat_of(n, u)), u[3] if len(u) > 3 else ""])
    out_items = dedupe(out_items, {stores.index(s) for s in OCR if s in stores})
    out_items.sort(key=lambda x: (x[1], x[2]))
    for _s in cfg:
        if _s not in status and _s in old.get("status", {}): status[_s] = old["status"][_s]   # nevykdyta – paliekam seną informaciją
    out = {"v": 11, "run": {"url": os.environ.get("RUN_URL", ""), "event": os.environ.get("EVENT", "")}, "cats": [{"id": c[0], "name": c[1], "icon": c[2]} for c in categories.META], "updated": datetime.datetime.now(datetime.timezone.utc).isoformat(), "stores": stores, "status": status, "items": out_items}
    (ROOT / "prices.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False, indent=1), "iš viso:", len(out_items))

if __name__ == "__main__":
    main()
