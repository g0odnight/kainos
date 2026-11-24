import json, pathlib, subprocess, sys
sys.path.insert(0, "scraper")
from playwright.sync_api import sync_playwright
import lidl
out = pathlib.Path("probe/out"); out.mkdir(parents=True, exist_ok=True)
url = "https://assets.leaflets.schwarz/leaflets/pdfs/01a1f981-a994-74f4-a464-72681c5766e6/NE-MAISTO-PREKIU-PASIULYMAI-Nuo-lapkricio-23-d-00.pdf"
with sync_playwright() as pw:
    b = pw.chromium.launch(); ctx = b.new_context()
    r = ctx.request.get(url, timeout=120000); (out / "nm.pdf").write_bytes(r.body()); b.close()
xml = subprocess.run(["pdftotext", "-bbox-layout", "probe/out/nm.pdf", "-"], capture_output=True, text=True).stdout
(out / "nm.xml").write_text(xml)
res = lidl.parse_xml(xml)
(out / "nm_parsed.json").write_text(json.dumps(res, ensure_ascii=False, indent=0))
print("parsed", len(res))
for x in res: print(x)
