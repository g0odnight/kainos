"""Šilo leidinio puslapių paveikslėliai (manoakcijos.lt) -> prekės.
Šilo maketas: stambi kaina („3 85 €“, sena kaina perbraukta), po ja pavadinimas, smulkiai kiekis ir kaina už kg/l:
„atvėsinta; 400 g“ + „1 kg – 9,63 €“. Stilizuotą stambią kainą OCR skaito prastai, todėl kainą apskaičiuojame:
kiekis × kaina už kg/l (lygiai kaip IKI), o centus patikriname pagal šalia perskaitytus stambius skaitmenis."""
import re
from promo import ocr_lines

UNIT = re.compile(r"1\s*(kg|k[gq9]|[lI1|/!])\s*[-–—~=]+\s*(\d{1,2}\s*[,.]\s*[\dSO]{2}|\d{3}|\d[,.]?[\dSO]{2})(?![\d,])", re.I)
QTY = re.compile(r"(?:(\d+)\s*[x×]\s*)?(\d+(?:[.,]\d+)?)\s*(kg|g|ml|l)\b(?!\s*[-–—])", re.I)
LQTY = re.compile(r"(?:(\d+)\s*[x×]\s*)?(\d+(?:[.,]\d+)?)(\s*(?:ml|[lI!|]|1)\b)?")
STOP = re.compile(r"Kainos galioja|Pažymėtas|prekybos centr|ŠILAS\b|Taros|u[zž]stat", re.I)


def _near(l, u):
    return abs(l["x0"] - u["x0"]) < 120


def _num(s):
    s = re.sub(r"\s", "", s).upper().replace("S", "5").replace("O", "0")
    if "," in s or "." in s: a, b = re.split(r"[,.]", s); return int(a) + int(b) / 100
    return int(s[:-2] or 0) + int(s[-2:]) / 100


def _liters(before):
    """„0,75 !“, „0,355 1“, „1,51“ (=1,5 l), „21“ (=2 l), „2!“, „(0,75 I)“ -> galimi kiekiai litrais."""
    ms = list(LQTY.finditer(before))
    if not ms: return [], None
    m = ms[-1]; v, u = m.group(2), (m.group(3) or "").strip().lower()
    mult = int(m.group(1)) if m.group(1) else 1
    c = []
    if u == "ml": c = [float(v.replace(",", ".")) / 1000]
    elif "," in v or "." in v:
        c = [float(v.replace(",", "."))]
        if not u and v.endswith("1") and len(v.split(",")[-1].split(".")[-1]) > 1: c.append(float(v[:-1].replace(",", ".")))
    elif u: c = [float(v)]
    elif v.endswith("1") and len(v) in (2, 3): c = [float(v[:-1]) if len(v) == 2 else float(v[0] + "." + v[1])]
    return [x * mult for x in c if 0.1 <= x * mult <= 10], m


def _prices(q, unit):
    """Leidinyje kaina už kg/l = round(kaina / kiekis) -> visos kainos, kurios duoda tą pačią kainą už kg/l."""
    lo, hi = (unit - 0.005) * q, (unit + 0.005) * q
    return [c / 100 for c in range(int(lo * 100), int(hi * 100) + 2) if lo - 1e-9 <= c / 100 <= hi + 1e-9]


