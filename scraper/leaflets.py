"""Kainų leidinių PDF -> prekės. Pirma bandoma teksto ištraukimas (pdftotext), jei PDF yra paveikslėlių – OCR (tesseract)."""
import glob, pathlib, re, subprocess, tempfile
from common import PRICE_RE

LET = re.compile(r"[^\W\d_]")
DATE_RES = [re.compile(r"(20\d{2})[-./](\d{1,2})[-./](\d{1,2})"), re.compile(r"iki\s+(\d{1,2})[-./](\d{1,2})", re.I)]

def _run(cmd, timeout=300):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout

def pdf_text(path, max_pages=60):
    txt = _run(["pdftotext", "-raw", "-l", str(max_pages), str(path), "-"], 120)
    if len(LET.findall(txt)) >= 400:
        return txt, "text"
    out = []
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["pdftoppm", "-r", "170", "-l", str(max_pages), "-png", str(path), d + "/p"], timeout=600)
        for img in sorted(glob.glob(d + "/p*.png")):
            t = _run(["tesseract", img, "stdout", "-l", "lit+eng", "--psm", "6"], 120)
            out.append(t)
    return "\n".join(out), "ocr"

RANGE_RE = re.compile(r"(20\d{2})\s*[-./ ]\s*(\d{1,2})\s*[-./ ]\s*(\d{1,2})\s*(?:d\.?)?\s*[–—-]\s*(?:(20\d{2})\s*[-./ ]\s*)?(\d{1,2})\s*[-./ ]\s*(\d{1,2})")
UNIT_RE = re.compile(r"(\d{1,3}[.,]\d{2})\s*(?:Eur|EUR|eur|€)\s*/\s*(kg|l|vnt)", re.I)

def valid_until(text, year):
    head = text[:8000]
    best = ""
    for m in RANGE_RE.finditer(head):
        y1, m1, d1, y2, m2, d2 = m.groups()
        y2 = int(y2) if y2 else int(y1)
        if int(m2) < int(m1) and not m.group(4): y2 += 1
        if 1 <= int(m2) <= 12 and 1 <= int(d2) <= 31:
            best = max(best, "%04d-%02d-%02d" % (y2, int(m2), int(d2)))
    if best: return best
    for m in DATE_RES[0].finditer(head):
        best = max(best, "%04d-%02d-%02d" % tuple(map(int, m.groups())))
    if not best:
        for m in DATE_RES[1].finditer(head):
            mo, d = int(m.group(1)), int(m.group(2))
            if 1 <= mo <= 12 and 1 <= d <= 31:
                best = max(best, "%04d-%02d-%02d" % (year, mo, d))
    return best

def parse_text(text, year=None):
    """Eilutė su kaina -> pavadinimas iš tos eilutės arba iš 1-3 ankstesnių.
    Kaina už kg/l (pvz. '3,99 Eur/kg') išsaugoma kaip prekė '<vardas> 1 kg'. Pagrindinė kaina - mažiausia ne-vieneto kaina."""
    import datetime
    year = year or datetime.date.today().year
    until = valid_until(text, year)
    text = "\n".join(x for x in text.splitlines() if not re.search(r"viewBox|xmlns|<path|<svg|\{|\}", x))
    text = re.sub(r"</?[a-zA-Z][^>]*>", " ", text)
    items, prev = [], []
    for raw in text.splitlines():
        line = raw.strip()
        if not line: continue
        units = UNIT_RE.findall(line)
        plain = UNIT_RE.sub(" ", line)
        prices = PRICE_RE.findall(plain)
        words = PRICE_RE.sub("", plain).strip(" -–€*:;")
        if prices or units:
            name = words if len(LET.findall(words)) >= 4 else " ".join(prev[-3:])
            if prev and len(LET.findall(words)) >= 4 and len(words) < 14: name = " ".join(prev[-3:] + [words])
            name = re.sub(r"\s+", " ", name).strip()
            if len(name) >= 4:
                for p, u in units:
                    u = u.lower(); pv = round(float(p.replace(",", ".")), 2)
                    if u in ("kg", "l") and 0.05 < pv < 300 and not re.search(r"\b1\s*(kg|l)\b", name, re.I):
                        items.append((f"{name[:110]} 1 {u}", pv, until))
                if prices:
                    price = min(float(p.replace(",", ".")) for p in prices)
                    if 0.05 < price < 300: items.append((name[:120], round(price, 2), until))
            prev = []
        elif len(LET.findall(line)) >= 3:
            prev.append(line); prev = prev[-3:]
    return list(dict.fromkeys(items))

def parse_pdf(path, year=None):
    text, mode = pdf_text(path)
    return parse_text(text, year), mode
