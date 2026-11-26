import os, urllib.request
os.makedirs("probe/out", exist_ok=True)
req = urllib.request.Request("https://www.silas.lt/wp-content/uploads/2026/11/SILAS_Nr23_2026.pdf", headers={"User-Agent": "Mozilla/5.0"})
open("probe/out/silas23.pdf", "wb").write(urllib.request.urlopen(req, timeout=120).read())
