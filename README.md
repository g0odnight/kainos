# Kainų palyginimas (be serverio)

Kasdien ~08:00 (Vilniaus laiku) GitHub Actions surenka e-parduotuvių katalogus ir kainų leidinius (PDF) į `prices.json`.
Programėlė (`index.html`, PWA) atsisiunčia tą failą ir **ieško pati telefone** – iškart, be serverio.
Kešas galioja iki kito surinkimo (programėlė kaskart patikrina ar `prices.json` pasikeitė).

## Paleidimas
1. Sukurk viešą GitHub repo, aplanke: `git init -b main && git add . && git commit -m init && git remote add origin https://github.com/TAVO_VARDAS/kainos.git && git push -u origin main`
2. Settings → Pages → Deploy from a branch → `main` / `(root)`.
3. Settings → Actions → General → Workflow permissions → **Read and write**.
4. Actions → `scrape` → **Run workflow** (pirmas paleidimas gali užtrukti 20–60 min).
5. Telefone: `https://TAVO_VARDAS.github.io/kainos/` → Chrome meniu → „Įdiegti programėlę“.
6. Programėlėje viršuje dešinėje paspaudus datą matysi kiek prekių surinkta iš kiekvienos parduotuvės.

## Derinimas (NEPATIKRINTA – tikėtina, kad teks taisyti)
Visi URL ir selektoriai `scraper/stores.json` yra spėjimai. Lokaliai:
`pip install -r scraper/requirements.txt && playwright install chromium` (+ `poppler-utils`, `tesseract-ocr`, `tesseract-ocr-lit` leidiniams)
- `python scraper/scrape.py --probe "URL" --store Rimi` – parodo kiek prekių ir kokių PDF rado puslapyje; HTML išsaugo `scraper/debug/probe.html`.
- `python scraper/scrape.py --pdf leidinys.pdf` – parodo kaip išparsinamas leidinys.
- `python scraper/scrape.py --store Rimi` – viena parduotuvė (kitų duomenys paliekami).
- Jei parduotuvė grąžina <30 % ankstesnio kiekio, paliekami seni duomenys ir programėlėje rodomas įspėjimas.
- Workflow įkelia `debug` artefaktą: jei neišeina, atsiųsk man `*.json` ir dalį `*.html`.

## Pastabos
- E-parduotuvių kainos gali skirtis nuo kainų parduotuvėje.
- Leidiniai: jei PDF turi tekstą – skaitoma tiesiogiai, jei paveikslėliai – OCR (mažiau tikslu). Kai kurie leidiniai būna ne PDF, o interaktyvūs katalogai; tada reikia rasti jų duomenų URL.
- GitHub cron gali vėluoti; jei diena praleista, paleisk rankiniu būdu. Viešuose repo suplanuoti workflow išsijungia po 60 d. be aktyvumo.
- Prieš naudodamas pasitikrink parduotuvių naudojimo sąlygas; skriptas daro ~1 užklausą per sekundę.
