"""Norfa leidinio PDF -> prekės.
Norfos leidinyje prie kiekvienos prekės parašyta „<pavadinimas>, 500 g, 2,30 Eur/kg“, o didelė kaina („1 15“)
stovi atskirai. Kainą apskaičiuojame iš svorio × vieneto kainos ir priimame tik tada, kai tokia kaina tikrai
yra tame puslapyje – taip išvengiame klaidingų porų."""
import re, subprocess
from lidl import _blocks

UNIT = re.compile(r"(\d{1,4}),(\d{2})\s*(?:Eur|€)\s*/\s*(kg|l)\b", re.I)
W = re.compile(r"(?:(\d+)\s*x\s*)?(\d+(?:[.,]\d+)?)\s*(kg|g|ml|l)\b", re.I)
BIG = re.compile(r"^\s*(\d{1,3})\s?(\d{2})\s*$")


def _merge(desc):
    desc = sorted(desc, key=lambda b: (round(b["x0"] / 4), b["y0"]))
    out = []
    for b in desc:
        p = out[-1] if out else None
        if p and abs(p["x0"] - b["x0"]) < 6 and 0 <= b["y0"] - p["y1"] < 8 and not UNIT.search(p["t"]):
            p["t"] += " " + b["t"]; p["y1"] = b["y1"]
        else:
            out.append(dict(b))
    return out


CPRICE = re.compile(r"^\s*(\d{1,3}),(\d{2})\s*€")


def parse_catalog_page(bl):
    """Kalėdinio katalogo maketas: „Pavadinimas, 75 g, 29,20 Eur/kg“ ir šalia „2,19 €“."""
    prices = [b for b in bl if b["h"] >= 18 and CPRICE.match(b["t"])]
    names = [b for b in bl if 12 <= b["h"] < 18 and len(re.findall(r"[^\W\d_]", b["t"])) >= 6]
    cands = []
    for ni, n in enumerate(names):
        t = re.sub(r"\s+", " ", n["t"].replace("\u00ad", "")).strip()
        um = UNIT.search(t); unit = float(um.group(1) + "." + um.group(2)) if um else None
        ws = list(W.finditer(t[:um.start()] if um else t))
        kg = None
        if ws:
            w = ws[-1]; q = float(w.group(2).replace(",", ".")) * (int(w.group(1)) if w.group(1) else 1)
            kg = q / 1000 if w.group(3).lower() in ("g", "ml") else q
        for pi, p in enumerate(prices):
            dx, dy = p["x0"] - n["x0"], p["y0"] - n["y0"]
            if not (-15 < dx < 260 and -15 < dy < 45): continue
            m = CPRICE.match(p["t"]); price = int(m.group(1)) + int(m.group(2)) / 100
            ok = unit and kg and abs(kg * unit - price) <= max(0.03, price * 0.015)
            cands.append(((0 if ok else 1000) + abs(dx) + abs(dy) * 2, ni, pi, price, t, um))
    cands.sort(); used_n, used_p, out = set(), set(), []
    for _, ni, pi, price, t, um in cands:
        if ni in used_n or pi in used_p: continue
        used_n.add(ni); used_p.add(pi)
        name = t[:um.start()] if um else t
        name = re.sub(r",?\s*art\.\s*[\w().\-/]+", "", name).strip(" ,")
        if len(re.findall(r"[^\W\d_]", name)) >= 4: out.append((name[:120], round(price, 2)))
    return out


def parse_page(bl):
    if not any(BIG.match(b["t"]) and b["h"] >= 20 for b in bl):
        return parse_catalog_page(bl)
    prices = []
    for b in bl:
        m = BIG.match(b["t"])
        if m and b["h"] >= 20: prices.append(int(m.group(1)) + int(m.group(2)) / 100)
    if not prices: return []
    desc = [b for b in bl if b["h"] < 13 and re.search(r"[^\W\d_]{3}", b["t"]) or UNIT.search(b["t"])]
    out = []
    for b in _merge(desc):
        t = re.sub(r"\s+", " ", b["t"].replace("\u00ad ", "").replace("\u00ad", "")).strip()
        t = re.sub(r"(?<=[a-ząčęėįšųūž])-\s(?=[a-ząčęėįšųūž])", "", t)
        um = UNIT.search(t)
        if not um: continue
        unit = float(um.group(1) + "." + um.group(2))
        ws = list(W.finditer(t[:um.start()]))
        if not ws: continue
        w = ws[-1] if not re.search(r"/pak", t) else next((x for x in ws if x.group(1)), ws[-1])
        q = float(w.group(2).replace(",", ".")) * (int(w.group(1)) if w.group(1) else 1)
        kg = q / 1000 if w.group(3).lower() in ("g", "ml") else q
        cand = kg * unit
        best = min(prices, key=lambda p: abs(p - cand))
        if abs(best - cand) <= max(0.03, best * 0.012):
            name = t[:ws[0].start()].strip(" ,")
            name = f"{name}, {w.group(0)}" if name else ""
            core = re.sub(r"\(?\d+\s*rūšių\)?|,\s*" + re.escape(w.group(0)) + "$", "", name)
            if len(re.findall(r"[^\W\d_]", core)) >= 4:
                out.append((name[:120], round(best, 2)))
    return out


def parse(path, until="", frm=""):
    xml = subprocess.run(["pdftotext", "-bbox-layout", str(path), "-"], capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=900).stdout
    res = []
    for bl in _blocks(xml):
        for n, p in parse_page(bl):
            res.append((n, p, until, frm, None))
    return list(dict.fromkeys(res))
