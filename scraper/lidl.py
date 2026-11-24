"""Lidl leidinio PDF -> prekės pagal teksto padėtį puslapyje (pdftotext -bbox-layout).
Lidl leidinyje kiekvienos prekės blokai: pavadinimas (vidutinis šriftas), aprašas su svoriu ir „1 kg = X €“
(mažas šriftas), prekės kodas (labai mažas) ir didelė kaina. Juos susiejame pagal atstumą ir patikriname
pagal vieneto kainą, kai ji nurodyta."""
import html, re, subprocess
from statistics import median

PRICE = re.compile(r"(?<![\d,])(\d{1,3}),(\d{2})(?!\d)")
EURO_INT = re.compile(r"^(\d{1,4})\s*€$")
WEIGHT = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:x\s*(\d+(?:[.,]\d+)?)\s*)?(kg|g|ml|l)\b", re.I)
UNITP = re.compile(r"1\s*(kg|l)\s*=\s*(\d{1,3}),(\d{2})", re.I)
NOT_NAME = re.compile(r"^(perkant|antram|antrai|su lidl plus|daugiau|nuo\b|super|kaina|prekių kiekis|www\.|brandinta|naujiena|verta|lidl|ieškoti|įvairių rūšių|kaina nuo|pigiau|\d|[-–*%])", re.I)
DATE = re.compile(r"(\d{2})\s*(\d{2})\s*,?\s*iki\s*(\d{2})\s*(\d{2})", re.I)


def _blocks(xml):
    pages = []
    for p in re.finditer(r"<page [^>]*>(.*?)</page>", xml, re.S):
        bl = []
        for b in re.finditer(r'<block xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</block>', p.group(1), re.S):
            lines, hs = [], []
            for l in re.finditer(r"<line[^>]*>(.*?)</line>", b.group(5), re.S):
                ws = re.findall(r'<word xMin="[\d.]+" yMin="([\d.]+)" xMax="[\d.]+" yMax="([\d.]+)">(.*?)</word>', l.group(1))
                if ws:
                    lines.append(" ".join(html.unescape(w[2]) for w in ws))
                    hs += [float(w[1]) - float(w[0]) for w in ws]
            if lines:
                x0, y0, x1, y1 = map(float, b.groups()[:4])
                bl.append({"x0": x0, "y0": y0, "x1": x1, "y1": y1, "h": max(hs), "lines": lines, "t": " ".join(lines)})
        pages.append(bl)
    return pages


def _merge_names(names):
    """Sujungia pavadinimo blokus, kurie vienas po kito tame pačiame stulpelyje (pvz. „DELUXE“ + „Keksas…“)."""
    names = sorted(names, key=lambda b: (b["x0"], b["y0"]))
    out = []
    for b in names:
        p = out[-1] if out else None
        if p and abs(p["x0"] - b["x0"]) < 6 and 0 <= b["y0"] - p["y1"] < 5:
            p["lines"] += b["lines"]; p["t"] += " " + b["t"]; p["y1"] = b["y1"]; p["x1"] = max(p["x1"], b["x1"])
        else:
            out.append(dict(b, lines=list(b["lines"])))
    return out


def _weight_kg(text):
    m = WEIGHT.search(text.replace(",", "."))
    if not m: return None, ""
    q = float(m.group(1)) * (float(m.group(2)) if m.group(2) else 1)
    u = m.group(3).lower()
    return (q / 1000 if u in ("g", "ml") else q), m.group(0)