def parse_lines(lines):
    out, used = [], set()
    for u in lines:
        um = UNIT.search(u["t"])
        if not um or STOP.search(u["t"]): continue
        per_kg = um.group(1).lower().startswith("k")
        unit = _num(um.group(2))
        if not 0.05 <= unit <= 200: continue
        # eilutės virš (pavadinimas, kiekis) tame pačiame stulpelyje
        block, top = [u], u
        for _ in range(7):
            up = [l for l in lines if l is not top and id(l) not in used and _near(l, u) and not STOP.search(l["t"])
                  and -20 <= top["y0"] - l["y1"] < max(28, top["h"] * 1.2) and l["y0"] < top["y0"] - 5 and l["h"] < 70 and not UNIT.search(l["t"])]
            if not up: break
            top = max(up, key=lambda l: l["y1"]); block.insert(0, top)
        text = re.sub(r"\s+", " ", " ".join(l["t"] for l in block)).strip()
        before = text[:text.find(um.group(0))] if um.group(0) in text else text
        before = before.strip(" ;,(")
        if per_kg:
            # OCR klaidos kiekyje: „3108“ = „310g“, „430“ (g nenuskaitytas) – tik eilutės gale
            before = re.sub(r"(?<![\d,.])(\d{2,3})8\s*\)?$", r"\1 g", before)
            if not QTY.search(before): before = re.sub(r"(?<![\d,.%])(\d{2,3})\s*\)?$", r"\1 g", before)
            qms = [m for m in QTY.finditer(before) if m.group(3).lower() in ("g", "kg")]
            if not qms: continue
            qm = qms[-1]
            q = float(qm.group(2).replace(",", ".")) * (int(qm.group(1)) if qm.group(1) else 1)
            qs = [q / 1000 if qm.group(3).lower() == "g" else q]
            qtxt = qm.group(0)
        else:
            qs, qm = _liters(before)
            if not qs: continue
            qtxt = f"{qs[0]:g} l".replace(".", ",")
        qs = [q for q in qs if 0.02 <= q <= 10]
        cands = sorted({p for q in qs for p in _prices(q, unit)})
        if not cands: continue
        if len(cands) > 1:   # keli variantai – sprendžiam pagal stambius skaitmenis virš pavadinimo
            bx0, by0 = min(l["x0"] for l in block), block[0]["y0"]
            big = " ".join(l["t"] for l in lines if l["h"] >= 45 and -40 < l["x0"] - bx0 < 260 and 0 < by0 - l["y1"] < 260)
            digits = re.sub(r"\D", "", big)
            cands = [c for c in cands if f"{round(c * 100) % 100:02d}" in digits]
            if len(cands) != 1: continue
        price = cands[0]
        if not per_kg and len(qs) > 1:
            qtxt = f"{min(qs, key=lambda q: abs(q * unit - price)):g} l".replace(".", ",")
        name = before[:qm.start()].strip(" ,;:.-(")
        name = re.sub(r"^[^A-Za-zĄČĘĖĮŠŲŪŽąčęėįšųūž]+", "", name)
        while True:   # nuimam aprašo žodžius gale („virta; a. r.; griežinėliais“)
            n2 = re.sub(r"[\s;,.(]*(atv[eė]+sint\w*|at[sš]aldyt\w*|virt\w*|kept\w*|kar[sš]tai\s*r\w*|[sš]altai\s*r\w*|su[sš]aldyt\w*|a\.?\s*[rF£]\.?|gri[eė][zž]in\w*|\d*\s*r[uū][sš]i\w*|[iį]vairi\w*|\d*\s*(pak|vnt|unt|d[eė][zž])\.?|gazuot\w*|negazuot\w*|pasteriz\w*)[\s;,.(]*$", "", name, flags=re.I)
            if n2 == name: break
            name = n2
        name = re.sub(r"^([iį]vairi\w*\s*r\w[sš]i\w*|\d+\s*r[uū][sš]i\w*)[\s;,]*", "", name.strip(" ,;:.-("), flags=re.I)
        if len(re.findall(r"[^\W\d_]", name)) < 6 or len(re.findall(r"[^\W\d_]{3,}", name)) < 2: continue
        for l in block: used.add(id(l))
        out.append((f"{name}, {qtxt}"[:120], price))
    return out


PASSES = ((200, "11"), (250, "11"), (300, "11"))


def _ocr(img_bytes, scale, psm, lang):
    import subprocess
    from promo import tsv_lines
    png = subprocess.run(["convert", "-", "-resize", f"{scale}%", "-colorspace", "Gray", "png:-"], input=img_bytes, capture_output=True, timeout=300).stdout
    tsv = subprocess.run(["tesseract", "stdin", "stdout", "-l", lang, "--psm", psm, "tsv"], input=png, capture_output=True, timeout=300).stdout.decode("utf-8", "replace")
    k = 300 / scale   # koordinatės visada kaip 300 % mastelyje
    return [dict(l, x0=l["x0"] * k, y0=l["y0"] * k, x1=l["x1"] * k, y1=l["y1"] * k, h=l["h"] * k) for l in tsv_lines(tsv)]


def parse_image(img_bytes, lang="lit+eng"):
    """Keli OCR praėjimai (skirtingas mastelis / režimas) – smulkų tekstą kiekvienas perskaito kitaip; sujungiame."""
    res = {}
    for sc, psm in PASSES:
        for name, price in parse_lines(_ocr(img_bytes, sc, psm, lang)):
            key = (round(price, 2), name.split(",")[-1].replace(" ", ""))   # ta pati kaina ir kiekis = ta pati prekė
            if key not in res or _score(name) > _score(res[key]): res[key] = name
    return [(n, k[0]) for k, n in res.items()]


def _score(n):
    return len(re.findall(r"[ąčęėįšųūž]", n, re.I)) - 3 * len(re.findall(r"[|\"'<>{}\[\]~^(]", n)) + 0.02 * min(len(n), 60)
