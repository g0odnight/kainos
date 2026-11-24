import os
os.makedirs("probe/out", exist_ok=True)
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(locale="lt-LT")
    pg.goto("https://www.maxima.lt/leidiniai", wait_until="domcontentloaded", timeout=90000)
    try: pg.wait_for_load_state("networkidle", timeout=12000)
    except Exception: pass
    open("probe/out/list.txt", "w").write(pg.inner_text("body"))
    h = pg.evaluate("""()=>[...document.querySelectorAll('a[href*="leidiniai/"]')].map(a=>{let e=a,o=[];for(let i=0;i<6&&e;i++,e=e.parentElement)o.push(e.tagName+'.'+e.className+' :: '+(e.innerText||'').replace(/\\s+/g,' ').slice(0,200));return a.href+'\\n  '+o.join('\\n  ')}).join('\\n\\n')""")
    open("probe/out/cards.txt", "w").write(h)
    open("probe/out/list.html", "w").write(pg.content())
