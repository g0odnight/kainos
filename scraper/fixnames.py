"""Pavadinimų sutvarkymas po rinkimo.
OCR (IKI, Promo) dažnai pameta lietuviškas raides: „Saltai rūkyta sonine“, „pomidory“, „jdaru“.
Atstatome jas pagal žodyną, sudarytą iš kitų parduotuvių (tekstinių) pavadinimų.
Taip pat išmetame pavadinimų nuotrupas („idaru, 85 g“, „Su karamelės įdaru“)."""
import re
from collections import Counter, defaultdict
from categories import norm

LT = re.compile(r"[ąčęėįšųūž]", re.I)
WORD = re.compile(r"[^\W\d_]+")
FRAGMENT = re.compile(r"^([a-ząčęėįšųūž]|(Su|Arba|Ir|Perkant|Ar)\b)")


def build_vocab(names):
    v = defaultdict(Counter)
    plain = Counter()
    for n in names:
        for w in WORD.findall(n):
            if len(w) < 3: continue
            lw = w.lower()
            if LT.search(lw): v[norm(lw)][lw] += 1
            else: plain[lw] += 1
    # žodis be diakritikų, kuris pats dažnai sutinkamas (pvz., „sultys“ vs „sūltys“), neliečiamas
    return {k: c.most_common(1)[0][0] for k, c in v.items() if sum(c.values()) >= 2 and sum(c.values()) > 3 * plain.get(k, 0)}


def _case(src, dst):
    if src.isupper(): return dst.upper()
    if src[0].isupper(): return dst[0].upper() + dst[1:]
    return dst


def restore(name, vocab):
    def fix(m):
        w = m.group(0); lw = w.lower()
        if len(w) < 3 or LT.search(lw): return w
        for cand in (lw, lw[:-1] + "u" if lw.endswith("y") else None, "i" + lw[1:] if lw.startswith("j") else None,
                     re.sub(r"y\b", "u", "i" + lw[1:]) if lw.startswith("j") else None):
            if cand and norm(cand) in vocab: return _case(w, vocab[norm(cand)])
        return w
    return WORD.sub(fix, name)


def is_fragment(name):
    return bool(FRAGMENT.match(name.strip()))
