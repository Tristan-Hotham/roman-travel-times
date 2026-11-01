"""Step 6. Build index.html from code/page_template.html and code/fullscreen_snippet.html, and data/places.json (modern
place names for the page search, from Natural Earth). Every number in the text is a {{path|format}} token filled from
data/results.json; 10.5281/zenodo.23863542 and https://blog.tristanhotham.com/2026/10/31/roman-travel-times/ are left for the publisher.
Run: python3 code/06_build_site.py
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

R = jload(f"{DATA}/results.json")

# modern places for search: Natural Earth populated places inside the map
P = jload(f"{GEO}/ne_10m_populated_places_simple.geojson")["features"]
pl = []
for f in P:
    p = f["properties"]; lon, lat = f["geometry"]["coordinates"][:2]
    if -12 <= lon <= 47 and 21.5 <= lat <= 58.5:
        pl.append([p["name"], f"{p.get('adm0name') or ''}".strip(), round(lon, 4), round(lat, 4)])
pl.sort(key=lambda r: r[0])
jsave(pl, f"{DATA}/places.json")


def build():
    tpl = open(os.path.join(ROOT, "code", "page_template.html"), encoding="utf-8").read()
    html = fill(tpl, R)
    left = re.findall(r"\{\{[^}]*\}\}", html)
    assert set(left) <= {"10.5281/zenodo.23863542", "https://blog.tristanhotham.com/2026/10/31/roman-travel-times/"}, left[:5]
    J_ = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":"))
    html = html.replace("/*RESULTS*/", J_(dash(R))).replace("/*RAMP*/", J_(RAMP))
    html = html.replace("/*FULLSCREEN*/", open(os.path.join(ROOT, "code", "fullscreen_snippet.html"), encoding="utf-8").read())
    vis = re.sub(r"<script.*?</script>|<style.*?</style>|<!--.*?-->", "", html, flags=re.S)
    vis = re.sub(r"<[^>]+>", " ", vis)
    visible_text_ok(vis, "page")
    for scr in re.findall(r"<script>(.*?)</script>", html, flags=re.S):
        for bad in ("—", "–"):
            assert bad not in scr, bad
    open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8").write(html)
    print("index.html", len(html.encode()) // 1024, "KB; places", len(pl))


if __name__ == "__main__":
    build()
