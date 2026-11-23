# Kainos

Programėlė: https://g0odnight.github.io/kainos/

Parduotuvių **kainų leidinių** akcijos vienoje vietoje: paieška, parduotuvių ir kategorijų filtrai, rūšiavimas, krepšelis.
Serverio nėra: GitHub Actions kasdien ~08:00 (Vilniaus laiku) surenka leidinius į `prices.json`, o programėlė telefone tik skaito tą failą.

## Kaip tai veikia

| Parduotuvė | Šaltinis | Kur renkama |
|---|---|---|
| Maxima | maxima.lt/leidiniai (iPaper tekstas) | GitHub debesyje |
| Rimi | rimi.lt savaitinis leidinys (iPaper tekstas) | GitHub debesyje |
| Lidl | lidl.lt leidinių PDF | GitHub debesyje |
| IKI, Norfa, Promo | jų leidinių puslapiai | **tavo kompiuteryje** (žr. žemiau) |

IKI ir Promo svetainės saugomos „Cloudflare“, Norfos leidiniai – „yumpu“. Jie atmeta užklausas iš debesų serverių,
todėl šias tris parduotuves renka tas pats skriptas, paleistas tavo kompiuteryje įprastame Chrome lange.

## IKI, Norfa, Promo: rinkimas tavo kompiuteryje (nebūtina)

Kompiuteris turi būti įjungtas apie 08:40. Vienkartinis nustatymas (~10 min.):

1. Įdiek Python 3.12: `winget install Python.Python.3.12` (PowerShell) ir Google Chrome, jei dar nėra.
2. GitHub: repo **Settings → Actions → Runners → New self-hosted runner → Windows**. Įvykdyk ten parodytas komandas
   PowerShell'e (aplanke, pvz., `C:\actions-runner`). Paskutinį žingsnį `./run.cmd` pakeisk į `./svc.cmd install` ir `./svc.cmd start`,
   kad veiktų fone.
   *Pastaba:* kad atsidarytų Chrome langas, runner turi veikti kaip tavo vartotojas, ne kaip „Network Service“.
   Paprasčiausia – nediegti kaip paslaugos, o įdėti `run.cmd` į *Startup* aplanką (Win+R → `shell:startup`).
3. Repo **Settings → Secrets and variables → Actions → Variables → New variable**: `LOCAL_RUNNER` = `1`.
4. Patikrink: **Actions → scrape-local → Run workflow**.

Jei svetainė vis tiek parodys „ar ne robotas“ patikrinimą, tą dieną tos parduotuvės duomenys tiesiog liks seni.

## Rankinis paleidimas

**Actions → scrape → Run workflow** (debesis) arba **scrape-local** (kompiuteris).

## Failai

- `index.html`, `sw.js`, `manifest.webmanifest`, `icon.svg` – programėlė (PWA, galima „Įdiegti“ į telefono ekraną).
- `prices.json` – duomenys (generuojami automatiškai, ranka neredaguoti).
- `scraper/scrape.py` – rinkimas; `leaflets.py`, `lidl.py` – leidinių skaitymas; `categories.py` – kategorijos; `stores.json` – adresai.
- Diagnostika po kiekvieno paleidimo įrašoma į šaką `debug-out`.
