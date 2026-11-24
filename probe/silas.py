import json, pathlib, re
from playwright.sync_api import sync_playwright
out = pathlib.Path("probe/out"); out.mkdir(parents=True, exist_ok=True)
res = []
with sync_playwright() as pw:
    b = pw.chromium.launch(); ctx = b.new_context(locale="lt-LT")
    for ln in ("/parduotuve/vynoteka/br_c5383401", "/parduotuve/vynoteka/br_15aec898"):
        h = ctx.request.get("https://www.akcijuseklys.lt" + ln, timeout=60000).text()
        m = next((m for m in re.finditer(r"<script[^>]*>(\{\"pages\".*?)</script>", h, re.S)), None)
        for x in json.loads(m.group(1))["deals"]:
            if re.search(r"inkin", x.get("title") or "", re.I): res.append({k: x.get(k) for k in ("title", "details", "promoPrice", "regularPrice", "promoLabel", "pageNumber")})
    b.close()
(out / "vyn.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
for r in res: print(json.dumps(r, ensure_ascii=False))
