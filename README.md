# Kainos

Programėlė: https://g0odnight.github.io/kainos/

Parduotuvių **akcijos ir leidinių pasiūlymai** vienoje vietoje: paieška, parduotuvių ir kategorijų filtrai, rūšiavimas, krepšelis.
Serverio nėra: GitHub Actions kasdien ~09:00 (Vilniaus laiku) surenka pasiūlymus į `prices.json`, o programėlė telefone tik skaito tą failą.

## Šaltiniai

| Parduotuvė | Iš kur renkama |
|---|---|
| Maxima | maxima.lt/pasiulymai + teminiai leidiniai (Kalėdų mėnuo ir pan.) + savaitės leidinys iš akcijuseklys.lt |
| Rimi | rimi.lt e. parduotuvės akcijos, savaitinis leidinys + katalogai iš akcijuseklys.lt |
| Lidl | lidl.lt leidinių PDF + ne maisto ir kiti leidiniai iš akcijuseklys.lt |
| Norfa | norfa.lt leidinių PDF + kalėdinis katalogas iš akcijuseklys.lt |
| IKI, Promo, Šilas, Vynoteka | akcijuseklys.lt (atsarginis variantas IKI, Promo, Šilui – leidinio paveikslėlių OCR) |

Ta pati prekė iš kelių šaltinių rodoma vieną kartą (ta pati kaina ir panašus pavadinimas).
Grupinės nuolaidos be konkrečios kainos („-30 % visiems šampūnams“) rodomos kaip „−30 % grupei“.

## Paleidimas

- Automatiškai: kasdien 09:00 (atsarginiai paleidimai vėliau, jei GitHub pavėluoja).
- Programėlėje: mygtukas ↻ (reikia GitHub rakto su teise „Actions: Read and write“ tik šiam repo; raktas saugomas tik telefone).
- Ranka: **Actions → scrape → Run workflow** (galima nurodyti tik kai kurias parduotuves, pvz. `Šilas`).

## Failai

- `index.html`, `sw.js`, `manifest.webmanifest`, `icon.svg` – programėlė (PWA, galima „Įdiegti“ į telefono ekraną).
- `prices.json` – duomenys (generuojami automatiškai, ranka neredaguoti).
- `scraper/scrape.py` – rinkimas; `categories.py` – kategorijos; `stores.json` – parduotuvių nustatymai;
  `leaflets.py`, `lidl.py`, `norfa.py` – PDF skaitymas; `iki.py`, `promo.py`, `silas.py` – OCR (atsarginis); `fixnames.py` – OCR pavadinimų taisymas;
  `recat.py` – kategorijų perskaičiavimas be naujo rinkimo.
- Diagnostika po kiekvieno paleidimo įrašoma į šaką `debug-out`.