def parse_page(bl):
    if not bl: return []
    desc_hs = [b["h"] for b in bl if UNITP.search(b["t"]) or re.search(r"\b\d+\s*(g|ml|vnt)\b", b["t"])]
    dh = median(desc_hs) if desc_hs else 9.5
    big = [b for b in bl if b["h"] >= 30 and (PRICE.search(b["lines"][0]) or EURO_INT.match(b["lines"][0].strip()))]
    small = [b for b in bl if b["h"] < 20 and re.fullmatch(r"\s*\d{1,3},\d{2}\s*", b["t"])]
    names = [b for b in bl if dh + 1.2 <= b["h"] <= 18 and len(re.findall(r"[^\W\d_]", b["t"])) >= 4
             and not NOT_NAME.search(b["lines"][0].strip()) and "=" not in b["t"]]
    descs = [b for b in bl if abs(b["h"] - dh) < 1.2]
    names = _merge_names(names)

    cands = []
    for ni, n in enumerate(names):
        # aprašas: blokai po pavadinimu tame pačiame stulpelyje
        d = " ".join(b["t"] for b in descs if abs(b["x0"] - n["x0"]) < 12 and 0 <= b["y0"] - n["y1"] < 45)
        wkg, wtxt = _weight_kg(d)
        um = UNITP.search(d)
        unit = float(um.group(2) + "." + um.group(3)) if um else None
        for pi, p in enumerate(big):
            m = PRICE.search(p["lines"][0])
            price = float(m.group(1) + "." + m.group(2)) if m else float(EURO_INT.match(p["lines"][0].strip()).group(1))
            dx = p["x0"] - n["x0"]; dy = p["y0"] - n["y0"]
            if dx < -40 or dx > 190 or dy < -45 or dy > 170: continue
            dist = (dx * dx + (dy * 1.3) ** 2) ** 0.5
            ok = wkg and unit and abs(price / wkg - unit) / unit < 0.04
            score = dist - (400 if ok else 0)
            cands.append((score, ni, pi, price, wtxt, d))
    cands.sort()
    used_n, used_p, out = set(), set(), []
    for score, ni, pi, price, wtxt, d in cands:
        if ni in used_n or pi in used_p: continue
        used_n.add(ni); used_p.add(pi)
        n, p = names[ni], big[pi]
        name = re.sub(r"\s+", " ", " ".join(n["lines"])).strip()
        name = re.sub(r"(?<=[a-ząčęėįšųūž])-\s(?=[a-ząčęėįšųūž])", "", name)
        if wtxt and wtxt not in name: name += ", " + wtxt
        old = None
        for s in small:  # perbraukta sena kaina – mažas skaičius šalia didžiosios
            if -5 < s["x0"] - p["x1"] < 30 and -5 < s["y0"] - p["y0"] < 40:
                v = float(s["t"].strip().replace(",", "."))
                if price < v < price * 3: old = v
        if 0.05 < price < 500:
            out.append((name[:120], round(price, 2), old))
    return out


BIGP = re.compile(r"^(\d{1,4})(?:[,.](\d{2}))?\s*€?\s*\*?$")
OLDP = re.compile(r"(\d{1,4}),(\d{2})\s*$")
CODE = re.compile(r"^\d{6}$")


def parse_page_codes(bl):
    """Ne maisto leidinio maketas: pavadinimas (šriftas ~12) → aprašas → 6 skaitmenų prekės kodas; šalia stambi
    kaina („30€*“, „69,99*“) ir virš jos sena kaina su nuolaida („-50﹪ 59,99“). Prekes atpažįstam nuo kodo."""
    codes = [b for b in bl if CODE.match(b["t"].strip()) and b["h"] < 9]
    if not codes: return []
    prices = [b for b in bl if b["h"] >= 38 and BIGP.match(b["t"].strip().replace(" ", ""))]
    titles = [b for b in bl if 11.3 <= b["h"] <= 12.7 and len(re.findall(r"[^\W\d_]", b["t"])) >= 4]
    cands = []
    for ci, c in enumerate(codes):
        for pi, p in enumerate(prices):
            dx, dy = p["x0"] - c["x0"], p["y0"] - c["y0"]
            if -40 < dx < 230 and -150 < dy < 90:
                cands.append(((dx * dx + (dy * 1.5) ** 2) ** 0.5, ci, pi))
    cands.sort(); used_c, used_p, out = set(), set(), []
    for _, ci, pi in cands:
        if ci in used_c or pi in used_p: continue
        c, p = codes[ci], prices[pi]
        above = [t for t in titles if abs(t["x0"] - c["x0"]) < 15 and 0 < c["y0"] - t["y0"] < 130]
        if not above: continue
        used_c.add(ci); used_p.add(pi)
        t = max(above, key=lambda t: t["y0"])
        m = BIGP.match(p["t"].strip().replace(" ", "")); price = int(m.group(1)) + (int(m.group(2)) / 100 if m.group(2) else 0)
        old = None
        for o in bl:   # „-50﹪ 59,99“ tiesiai virš stambios kainos
            if 10 < o["h"] < 38 and -15 < o["x0"] - p["x0"] < 40 and 0 < p["y0"] - o["y0"] < 40:
                mo = OLDP.search(o["t"])
                if mo and price < int(mo.group(1)) + int(mo.group(2)) / 100 < price * 4: old = int(mo.group(1)) + int(mo.group(2)) / 100
        name = re.sub(r"\s+", " ", t["t"]).strip()
        if 0.3 < price < 3000: out.append((name[:120], round(price, 2), old))
    return out


def parse(path):
    xml = subprocess.run(["pdftotext", "-bbox-layout", str(path), "-"], capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=900).stdout
    return parse_xml(xml)


def parse_xml(xml):
    res = []
    for bl in _blocks(xml):
        page = parse_page(bl)
        names = {n.split(",")[0].lower() for n, _, _ in page}
        for n, p, o in parse_page_codes(bl):   # ne maisto puslapiai: prekės, kurių maisto maketo skaitytuvas nerado
            if n.lower() not in names: page.append((n, p, o))
        for name, price, old in page:
            res.append((name, price, "", "", old))
    return list(dict.fromkeys(res))
