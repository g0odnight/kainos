import json, pathlib, subprocess, sys
sys.path.insert(0, "scraper")
from playwright.sync_api import sync_playwright
import lidl
out = pathlib.Path("probe/out"); out.mkdir(parents=True, exist_ok=True)
url = "https://assets.leaflets.schwarz/leaflets/pdfs/01a1f981-a994-74f4-a464-72681c5766e6/NE-MAISTO-PREKIU-PASIULYMAI-Nuo-lapkricio-23-d-00.pdf"
with sync_playwright() as pw:
    b = pw.chromium.launch(); ctx = b.new_context()
    r = ctx.request.get(url, timeout=120000); (out / "nm.pdf").write_bytes(r.body()); b.close()
print("ok", (out / "nm.pdf").stat().st_size)
