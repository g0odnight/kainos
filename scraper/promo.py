"""Promo Cash&Carry leidinio puslapių paveikslėliai -> prekės (OCR + padėtis puslapyje).
Promo maketas – langelių tinklelis: viršuje pavadinimas (ir „• 0,5 l • 2,38 Eur/l“), apačioje „€ 1,19/vnt.“.
Pavadinimą su kaina jungiame pagal stulpelį; kai yra kiekis ir kaina už l/kg – patikriname."""
import csv, io, re, subprocess

PRICE = re.compile(r"€\s*(\d{1,3})\s*[,.]\s*(\d{2})\s*/?\s*(vnt|pak|kg|l|rink|kompl)?", re.I)
UNIT = re.compile(r"(\d{1,3})[,.](\d{2})\s*Eur\s*/?\s*(kg|l)", re.I)
QTY = re.compile(r"(?:(\d+)\s*x\s*)?(\d+(?:[.,]\d+)?)\s*(kg|g|ml|l)\b", re.I)
SKIP = re.compile(r"Taros|Vartodami|Visos kainos|leidinyje|Prekių kiekis|užstato|gerimo|gėrimo|šeimos", re.I)


def _run(cmd, inp=None, timeout=300):
    return subprocess.run(cmd, input=inp, capture_output=True, timeout=timeout).stdout


def ocr_lines(img_bytes, scale=250):
    png = _run(["convert", "-", "-resize", f"{scale}%", "-colorspace", "Gray", "-sharpen", "0x1", "png:-"], img_bytes)
    tsv = _run(["tesseract", "stdin", "stdout", "-l", "lit+eng", "--psm", "11", "tsv"], png).decode("utf-8", "replace")
    return tsv_lines(tsv)


def tsv_lines(tsv):
    rows = [r for r in csv.DictReader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE)
            if (r.get("text") or "").strip() and float(r.get("conf") or -1) >= 0]
    L = {}
    for r in rows:
        k = (r["block_num"], r["par_num"], r["line_num"])
        L.setdefault(k, []).append(r)
    out = []
    for ws in L.values():
        x0 = min(int(w["left"]) for w in ws); y0 = min(int(w["top"]) for w in ws)
        x1 = max(int(w["left"]) + int(w["width"]) for w in ws); y1 = max(int(w["top"]) + int(w["height"]) for w in ws)
        conf = sum(float(w["conf"]) for w in ws) / len(ws)
        out.append({"x0": x0, "y0": y0, "x1": x1, "y1": y1, "h": y1 - y0, "conf": conf, "t": " ".join(w["text"] for w in ws)})
    # sujungiam žodžius toje pačioje eilutėje (psm 11 skaido smulkiai)
    out.sort(key=lambda l: (l["y0"], l["x0"]))
    merged = []
    for l in out:
        m = next((p for p in reversed(merged[-6:]) if abs(p["y0"] - l["y0"]) < max(8, p["h"] * 0.4) and 0 <= l["x0"] - p["x1"] < max(25, p["h"] * 0.9)), None)
        if m:
            m["t"] += " " + l["t"]; m["x1"] = max(m["x1"], l["x1"]); m["y1"] = max(m["y1"], l["y1"]); m["conf"] = min(m["conf"], l["conf"])
        else:
            merged.append(dict(l))
    return merged


def _qty_cands(spec):
    """Kiekio kandidatai iš triukšmingo OCR („0,451“ = 0,45 l, „4x0,5681“ = 4×0,568 l, „500 g“)."""
    t = spec.replace("•", " ").replace("+", " ").replace("©", " ")
    out = []
    for m in re.finditer(r"(?:(\d{1,2})\s*[xX×]\s*)?(\d+(?:,\d{1,4})?)\s*(kg|g|ml|l|1|I)?\b", t):
        mult = int(m.group(1)) if m.group(1) else 1
        num, u = m.group(2), (m.group(3) or "")
        if "%" in t[m.end():m.end() + 2]: continue
        vals = [num]
        if u in ("", "1", "I") and "," in num and num.endswith("1"): vals.append(num[:-1])   # „0,451“ -> „0,45“ + l
        for v in vals:
            try: q = float(v.replace(",", "."))
            except ValueError: continue
            if u.lower() in ("g", "ml"): q /= 1000
            if 0.02 <= q * mult <= 30: out.append(q * mult)
    return out


