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

def valid_range(text, year):
    """-> (nuo, iki) ISO datos arba ('' , '')."""
    head = text[:8000]
    for m in RANGE_RE.finditer(head):
        y1, m1, d1, y2, m2, d2 = m.groups()
        y1 = int(y1); y2i = int(y2) if y2 else y1
        if int(m2) < int(m1) and not y2: y2i += 1
        if 1 <= int(m1) <= 12 and 1 <= int(m2) <= 12 and 1 <= int(d1) <= 31 and 1 <= int(d2) <= 31:
            return "%04d-%02d-%02d" % (y1, int(m1), int(d1)), "%04d-%02d-%02d" % (y2i, int(m2), int(d2))
    best = ""
    for m in DATE_RES[0].finditer(head):
        best = max(best, "%04d-%02d-%02d" % tuple(map(int, m.groups())))
    if not best:
        for m in DATE_RES[1].finditer(head):
            mo, d = int(m.group(1)), int(m.group(2))
            if 1 <= mo <= 12 and 1 <= d <= 31:
                best = max(best, "%04d-%02d-%02d" % (year, mo, d))
    return "", best

def valid_until(text, year):
    return valid_range(text, year)[1]

JUNK = re.compile(r"vnt\.\s*=|lidl\s*plus|nuopirmadienio|remiantis|nuolaida|prekių kiekis|galioja|www\.|\bkaina\b|pasiūlymas|^[/*\d\W]|=\s*/|€\s*/|\bišpardav", re.I)

def good_name(n):
    words = [w for w in re.findall(r"[^\W\d_]{3,}", n) if w.lower() not in ("vnt", "rink", "pak", "kaina")]
    return len(words) >= 2 and not JUNK.search(n)

def parse_text(text, year=None):
    """Eilutė su kaina -> pavadinimas iš tos eilutės arba iš 1-3 ankstesnių.
    Kaina už kg/l (pvz. '3,99 Eur/kg') išsaugoma kaip prekė '<vardas> 1 kg'. Pagrindinė kaina - mažiausia ne-vieneto kaina."""
    import datetime
    year = year or datetime.date.today().year
    frm, until = valid_range(text, year)
    text = "\n".join(x for x in text.splitlines() if not re.search(r"viewBox|xmlns|<path|<svg|\{|\}", x))
    text = re.sub(r"</?[a-zA-Z][^>]*>", " ", text)
    items, prev = [], []
    for raw in text.splitlines():
        line = raw.strip()
        if not line: continue
        if RANGE_RE.search(line) or re.search(r"galioja|pasiūlymai galioja", line, re.I): continue
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
                        items.append((f"{name[:110]} 1 {u}", pv, until, frm))
                if prices:
                    price = min(float(p.replace(",", ".")) for p in prices)
                    if 0.05 < price < 300: items.append((name[:120], round(price, 2), until, frm))
            prev = []
        elif len(LET.findall(line)) >= 3:
            prev.append(line); prev = prev[-3:]
    return list(dict.fromkeys(x for x in items if good_name(x[0])))

def parse_pdf(path, year=None):
    text, mode = pdf_text(path)
    return parse_text(text, year), mode


IP_PAT = re.compile(r"(?:(-\d{1,2})\s?%\s+|TIK\s+)?(\d{1,3},\d{2})(?:\s+(\d{1,3},\d{2}))?\s+(?=[A-ZĄČĘĖĮŠŲŪŽ])")
UNIT_PAREN = re.compile(r"\(\d[\d,.]*\s*€\s*/\s*(?:kg|l|vnt\.?)\)")
UNIT_TOK = re.compile(r"^(.*?\b\d+(?:[.,]\d+)?\s?(?:g|kg|ml|l|vnt\.?|rit\.?)(?![\wąčęėįšųūž]))")

def is_ipaper_text(text):
    return len(IP_PAT.findall(text)) >= 5 and "€ / " in text

