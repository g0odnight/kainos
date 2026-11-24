import json, pathlib, re
from playwright.sync_api import sync_playwright
out = pathlib.Path("probe/out"); out.mkdir(parents=True, exist_ok=True)
caps = []
with sync_playwright() as pw:
    b = pw.chromium.launch(); ctx = b.new_context(locale="lt-LT", user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"); p = ctx.new_page()
    def on_resp(r):
        try:
            ct = r.headers.get("content-type", "")
            if "json" in ct or ("akcijuseklys" in r.url and "image" not in ct and not r.url.split("?")[0].endswith((".js", ".css", ".webp", ".png", ".woff2", ".svg"))):
                caps.append({"url": r.url, "status": r.status, "ct": ct, "body": r.text()[:200000]})
        except Exception as e: caps.append({"url": r.url, "err": str(e)})
    p.on("response", on_resp)
    for n in (1, 2, 10):
        p.goto(f"https://www.akcijuseklys.lt/parduotuve/silas/br_76a6a6cb?page={n}", wait_until="domcontentloaded", timeout=90000)
        try: p.wait_for_load_state("networkidle", timeout=20000)
        except Exception: pass
        p.wait_for_timeout(3000)
        (out / f"page{n}.html").write_text(p.content())
        (out / f"page{n}.txt").write_text(p.inner_text("body"))
        p.screenshot(path=str(out / f"page{n}.png"), full_page=True)
    b.close()
(out / "net.json").write_text(json.dumps(caps, ensure_ascii=False, indent=1))
print(len(caps), [c["url"][:120] for c in caps][:80])
