"""Prekių kategorijos pagal pavadinimą.
Regex taikomi normalizuotam pavadinimui (mažosios raidės, be lietuviškų diakritikų).
Tvarka svarbi: tikrinama iš eilės, laimi pirma tinkanti taisyklė."""
import re, unicodedata

# Rodymo tvarka programėlėje
META = [
    ("vaisiai", "Vaisiai ir daržovės", "🥦"),
    ("mesa", "Mėsa ir mėsos gaminiai", "🥩"),
    ("zuvis", "Žuvis ir jūros gėrybės", "🐟"),
    ("pienas", "Pieno gaminiai ir kiaušiniai", "🥛"),
    ("duona", "Duona ir kepiniai", "🍞"),
    ("kulinarija", "Kulinarija", "🥗"),
    ("konditerija", "Konditerija", "🎂"),
    ("saldyta", "Šaldytas maistas", "🧊"),
    ("saldumynai", "Saldumynai", "🍫"),
    ("uzkandziai", "Užkandžiai ir riešutai", "🥨"),
    ("bakaleja", "Bakalėja", "🍝"),
    ("konservai", "Konservai ir padažai", "🥫"),
    ("kava", "Kava, kakava, arbata", "☕"),
    ("gerimai", "Gėrimai", "🥤"),
    ("alkoholis", "Alkoholiniai gėrimai", "🍷"),
    ("vaikai", "Kūdikių ir vaikų prekės", "🍼"),
    ("gyvunai", "Prekės gyvūnams", "🐾"),
    ("kosmetika", "Kosmetika ir higiena", "🧴"),
    ("buitine", "Buitinė chemija ir popierius", "🧽"),
    ("namai", "Namai, laisvalaikis, įrankiai", "🧰"),
    ("augalai", "Gėlės ir augalai", "🌱"),
    ("kita", "Kita", "🛒"),
]

