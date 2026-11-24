"""IKI leidinio puslapių paveikslėliai (manoakcijos.lt) -> prekės.
IKI maketas: „ARVI kalakutienos faršas, 400 g, 5,48 Eur/kg“ smulkiu šriftu ir stilizuota kaina („2 19“).
Smulkus tekstas OCR skaitomas gerai, todėl kainą apskaičiuojame: kiekis × kaina už kg/l, o jei šalia
perskaityta didelė kaina sutampa (±2 ct), naudojame ją. Prekės be kainos už kg/l (pvz. „-40 % kruopoms“, „1+1“) praleidžiamos."""
import re
from promo import ocr_lines

UNIT = re.compile(r"(\d{1,3})\s*[,.]\s*(\d{2})\s*Eur\s*/\s*(kg|k[oąg]|l|I|\||vnt)", re.I)
QTY = re.compile(r"(?:(\d+)\s*[x×]\s*)?(\d+(?:[.,]\d+)?)\s*(kg|g|ml|l)\b(?!\s*=)", re.I)


def _near(l, u):
    """Tame pačiame stulpelyje: lygiuota kairėje arba dešinėje (IKI tekstai dažnai lygiuoti dešinėje)."""
    return abs(l["x0"] - u["x0"]) < 45 or abs(l["x1"] - u["x1"]) < 45


def parse_lines(lines):
    out = []
    for u in lines:
        um = UNIT.search(u["t"])
        if not um: continue
        per = um.group(3).lower()
        per = "vnt" if per == "vnt" else ("kg" if per.startswith("k") else "l")
        block, top = [u], u
        for _ in range(5):   # eilutės virš (pavadinimas, kiekis) tame pačiame stulpelyje
            up = [l for l in lines if l is not top and _near(l, u) and 0 <= top["y0"] - l["y1"] < max(30, top["h"] * 0.9) and l["h"] < 90]
            if not up: break
            top = max(up, key=lambda l: l["y1"]); block.insert(0, top)
        text = re.sub(r"\s+", " ", " ".join(l["t"] for l in block)).strip()
        before = text[:text.find(um.group(0))] if um.group(0) in text else text
        unit = int(um.group(1)) + int(um.group(2)) / 100
        qms = list(QTY.finditer(before))
        qm = qms[-1] if qms else None
        tol = 0.011
        if per == "vnt":
            nm = re.search(r"(\d+)\s*vnt", before)
            n = int(nm.group(1)) if nm else 1
            # „12 vnt., 0,12 Eur/vnt.“ – tai vieno vieneto kaina; pakuotės kaina = 12 × 0,12 (± apvalinimas),
            # todėl tokią prekę imame tik jei šalia perskaityta stambi kaina tai patvirtina
            cand = n * unit; tol = 0.011 if n == 1 else 0.006 * n + 0.01
            qtxt = (qm.group(0) if qm else "") or (nm.group(0) if nm else "")
        else:
            if not qm:   # „Supakuota“ ženkliukas su kiekiu šalia
                for l in lines:
                    if "upakuot" in l["t"] and abs(l["y0"] - u["y0"]) < 900 and abs(l["x0"] - u["x0"]) < 1100:
                        nxt = [m for m in lines if 0 <= m["y0"] - l["y0"] < 90 and abs(m["x0"] - l["x0"]) < 120]
                        mm = QTY.search(" ".join(m["t"] for m in [l] + nxt))
                        if mm: qm = mm; break
            if not qm: continue
            q = float(qm.group(2).replace(",", ".")) * (int(qm.group(1)) if qm.group(1) else 1)
            kg = q / 1000 if qm.group(3).lower() in ("g", "ml") else q
            cand = kg * unit; qtxt = qm.group(0)
        if not (0.1 < cand < 200): continue
        price = round(cand + 1e-6, 2)   # apvalinimas „half-up“ (0,5 × 2,97 = 1,485 -> 1,49)
        snapped = False
        for b in lines:   # stambi kaina šalia – jei skaitmenys sutampa, imame ją
            if b["h"] < 120 or not (-1200 < b["x0"] - u["x0"] < 1400 and -900 < b["y0"] - u["y0"] < 600): continue
            d = re.sub(r"\D", "", b["t"])
            for k in (3, 4):
                if len(d) >= k and abs(int(d[:k]) / 100 - cand) <= tol: price = int(d[:k]) / 100; snapped = True
        if tol > 0.011 and not snapped: continue
        name = before[:qms[-1].start()] if qms else before
        if per == "vnt" and not qms and nm: name = before[:nm.start()]
        name = re.sub(r"\b\d+\s*rūšių\b|įvairių rūšių|TIK\b", "", name, flags=re.I).strip(" ,;*")
        name = re.sub(r"^[^A-Za-zĄČĘĖĮŠŲŪŽąčęėįšųūž]+", "", name)
        if len(re.findall(r"[^\W\d_]", name)) < 5: continue
        out.append((f"{name}, {qtxt}".strip(" ,")[:120], price))
    return list(dict.fromkeys(out))


def parse_image(img_bytes):
    return parse_lines(ocr_lines(img_bytes))
