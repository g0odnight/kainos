"""IKI leidinio puslapių paveikslėliai (manoakcijos.lt) -> prekės.
IKI maketas: „ARVI kalakutienos faršas, 400 g, 5,48 Eur/kg“ smulkiu šriftu ir stilizuota kaina („2 19“).
Smulkus tekstas OCR skaitomas gerai, todėl kainą apskaičiuojame: kiekis × kaina už kg/l, o jei šalia
perskaityta didelė kaina sutampa (±2 ct), naudojame ją. Prekės be kainos už kg/l (pvz. „-40 % kruopoms“, „1+1“) praleidžiamos."""
import re
from promo import ocr_lines

UNIT = re.compile(r"(\d{1,3})\s*[,.]\s*(\d{2})\s*Eur\s*/\s*(kg|l)\b", re.I)
QTY = re.compile(r"(?:(\d+)\s*[x×]\s*)?(\d+(?:[.,]\d+)?)\s*(kg|g|ml|l)\b(?!\s*=)", re.I)


def parse_lines(lines):
    out = []
    for u in lines:
        um = UNIT.search(u["t"])
        if not um: continue
        block, top = [u], u
        for _ in range(4):   # eilutės virš (pavadinimas, kiekis) tame pačiame stulpelyje
            up = [l for l in lines if l is not top and abs(l["x0"] - u["x0"]) < 45 and 0 <= top["y0"] - l["y1"] < max(30, top["h"] * 0.9) and l["h"] < 90]
            if not up: break
            top = max(up, key=lambda l: l["y1"]); block.insert(0, top)
        text = re.sub(r"\s+", " ", " ".join(l["t"] for l in block)).strip()
        before = text[:text.find(um.group(0))] if um.group(0) in text else text
        qms = [m for m in QTY.finditer(before)]
        if not qms: continue
        qm = qms[-1]
        q = float(qm.group(2).replace(",", ".")) * (int(qm.group(1)) if qm.group(1) else 1)
        kg = q / 1000 if qm.group(3).lower() in ("g", "ml") else q
        unit = int(um.group(1)) + int(um.group(2)) / 100
        cand = kg * unit
        if not (0.1 < cand < 200): continue
        price = round(cand, 2)
        # stambi kaina šalia (dešiniau/aukščiau) – jei skaitmenys sutampa ±2 ct, imame ją
        for b in lines:
            if b["h"] < 120 or not (-200 < b["x0"] - u["x0"] < 1400 and -500 < b["y0"] - u["y0"] < 200): continue
            d = re.sub(r"\D", "", b["t"])
            for n in (3, 4):
                if len(d) >= n and abs(int(d[:n]) / 100 - cand) <= 0.011: price = int(d[:n]) / 100
        name = before[:qm.start()].strip(" ,;")
        name = re.sub(r"^[^A-Za-zĄČĘĖĮŠŲŪŽąčęėįšųūž]+", "", name)
        if len(re.findall(r"[^\W\d_]", name)) < 5: continue
        out.append((f"{name}, {qm.group(0)}"[:120], price))
    return list(dict.fromkeys(out))


def parse_image(img_bytes):
    return parse_lines(ocr_lines(img_bytes))