# (kategorija, regex) – tikrinimo tvarka
RULES = [
    # tikslūs išimčių atvejai (prieš bendras taisykles)
    # grupinės nuolaidos (dažnai naudininku: „padažams“, „sūriams“, „vaikų maistui“)
    ("konservai", r"(padazams|kecupui|mutti)"),
    ("vaikai", r"(vaiku maist|vaiku prieziur|tommee|marmaluzi)"),
    ("kosmetika", r"(prezervatyv|lubrikant|\btaft\b|oral-b|sukuosenos formavimo)"),
    ("buitine", r"(buitin\w* chemij|coccolino|arbre vert|acappella|lappel)"),
    ("gyvunai", r"(optimeal|pavadel)"),
    ("namai", r"(automobili\w* (prek|prieziur)|automobiliniams|ledo grandikl|sniego sepet|maisto laikymo|maisto ruosimo (irank|priemon|medziag)|virtuves (prek|reikm)|klijams|tvirtinimo|dovanu pakavimo|kalendoriams|kaledine apranga|kaledinia?i? nykstuk|vienkartin\w* (dezut|irank|ind|lekst)|tortu padekl|daugkartinio naudojimo|varikliu alyv)"),
    ("mesa", r"(fasuotai mesai|krekenavos gaminiams|mazeikiu mesine|nematekas|giminiu produkcija)"),
    ("pienas", r"(suriams|pelesiniams)"),
    ("zuvis", r"(\btunams|sukutes)"),
    ("saldumynai", r"(saldumynams|saldumynai geisha|hematogen|magic of winter)"),
    ("bakaleja", r"(sausi[ae]ms pusryciams|sultiniams|sultiniai|sriuboms|(produkcij\w*|visai|produktams).{0,30}(maggi|knorr|santa maria|bonduelle|oetker|gourmet green|bornibus)|(maggi|knorr|bonduelle|oetker|bornibus).{0,20}produkcij|\bmedui\b)"),
    ("uzkandziai", r"(o!nuts|onuts)"),
    ("gerimai", r"(\bgirai\b)"),
    ("vaikai", r"((?<!kirpimo )masinel|traukin|kaladel|gelezinkel|virtuvel|vagonel|lavinam|ridenimo|teleskop|sraigtaspar|kvadrokopter|nuotoliniu budu valdom|muzikos instrument|klavisin|sintezator|zemelap|mokomas|walkie|spalvoti piestuk)"),
    ("namai", r"(^(?!.*(zaisl|lego)).*(siurbl|valytuv|plaktuk)|uzuolaid|sildytuv|kilimas|irigator|kraujospud|masazinis pistolet|kompresor|pledas|paltas|puodu rinkin|klimato stotel|kroviklis|kedut|sluot|plakikl|trintuv|tualeto reikmen|paklode|rakt\w* pakabuk|puosu rinkin)"),
    ("saldumynai", r"(roulette|ritineliai|karamele su pieno|surio sausain)"),
    ("vaisiai", r"(^(?!.*(jogurt|varsk|dziovint)).*silauog)"),
    ("buitine", r"(nosinait)"),
    ("duona", r"(riestain)"),
    ("alkoholis", r"(^rinkinys nr)"),
    ("buitine", r"(valymo (pasta|priemon|servet|milt)|cillit|mr\.? ?soda)"),
    ("bakaleja", r"(stiklin\w* makaron)"),
    ("konservai", r"(sur\w*.{0,30}(pad\.|padaz))"),
    ("uzkandziai", r"(cheetos|doritos|sauleg\w*(?! aliej)\b(?!.{0,10}aliej)|traskuc)"),
    ("saldumynai", r"(^vafl|\bvafliai\b)"),
    ("pienas", r"(lyd\.? ?(ruk\.? ?)?sur|ruk\.? ?lyd|lydytas suris)"),
    ("augalai", r"(^(?!.*lego).*(\brozes\b|chrizantem|frezij|skintos|skintu|tulpes))"),
    ("saldumynai", r"(advento kalendoriai$|advento kalendorius .{0,30}(sokolad|kinder|milka|lindt|kit kat|ferrero|saldain)|tepamasis kremas|nutella|skanestu rinkin)"),
    ("alkoholis", r"(chardonnay|merlot|sauvignon|cabernet|riesling|cremant|appassimento|primitivo|tempranillo)"),
    ("zuvis", r"(pleksn|argentin|austres|sardines|sardin)"),
    ("mesa", r"(\bantis\b(?!\.)|anties)"),
    ("kulinarija", r"(kebabas|pietu rinkin|^(?!.*milt).*tempura|\bsusi\b)"),
    ("bakaleja", r"(tapijok|kataifi|\bfilo\b|^(?!.*saldyt).*\btesla\b)"),
    ("duona", r"(prancuziski batonai|batonai\b)"),
    ("vaisiai", r"(baklazan(as|ai)\b|(?<!dziovinti )\bmangai\b|salota iceberg|\bsalota\b)"),
    ("buitine", r"(valymo putos|kvapui|demems|tirpikl|valymo irengin)"),
    ("vaikai", r"(lipduk|automodel|automobilio model|modelis 1:|pies\. rinkin|piesimo rinkin|play-doh|littlest pet|slime|gleiv|mokyklin|^(?!.*(sald|sokolad)).*kamuol|\blel(e|ems|es|iu)\b|vienarag|mikroskop|eksperiment|paspirtuk|arkliuk|clementoni|mini brands|miniatiur|^(?!.*(sokolad|kinder|smarties|kit kat|saldain|favorina)).*figurel|zaisl|\blego\b|delion|konstrukt|kurybinis rinkinys|kurybos rinkin|hot wheels|barbie|stalo zaidim|\brc\b|balansinis|spalvinimo|plius\.|pliusin|kemperis|robotas|magnetuk|\d+ m\+)"),
    ("pienas", r"(\bkiausiniai\b|kiausiniu \d|kefyro gerim|pieno gerim|kastinys)"),
    ("saldyta", r"(alaus tesloje|\bledai\b|\bledams\b|\bledu\b(?! saldain))"),
    ("kulinarija", r"(\bkibin(as|ai)\b|sumustinis\b|kebabo)"),
    ("duona", r"(plesomosios bandel|brioche)"),
    ("konservai", r"(konservuoti|marinuoti .{0,30}agurk|sviestines pupel|pomidoru pasta|krienai|remulad)"),
    ("mesa", r"(servelat|sardel|kabanos|varliu slaunel)"),
    ("saldumynai", r"(saldumynu rinkin|saldainiu rinkin|saldiniu rinkin|ledinuk|celebrations|snow balls)"),
    ("buitine", r"(avalynes|impregnant|namu kvap|automobiliu kvap)"),
    ("namai", r"((torto|pyrago|keksiuk\w*|kepimo|sausainiu) form|^(?!.*(vaik|kudik|huggies|pampers)).*(kepur|pirstin|salikas|ausines|gobtuv|beret|slepet|kojin|apatiniai|marskinel|trumpik|kelnait|pizam|bokser|liemenel|megztin|striuk|dzemper|kelnes|marskiniai|tampres|pedkelnes|chalat|sortai)|(?<!pl\. )(?<!plauku )dazai|drob(e|iu)|pakabai|pjovimo|slifav|kombain|lygintuv|klaviatur|\bpele\b|fotoaparat|patefon|knyg|aukst\w* slegio|kaledin(e|es|iai|is) (dekor|egl|papuos|kepur)|dekoracij|girliand|dirbtine eglut|egles virsune|eglutes papuos|dubenel|tortine|\bsamtis|serviravimo|zirkles|atidarytuv|asotis|gertuve|termo |kanceliar|tusinuk|piesimo|kaledu senis su)"),
    ("duona", r"(\bbatonas\b|prancuziskas batonas|bagete)"),
    ("bakaleja", r"(pagalveles|kukuruzu dribs|avizin)"),
    ("gyvunai", r"(katem|kates\b|kaciu|kaciuk|katei\b|\bsun(ims|u|ys|iui|eliams)\b|sunim|sunu\b|gyvun|pasaras|pasaro|kraik|grauzik|papug|akvarium|pedigree|whiskas|felix|friskies|purina|kitekat|chappi)"),
    ("vaikai", r"(kudik|sauskel|vystykl|zinduk|pampers|huggies|nuo \d+ men|vaikisk|vaikams)"),
    ("buitine", r"(\bw5\b|svaros prek|skalb|indaplov|ploviklis|plovikl|valikl|minkstikl|balikl|dezinf|kalkiu|\bwc\b|siuksliu|maiseli|kempin|sluost|\bariel|persil|lenor|fairy|finish|domestos|vanish|calgon|\bcif\b|purio|formil|silan|tualetinis popier|popierinis ranksl|servetel|kvapikl|oro gaiv|allin ?(1|one)|\bdiscs\b|folija|kepimo popier|maistine pleve)"),
    ("kosmetika", r"(sampun|kondicionier|\bmuil|dantu|burnos|dezodor|antiperspir|kosmet|veido|rank(u|ų) krem|kuno|losjon|plauk|skutim|skustuv|higien|\bvatos|vatos|paklotel|tamponai|ikl(u|i)ot|kvepal|tualetinis vanduo|sensodyne|colgate|nivea|gillette|dus(o|ui) (gel|zele)|duso zel|vonios|nagu|lupu|makiaz|pastiles)"),
    ("augalai", r"(\begle\b|eglut(e|es)\b(?!.{0,20}(sokolad|saldain))|egle |kenis|puansetij|selagin|phalaenops|orchid(?!.{0,8}vanil)|\bgel(e|es|iu)\b|vazon|augal|puokst|sodinuk|trasos|zemes misin|tulpi|amarili)"),
    ("namai", r"(akumuliator|grezt|slifuokl|\bpjuk|irankiu|irankis|parkside|silvercrest|ernesto|livarno|crivit|lupilu|esmara|lempa|lemput|zibint|girliand|baterij|kabel|patalyn|pagalv|antklod|rankslu|chalat|kojin|marskin|kelnes|striuk|\bbatai|slepet|zaisl|zaidim|\blego|\blel(e|es)\b|keptuv|puod(as|ai|ukas)|peili|\bindai\b|lekst|puodel|stiklin|taure|termos|zvak|dekoracij|elektrin|maisytuv|virdul|gruzdintuv|svarstykl|laikrod|kuprin|lagamin|dvirat|pieno putu|rinkinys martinelia|dollhouse|gabby|stitch|frozen|magic studio)"),
    ("alkoholis", r"(\bvyn(as|o|ai|u)?\b(?!uog)|vynas|sampan(?!.{0,10}skonio)|\balus\b|\balaus\b|degtin|\bviski|whisk|konjak|brendis|brandy|\bromas\b|\bgin\b|dzinas|likeris|likerio|trauktin|sidras|\bvodka|prosecco|martini|stiprus gerim|spiritin|captain morgan|tekila)"),
    ("kava", r"(kava|kavos|kavine|lavazza|jacobs|nescafe|paulig|pellini|dallmayr|arbat|kakava|kakavos (milt|gerim)|cikorij|karstas sokoladas)"),
    ("gerimai", r"(gerim|sultys\b|sulciu|nektar|vanduo|vandens|mineralin|limonad|gira\b|\bcola\b|coca|pepsi|fanta|sprite|energin|tonik|kokteil|smoothie|kombuc|depozit|nealkohol|tymbark|oshee|izotonin)"),
    ("uzkandziai", r"(trasku|traskios|\bcips|chips|popcorn|spragesi|krekeri|snack|lay.?s|pringles|estrella)"),
    ("bakaleja", r"(prieskon|makaron|lakst|ramen|nudel|sultinys|buljon|\bpadaz(as|ai)\b|marinat|kosė .*knorr|kose .*knorr)"),
    ("saldyta", r"((?<!at)saldyt(?!uv)|\bledai|ledai|\bledu\b|plombyr|\bpica|picos|koldun|virtiniai|ceburek|panzerotti)"),
    ("kulinarija", r"(kulinar|apkepel|rizotas|\bsalotos\b(?! lap)|salotos,|\bsalotu\b|susi\b|sushi|griliu? visti|kepta visti|paruostas maist|patiekal|cepelin|balandel|vedarai|kugel|suktinuk|wrap|kotlet|\bblynai|\bplovas|sriuba(?!.{0,20}(sausa|koncentr|kub))|paruosti valgyti|vitello|lasagn|lazanij)"),
    ("zuvis", r"(zuv|lasis|lasiu|lasisa|lasisos|silk|krevet|ikrai|\bikr|tun(as|ai|u)\b|sprot|skumbr|strimel|menk|upetak|karpi|lydek|kalmar|midij|krab|surimi|juru ?geryb|wide ocean|\beser|juri?nis eser|ersket|stint|omar|astuonkoj|polok|heke|tilapij|dorad|lasis)"),
    ("mesa", r"(mes(a|os)\b|mesos|visti|vistuk|visciuk|kiauli|jautien|versien|aviena|antien|kalakut|triusi|zverien|sernien|elnien|desr|sosis|kumpi|skiland|\bsonin|\bfars|kepsnin|saslik|broiler|blauzdel|sparnel|kepenel|pastet|saliam|salami|mortadel|chorizo|prosciutto|iberico|bekon|vytint|nugarin|pjausn|mente\b|sprandin|karbonad|paukstien|\bfile\b|\bfile )"),
    ("pienas", r"(pien(as|o)(?!.{0,25}sokolad)|\buht\b|jogurt|kefyr|varsk|sur(is|io|iu|iai|elis|eliai)|sureli|sviest|grietin|kiausin|margarin|pudingas|mocarel|mozzarel|\bfeta\b|parmez|parmigiano|gouda|cheddar|maskarpon|mascarpon|rikota|ricotta|ayran|pasukos|rugpien|tvarog|glaistyt|lydytas|brie\b|camembert|gorgonzol)"),
    ("konditerija", r"(panet|pandoro|profitrol|sluoksniuot|tortas|\btort(o|ai|eliai|elis)\b|pyrag|keks|eklera|beze|spurg|kibin|desert|stolen|meduol|vyniotin|ruletas|tiramisu|kuciuk|sakot|bandel(e|es) su|cinamonin|kruasan|croissant)"),
    ("saldumynai", r"(sokolad|saldain|sausain|vafl|zefyr|marmelad|guminuk|kramtom|karamel|batonel|iriso|halva|praline|triufel|lindt|milka|kinder|ferrero|raffaello|toblerone|snickers|twix|\bmars\b|bounty|m&m|haribo|\bruta\b|marcipan|pinigeliai|\bnuga\b|drazes|draze|advento kalendorius|cukrines lazdel|lazdele ?mega)"),
    ("bakaleja", r"(cukruot|aliejus|aliejaus|sekl(u|os) aliej)"),
    ("duona", r"(baget|duon|grudaini|batonas|\bbaton\b|bandel|bandut|raguol|ciabat|bagete|\bbagel|tortilij|lavas|\bpita\b|skrebuc|tosto|kepinys|kepiniai|plutele|sumustiniu)"),
    ("uzkandziai", r"(riesut|migdol|lazdyn|anakard|pistacij|sauleg|moliugu sekl|uzkand|alyvuog(?!.{0,15}aliej))"),
    ("vaisiai", r"(mangas|mandar ?nai|obuol|banan|mandarin|apelsin|citrin|\bkiv|kiwi|agurk|pomidor|\bmork|bulv|kopust|svogun|darzov|vaisi(ai|u)\b|avokad|persimon|\buog(os|u)\b|braskes|avietes|melynes|spanguol|salotos lap|salotu lap|paprik|brokol|kalafior|grybai|grybu|pievagryb|ananas|vynuog|kriaus|cesnak|burokel|cukinij|moliug|granat|greipfrut|laim(as|ai)\b|petrazol|krapai|ridik|salier|porai|sparag|mango|slyv|abrikos|persik|nektarin|arbuz|melion|datul|figos|imbier|zalumyn|rukola|spinat|batat|artisok|kokos(as|ai)\b)"),
    ("konservai", r"(catnis|konserv|zirnel|pupel|kukuruz|pomidoru padaz|savo sultyse|marinuot|raugint|agurkeliai|troskin|uogien|dzem(?!per)|kompot|\bmedus|kecup|majonez|garstyc|padaz|uztepel|tyre|alyvuoges)"),
    ("bakaleja", r"(raviol|makaron|spagec|\bryz(iai|iu|ai)|balandos|dziuvesel|panko|kruop|grikiai|miltai|cukrus|cukraus|druska|druskos|aliejus|aliejaus|aliejui|\bactas|dribs|avizin|musli|granol|prieskon|pipir|cinamonas|vanil|mieles|sultinys|buljon|kubel|ramen|nudel|lakst|kuskus|bulgur|avinzirn|lesi(ai|u)|\bpasta\b|kepimo|glajus|glazur|papuosim|pabarstuk|sirup|cukruot|razin|dziovint|sekl(os|u)|kokoso droz|krakmol|zelatin|tagliolin|penne|fusilli|kepiniams)"),
    # paskutinės: sutrumpinti (Rimi) pavadinimai, kurių ankstesnės taisyklės neatpažino
    ("namai", r"(\bpedk\b|pedk\.|\bvyr\.? ?apat|pizama|aut\.? ?gaiv|automobilio gaiv|staltiese|\bdubuo\b|luminarc|mentele|serv\.? ?rinkin|indeliu|kaspin|dovanu (popier|krepsel|maisel)|krepinis popier|pakabinam|zvaigzd|girlaind|nykstuk|cozy home|dekor|atspindint|zvake|zvakid|lekst|puodel|taure|stiklin|padekl|rankine|kuprin|lagamin)"),
    ("vaikai", r"(matchbox|rastar|\blavin|staigmena|jellykings|metal mashines|automobiliuk|meskiuk|\bciul\.|avent|\bhipp\b|hot wheels|barbie|pliusin|minkstas zais)"),
    ("buitine", r"(tual\.? ?gaiv|tualeto gaiv|pop\.? ?ranksl|skal\.? ?pri|tri-bio|batu krem|\bindu plov|grindu|stiklu valy)"),
    ("zuvis", r"(\bkrev\.)"),
    ("gyvunai", r"(\bkat\.|\bed\.|edalas|\bsun\.)"),
    ("bakaleja", r"(balzam\w*\.? ?act)"),
    ("kosmetika", r"(hig\.? ?paket|drek\.|kilig|\bd\.? ?zele|dus\.? ?zel|puršk\.? ?kond|pursk\.? ?kond|pursk\.? ?dez|\bdez\.|balzam(?!.{0,6}act)|listerine|b\.? ?sk\.? ?skyst|rexona|neutrogena|garnier|loreal|l'oreal|dove\b|palmolive|schauma|syoss|head ?& ?shoulders|pantene|(?<!balzam\.)(?<!acto )kremas\b(?!.{0,20}act))"),
    ("kava", r"((^|\s)arb\.)"),
    ("gerimai", r"(\bgaz\.|cido|hohes c|vais\.? ?sult|\bsk\.? ?ger|\bger\.)"),
    ("konservai", r"(\bkons\.)"),
    ("bakaleja", r"(priesk|sausi pusryciai|miltu misin|\bmakar\.|tako\b|sriub)"),
    ("uzkandziai", r"(trapuc|siaudeliai|lazdeles|karaliskasis misinys|kraker)"),
    ("pienas", r"(\bvars\.|\bsur\.|\bjog\.)"),
    ("saldumynai", r"(\bsaus\. su|saus\..{0,15}(sok|sk\.)|sald\. rinkin|pien\. sald|\bsok\.)"),
    ("alkoholis", r"^(?!.*(nekt|sult|ger\.|gaz|vand|limon|sirup|\bvit\.)).*(0,75 l|0,7 l)$"),
]

