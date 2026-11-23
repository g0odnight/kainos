import json, pathlib, re
HERE = pathlib.Path(__file__).resolve().parent
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
NAME_KEYS = ("name", "title", "productName", "product_name", "displayName")
PRICE_KEYS = ("price", "currentPrice", "salePrice", "finalPrice", "regularPrice", "priceValue")
PRICE_RE = re.compile(r"(?<!\d)(\d{1,3}[.,]\d{2})(?!\d)")

def num(v):
    try:
        if isinstance(v, str):
            m = PRICE_RE.search(v.replace("\xa0", " "))
            if not m: return None
            v = m.group(1).replace(",", ".")
        f = float(v)
        return round(f, 2) if 0.05 < f < 500 else None
    except Exception:
        return None

def get_price(o):
    for k in PRICE_KEYS:
        v = o.get(k)
        if isinstance(v, dict):
            v = next((v[x] for x in ("amount", "value", "current", "price") if x in v), None)
        p = num(v) if v is not None else None
        if p: return p
    off = o.get("offers")
    if isinstance(off, list) and off: off = off[0]
    if isinstance(off, dict): return get_price(off)
    return None

def walk(o, out):
    """Ieško bet kur JSON'e objektų su pavadinimu ir kaina."""
    if isinstance(o, dict):
        n = next((o[k] for k in NAME_KEYS if isinstance(o.get(k), str) and len(o[k]) > 3), None)
        p = get_price(o)
        if n and p: out.append((n.strip(), p))
        for v in o.values(): walk(v, out)
    elif isinstance(o, list):
        for v in o: walk(v, out)

CARD_JS = """(els)=>{const out=[],seen=new Set();for(const a of els){let c=a,t='';for(let i=0;i<7&&c;i++){const x=c.innerText||'';if(/\\d[.,]\\d{2}\\s*€|€\\s*\\d/.test(x)){t=x;break}c=c.parentElement}
if(!t||seen.has(t))continue;seen.add(t);const img=a.querySelector('img')||(c&&c.querySelector('img'));out.push([(a.innerText||'').trim(),a.getAttribute('title')||a.getAttribute('aria-label')||'',img?(img.alt||''):'',t])}return out}"""

def card_items(page, link_sel):
    """Be selektorių klasių: paima nuorodas į prekes ir artimiausią tėvinį bloką su kaina €."""
    out = []
    try:
        for a, title, alt, block in page.eval_on_selector_all(link_sel, CARD_JS):
            name = next((x.strip() for x in (title, alt, a, block.split("\n")[0]) if x and len(x.strip()) > 3), "")
            name = name.split("\n")[0]
            p = num(block.replace("\n", " "))
            if name and p: out.append((name, p))
    except Exception as e:
        print("   kortelių klaida:", e)
    return out

def from_dom(page, sel):
    out = []
    try:
        for t in page.eval_on_selector_all('script[type="application/ld+json"]', "e=>e.map(x=>x.textContent)"):
            try: walk(json.loads(t), out)
            except Exception: pass
        if sel and sel.get("link"):
            out.extend(card_items(page, sel["link"]))
        if sel and sel.get("item"):
            rows = page.eval_on_selector_all(
                sel["item"],
                "(els,s)=>els.map(e=>{const n=e.querySelector(s.name),p=e.querySelector(s.price);return [n?n.innerText:'',p?p.innerText:'']})",
                sel)
            for n, p in rows:
                n = (n or "").strip().split("\n")[0]; pv = num(p)
                if len(n) > 3 and pv: out.append((n, pv))
    except Exception as e:
        print("   dom klaida:", e)
    return out

def scrape_page(page, url, sel, debug_tag=None, links=False):
    """Atidaro puslapį, grąžina [(pavadinimas, kaina)] iš XHR JSON, JSON-LD ir DOM selektorių."""
    found, blobs, hrefs = [], [], []
    def on_resp(r):
        try:
            if "json" in (r.headers.get("content-type") or ""):
                items = []; walk(r.json(), items)
                if items: found.extend(items); blobs.append((r.url, items[:3]))
        except Exception:
            pass
    page.on("response", on_resp)
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=90000)
        try: page.wait_for_load_state("networkidle", timeout=12000)
        except Exception: pass
        for _ in range(3):
            page.mouse.wheel(0, 3000); page.wait_for_timeout(400)
        dom = from_dom(page, sel); found.extend(dom)
        hrefs = []
        if links:
            hrefs = page.eval_on_selector_all("a[href]", "e=>e.map(x=>x.href.split('#')[0])")
        if debug_tag:
            d = HERE / "debug"; d.mkdir(exist_ok=True)
            (d / f"{debug_tag}.html").write_text(page.content()[:300000], encoding="utf-8")
            (d / f"{debug_tag}.json").write_text(json.dumps({"url": url, "dom_items": len(dom), "json_hits": blobs[:8]}, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception as e:
        print("   klaida:", url, e)
    finally:
        page.remove_listener("response", on_resp)
    res = list(dict.fromkeys(found))
    return (res, hrefs) if links else res


LNAME = ("title", "name", "productname", "product_name", "headline", "label", "heading", "description", "text")
def _lnum(v):
    if isinstance(v, bool): return None
    if isinstance(v, (int, float)):
        f = float(v); return round(f, 2) if 0.05 < f < 500 else None
    if isinstance(v, str): return num(v)
    return None

def _lprice(d, depth=0):
    """Ieško kainos bet kuriame rakte, kurio varde 'price'/'kaina'/'amount'."""
    for k, v in d.items():
        kl = str(k).lower()
        if (any(x in kl for x in ("price", "kaina", "amount")) or (depth > 0 and kl in ("value", "current", "now"))) and "old" not in kl and "regular" not in kl and "before" not in kl:
            if isinstance(v, dict) and depth < 2:
                p = _lprice(v, depth + 1)
                if p: return p
            elif isinstance(v, list) and v and isinstance(v[0], dict) and depth < 2:
                p = _lprice(v[0], depth + 1)
                if p: return p
            else:
                p = _lnum(v)
                if p: return p
    return None

def walk_loose(o, out):
    """Laisvesnis variantas: bet koks dict su tekstiniu pavadinimu ir kaina viename ar giliau rakte (raktai nejautrūs raidžių dydžiui)."""
    if isinstance(o, dict):
        low = {str(k).lower(): v for k, v in o.items()}
        n = next((low[k] for k in LNAME if isinstance(low.get(k), str) and len(low[k].strip()) > 3), None)
        p = _lprice(o)
        if n and p: out.append((n.strip().replace("\n", " ")[:140], p))
        for v in o.values(): walk_loose(v, out)
    elif isinstance(o, list):
        for v in o: walk_loose(v, out)
