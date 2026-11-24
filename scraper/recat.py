"""Perskaičiuoja prices.json kategorijas pagal dabartines categories.py taisykles (be naujo rinkimo).
Keičiama tik tada, kai taisyklės prekę atpažįsta (ne „kita“) – Rimi skyrių užuominos lieka."""
import json, pathlib, categories
p = pathlib.Path(__file__).resolve().parent.parent / "prices.json"
d = json.loads(p.read_text(encoding="utf-8"))
ids = [c["id"] for c in d["cats"]]; n = 0
for it in d["items"]:
    c = categories.classify(it[1])
    if c != "kita" and c in ids and ids[it[7]] != c: it[7] = ids.index(c); n += 1
p.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print("pakeista kategorijų:", n)
