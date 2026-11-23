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

def valid_until(text, year):
    best = ""
    for m in DATE_RES[0].finditer(text[:6000]):
        best = max(best, "%04d-%02d-%02d" % tuple(map(int, m.groups())))
    if not best:
        for m in DATE_RES[1].finditer(text[:6000]):
            mo, d = int(m.group(1)), int(m.group(2))
            if 1 <= mo <= 12 and 1 <= d <= 31:
                best = max(best, "%04d-%02d-%02d" % (year, mo, d))
    return best

def parse_text(text, year):
    """Euristika: eilutė su kaina -> pavadinimas iš tos eilutės arba iš 1-2 ankstesnių eilučių."""
    until = valid_until(text, year)
    items, prev = [], []
    for raw in text.splitlines():
        line = raw.strip()
        if not line: continue
        prices = PRICE_RE.findall(line)
        words = PRICE_RE.sub("", line).strip(" -–€*:;")
        if prices:
            name = words if len(LET.findall(words)) >= 4 else " ".join(prev[-2:])
            name = re.sub(r"\s+", " ", name).strip()
            if len(name) >= 4:
                price = min(float(p.replace(",", ".")) for p in prices)
                if 0.05 < price < 300: items.append((name[:120], round(price, 2), until))
            prev = []
        elif len(LET.findall(line)) >= 3:
            prev.append(line); prev = prev[-3:]
    return list(dict.fromkeys(items))

def parse_pdf(path, year):
    text, mode = pdf_text(path)
    return parse_text(text, year), mode
