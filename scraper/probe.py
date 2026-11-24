"""IKI didžiojo leidinio puslapiai iš manoakcijos.lt: paveikslėliai + OCR TSV analizei."""
import pathlib, subprocess
from playwright.sync_api import sync_playwright
OUT = pathlib.Path(__file__).parent / "probe"; OUT.mkdir(exist_ok=True)
with sync_playwright() as pw:
    br = pw.chromium.launch(); ctx = br.new_context()
    for k in (2, 3, 5, 8, 12, 20):
        r = ctx.request.get(f"https://app.manoakcijos.lt/261129_261123_iki_jawkw/image{k:02d}.webp", timeout=60000)
        if r.status != 200: continue
        fn = OUT / f"p{k}.webp"; fn.write_bytes(r.body())
        png = subprocess.run(["convert", str(fn), "-resize", "250%", "-colorspace", "Gray", "-sharpen", "0x1", "png:-"], capture_output=True).stdout
        tsv = subprocess.run(["tesseract", "stdin", "stdout", "-l", "lit+eng", "--psm", "11", "tsv"], input=png, capture_output=True).stdout
        (OUT / f"p{k}.tsv").write_bytes(tsv)
    br.close()
