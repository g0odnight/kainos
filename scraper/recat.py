"""Perskaičiuoja prices.json kategorijas pagal dabartines categories.py taisykles (be naujo rinkimo).
Keičiama tik tada, kai taisyklės prekę atpažįsta (ne „kita“) – Rimi skyrių užuominos lieka."""
import json, pathlib, re, categories
p = pathlib.Path(__file__).resolve().parent.parent / "prices.json"
d = json.loads(p.read_text(encoding="utf-8"))
ids = [c["id"] for c in d["cats"]]; n = 0
for it in d["items"]:
    nm = re.sub(r"\s{2,}", " ", re.sub(r"\s*\|\s*", ", ", it[1].replace("\u00a0", " ")))
    nm = re.sub(r"[,\s]*(?<![A-Za-zĄČĘĖĮŠŲŪŽąčęėįšųūž])(AW|SS|CH|HW|FW)\d{2}\b", "", nm).strip(" ,")
    if nm != it[1]: it[1] = nm; n += 1
    c = categories.classify(it[1])
    if c != "kita" and c in ids and ids[it[7]] != c: it[7] = ids.index(c); n += 1
# Lidl leidinio skyrių antraštės („MUZIKOS INSTRUMENTAI“) – ne prekės
L = d["stores"].index("Lidl") if "Lidl" in d["stores"] else -1
d["items"] = [it for it in d["items"] if not (it[0] == L and it[1].isupper() and len(it[1].split()) <= 4 and not re.search(r"\d", it[1]))]
p.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print("pakeista (kategorijos ir pavadinimai):", n)