def parse_ipaper(text, year=None):
    """iPaper SEO tekstas: '-35% 1,29 1,99 Pavadinimas, 500 g (2,58 € / kg)' -> (vardas, akcijos kaina, iki, nuo)."""
    import datetime
    year = year or datetime.date.today().year
    frm, until = valid_range(text, year)
    text = re.sub(r"</?[a-zA-Z][^>]*>", " ", text)
    text = re.sub(r"\s+", " ", text)
    ms = list(IP_PAT.finditer(text)); out = []
    for k, m in enumerate(ms):
        end = ms[k + 1].start() if k + 1 < len(ms) else len(text)
        name = UNIT_PAREN.split(text[m.end():end])[0].strip()
        u = UNIT_TOK.match(name)
        name = (u.group(1) if u else name[:90]).strip(" ,;-")
        p = float(m.group(2).replace(",", "."))
        if len(name) >= 4 and 0.05 < p < 500: out.append((name[:120], round(p, 2), until, frm))
    return list(dict.fromkeys(out))


LT_MONTHS = {"sausio":1,"vasario":2,"kovo":3,"balandžio":4,"gegužės":5,"birželio":6,"liepos":7,"rugpjūčio":8,"rugsėjo":9,"spalio":10,"lapkričio":11,"gruodžio":12}
LT_RANGE = re.compile(r"(20\d{2})\s*m\.?\s*(" + "|".join(LT_MONTHS) + r")\s+(\d{1,2})\s*[–-]\s*(?:(" + "|".join(LT_MONTHS) + r")\s+)?(\d{1,2})")

def lt_range(text):
    m = LT_RANGE.search(text)
    if not m: return "", ""
    y, m1, d1, m2, d2 = m.groups()
    a, b = LT_MONTHS[m1], LT_MONTHS[m2] if m2 else LT_MONTHS[m1]
    y = int(y); yb = y + 1 if b < a else y
    return "%04d-%02d-%02d" % (y, a, int(d1)), "%04d-%02d-%02d" % (yb, b, int(d2))

_UN = r"(?:g|kg|ml|l|vnt\.?)"
MX_REC = re.compile(r"(?P<name>[^€]{4,220}?\b\d+(?:[.,]\d+)?\s?" + _UN + r"(?![\wąčęėįšųūž])(?:\s*[,;]?\s*sveriamas,?\s*1 kg)?)\s*(?:1 (?:kg|l) [–≤≤-]+ \d+,\d{2} €\s*)?(?P<e>\d{1,3}) (?P<c>\d{2}) €(?:\s+(?P<reg>\d+,\d{2}) €)?")
MX_LEAD = re.compile(r"^(?:(?:-\d+\s?%|Iki \d+ kg|Perkant \d+ ar daugiau|\d+ vnt\.|ĮPRASTA KAINA|PIGIAUSIAS\* PASIRINKIMAS MAXIMOJE|KASDIEN PIGIAU! Sunku patikėti, lengva palyginti!|NAUJIENA!?|\*+)\s*)+")
MX_CUT = re.compile(r"^.*(?:Page number \d+|Page \d+|MAXIMA\.|MAXIMOJE|Lietuva“|Vilnius\.|\d+-\d+ / \d+|\.\.\.)\s+", re.S)

def is_maxima_text(text):
    return len(MX_REC.findall(re.sub(r"\s+", " ", text))) >= 5 and "ĮPRASTA KAINA" in text

def parse_maxima(text, year=None):
    """Maxima iPaper: 'Pavadinimas, 500 g [1 kg – 2,98 €] 1 49 € 2,19 € -31 %' -> kaina 1,49 (centai atskirti tarpu)."""
    frm, until = lt_range(text)
    if not until: frm, until = valid_range(text, year or 2026)
    t = re.sub(r"</?[a-zA-Z][^>]*>", " ", text).replace("&#215;", "×")
    t = re.sub(r"\s+", " ", t); out = []
    for m in MX_REC.finditer(t):
        n = MX_CUT.sub("", m.group("name")).strip()
        n = MX_LEAD.sub("", n).strip(" ,;")
        n = n.replace("**", "").strip()
        p = round(int(m.group("e")) + int(m.group("c")) / 100, 2)
        if len(n) >= 4 and 0.05 < p < 500: out.append((n[:120], p, until, frm))
    return list(dict.fromkeys(out))