def _unit(spec):
    m = re.search(r"(\d{1,3})[,.]?(\d{2})\s*Eur", spec)
    return int(m.group(1)) + int(m.group(2)) / 100 if m else None


def _price_cands(t):
    """„€ 1,1 O/vnt.“ -> 1.10/1.19…; „€1 29“ -> 1.29; „€ 27,99“ -> 27.99."""
    t = t.replace("O", "0").replace("o", "0")
    m = PRICE.search(t)
    c = []
    if m: c.append(int(m.group(1)) + int(m.group(2)) / 100)
    d = re.sub(r"\D", "", t.split("/")[0])
    for n in (3, 4):
        if len(d) >= n: c.append(int(d[:n]) / 100)
    if len(d) == 2: c += [int(d[0]) + int(d[1]) / 10 + k / 100 for k in range(10)]   # „1,1O“ – trūksta skaitmens
    return c


def parse_lines(lines, page_w):
    names = [l for l in lines if re.match(r"^[A-ZĄČĘĖĮŠŲŪŽ][a-ząčęėįšųūž]+\s+\S", l["t"]) and l["conf"] >= 80 and 15 < l["h"] < 45
             and len(re.findall(r"[A-Za-zĄČĘĖĮŠŲŪŽąčęėįšųūž]{3,}", l["t"])) >= 2 and not SKIP.search(l["t"]) and "€" not in l["t"]]
    pls = [l for l in lines if "€" in l["t"] and l["h"] > 45]
    cont = {id(n) for n in names for m in names if m is not n and abs(m["x0"] - n["x0"]) < 15 and 0 < n["y0"] - m["y0"] < 45}
    names = [n for n in names if id(n) not in cont]
    out = []
    for n in names:
        same = sorted([m for m in names if abs(m["x0"] - n["x0"]) < 60 and m["y0"] > n["y0"] + 60], key=lambda m: m["y0"])
        y_end = same[0]["y0"] if same else 10 ** 6
        spec = " ".join(l["t"] for l in lines if abs(l["x0"] - n["x0"]) < 80 and n["y1"] - 5 <= l["y0"] < n["y1"] + 110)
        cw = min([abs(m["x0"] - n["x0"]) for m in names if abs(m["x0"] - n["x0"]) > 200] or [page_w / 5])
        prices = [p for p in pls if n["y0"] < p["y0"] < y_end and n["x0"] - 30 < p["x0"] < n["x0"] + cw * 0.8]
        if not prices: continue
        p = max(prices, key=lambda q: q["h"])
        unit, qs = _unit(spec), _qty_cands(spec)
        best = None
        if unit:
            for c in _price_cands(p["t"]):
                for q in qs:
                    if abs(q * unit - c) <= max(0.02, c * 0.02): best = c; break
                if best: break
        if best is None:
            m = PRICE.search(p["t"])
            if m and p["conf"] >= 85 and not unit: best = int(m.group(1)) + int(m.group(2)) / 100   # be vieneto kainos – tik labai aiški kaina
        if best is None: continue
        name = re.sub(r"\s+", " ", n["t"]).strip(" •+-/")
        nxt = [l for l in lines if abs(l["x0"] - n["x0"]) < 15 and 0 < l["y0"] - n["y1"] < 12 and l["conf"] >= 80 and not re.search(r"Eur|%|•|\+", l["t"])]
        if nxt: name += " " + nxt[0]["t"]
        qm = QTY.search(re.sub(r"(\d,\d+)1\b", r"\1 l", spec.replace("•", " ")))
        if qm and qm.group(0) not in name: name += ", " + qm.group(0)
        out.append((name[:120], round(best, 2), True))
    return out


def parse_image(img_bytes):
    lines = ocr_lines(img_bytes)
    w = max((l["x1"] for l in lines), default=3000)
    return parse_lines(lines, w)
