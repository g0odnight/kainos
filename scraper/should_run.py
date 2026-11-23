"""Nusprendžia ar paleisti: rankinis paleidimas visada; pagal grafiką – tik po 08:00 Vilniaus laiku ir jei šiandien dar neatnaujinta."""
import datetime, json, os, pathlib
from zoneinfo import ZoneInfo
tz = ZoneInfo("Europe/Vilnius"); now = datetime.datetime.now(tz)
run = True
if os.environ.get("EVENT") == "schedule":
    run = now.hour >= 8
    try:
        u = json.load(open(pathlib.Path(__file__).resolve().parent.parent / "prices.json"))["updated"]
        if u and datetime.datetime.fromisoformat(u).astimezone(tz).date() == now.date(): run = False
    except Exception: pass
print("run =", run)
with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a") as f: f.write(f"run={'true' if run else 'false'}\n")