def norm(s):
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn").replace(",", ",")

_R = [(cid, re.compile(rx)) for cid, rx in RULES]
IDS = [m[0] for m in META]

def classify(name):
    t = norm(name)
    for cid, rx in _R:
        if rx.search(t): return cid
    return "kita"


# Rimi e. parduotuvės skyriai -> mūsų kategorijos (kai pagal pavadinimą neatpažinta)
TOP = {"vaisiai, darzoves ir geles": "vaisiai", "augaliniai produktai": "bakaleja", "pieno produktai ir kiausiniai": "pienas",
       "duonos gaminiai": "duona", "mesa ir zuvis": "mesa", "saldytas maistas": "saldyta", "bakaleja": "bakaleja",
       "rimi konditerija ir kulinarija": "kulinarija", "vaiku ir kudikiu prekes": "vaikai", "saldumynai ir uzkandziai": "saldumynai",
       "gerimai": "gerimai", "alkoholiniai ir nealkoholiniai gerimai": "alkoholis", "kosmetika ir higiena": "kosmetika",
       "buitines chemijos ir valymo priemones": "buitine", "gyvunu prekes": "gyvunai", "namu ukio ir laisvalaikio prekes": "namai"}

def classify_hint(path):
    """path – Rimi skyrių pavadinimai nuo bendriausio iki tiksliausio."""
    for p in reversed(path[1:]):
        c = classify(p)
        if c != "kita": return c
    return TOP.get(norm(path[0]).strip(), "kita") if path else "kita"
