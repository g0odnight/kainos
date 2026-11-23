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

def from_dom(page, sel):
    out = []
    try:
        for t in page.eval_on_selector_all('script[type="application/ld+json"]', "e=>e.map(x=>x.textContent)"):
            try: walk(json.loads(t), out)
            except Exception: pass
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

def scrape_page(page, url, sel, debug_tag=None):
    """Atidaro puslapį, grąžina [(pavadinimas, kaina)] iš XHR JSON, JSON-LD ir DOM selektorių."""
    found, blobs = [], []
    def on_resp(r):
        try:
            if "json" in (r.headers.get("content-type") or ""):
                items = []; walk(r.json(), items)
                if items: found.extend(items); blobs.append((r.url, items[:3]))
        except Exception:
            pass
    page.on("response", on_resp)
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        try: page.wait_for_load_state("networkidle", timeout=12000)
        except Exception: pass
        for _ in range(3):
            page.mouse.wheel(0, 3000); page.wait_for_timeout(400)
        dom = from_dom(page, sel); found.extend(dom)
        if debug_tag:
            d = HERE / "debug"; d.mkdir(exist_ok=True)
            (d / f"{debug_tag}.html").write_text(page.content()[:300000], encoding="utf-8")
            (d / f"{debug_tag}.json").write_text(json.dumps({"url": url, "dom_items": len(dom), "json_hits": blobs[:8]}, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception as e:
        print("   klaida:", url, e)
    finally:
        page.remove_listener("response", on_resp)
    return list(dict.fromkeys(found))
