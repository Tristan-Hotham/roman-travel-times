"""Step 10. Blog post and meta (release/blog), Zenodo files and metadata (release/zenodo), Reddit post (reddit/post.md).
Numbers written out in the blog's alt text are checked against results.json here.
Run: python3 code/10_release.py
"""
import os, re, sys, zipfile, json as _json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

R = jload(f"{DATA}/results.json"); C = R["city"]
REL = os.path.join(ROOT, "release"); NAME = "Hotham_By_Road_and_by_Sea"

# ---------- facts written as numbers in alt text ----------
alt = {"lepcis": (231, 9), "carthago": (210, 6), "alexandria": (180, 12), "hierosolyma": (157, 17), "antiochia": (128, 17), "gades": (116, 13),
       "eboracum": (94, 40), "london": (81, 30), "constantinople": (75, 17), "athenae": (67, 11), "lutetia": (67, 37), "massilia": (45, 6)}
for k_, (a, b) in alt.items():
    assert (round(C[k_]["winter_foot"]), round(C[k_]["summer_foot"])) == (a, b), (k_, C[k_]["winter_foot"], C[k_]["summer_foot"])
A = R["area_share"]
assert (round(A["winter_foot"]["30"] * 100, 1), round(A["summer_foot"]["30"] * 100), round(A["winter_courier"]["30"] * 100), round(A["summer_courier"]["30"] * 100)) == (3.9, 59, 53, 92)
assert R["validation"]["n"] == 34 and round(R["params"]["ostia_alex_days"]) == 11 and round(R["params"]["alex_ostia_days"]) == 30
assert R["table1_B"]["n"] == 57 and R["table1_rows"] and len(R["table1_rows"]) == 57 and round(R["params"]["A"]["alex_ostia_days"]) == 63

post = fill(open(os.path.join(ROOT, "code", "blog_template.html"), encoding="utf-8").read(), R)
used = re.findall(r"\{\{IMG\|([^|]+)\|", post)
assert 5 <= len(used) <= 8, used
for img in used:
    assert os.path.exists(f"{REL}/blog/{img}"), img
for fn in os.listdir(f"{REL}/blog"):
    if fn.startswith("b_") and fn not in used:
        os.remove(f"{REL}/blog/{fn}")
for ln in post.splitlines():
    if "{{IMG|" in ln:
        assert ln.startswith("{{IMG|") and ln.endswith("}}"), ln
assert not re.search(r"\{\{(?!IMG\||DOI_URL\}\}|BLOG_URL\}\}|DOI\}\})", post)
vis = re.sub(r"<!--.*?-->", "", post, flags=re.S)
visible_text_ok(vis, "blog")
open(f"{REL}/blog/post.html", "w", encoding="utf-8").write(post)
words = len(re.sub(r"<[^>]+>|\{\{IMG\|[^}]*\}\}", " ", vis).split())
meta = {"title": "By road and by sea: the fastest way from Rome to anywhere in the Roman Empire",
        "slug": "roman-travel-times",
        "excerpt": f"By road alone Carthage was {C['carthago']['winter_foot']:.0f} days' walk from Rome. With a ship it was {C['carthago']['summer_foot']:.0f}. I added the sea to my map of Roman roads, with sailing speeds from ancient voyages and the summer etesian winds.",
        "seo_description": "Fastest travel times from Rome across the Roman Empire by road and by sea, with ancient sailing speeds and the summer winds.",
        "tags": ["Roman Empire", "Roman roads", "ancient shipping", "history", "maps", "data visualisation", "travel time", "Itiner-e"],
        "header_alt": f"Title card reading 'By road and by sea' in black on cream, beside a map of the Mediterranean where roads and sea are coloured by days from Rome, red and orange around Italy and across the sea to Africa and Egypt, green and blue further away. Text: Carthage {C['carthago']['winter_foot']:.0f} days by road, {C['carthago']['summer_foot']:.0f} with a ship; Alexandria {C['alexandria']['winter_foot']:.0f} days, or {C['alexandria']['summer_foot']:.0f}."}
assert len(meta["seo_description"]) < 160, len(meta["seo_description"])
jsave(meta, f"{REL}/blog/meta.json", indent=2)

# ---------- Zenodo ----------
Zd = f"{REL}/zenodo"; os.makedirs(Zd, exist_ok=True)
for fn in os.listdir(Zd):
    os.remove(os.path.join(Zd, fn))
os.link(f"{REL}/paper/{NAME}.pdf", f"{Zd}/{NAME}.pdf")
zp = f"{Zd}/roman-travel-times_code_and_data.zip"
with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
    for d in ("code", "data"):
        for fn in sorted(os.listdir(os.path.join(ROOT, d))):
            if fn.endswith(".pyc") or fn == "__pycache__":
                continue
            z.write(os.path.join(ROOT, d, fn), f"roman-travel-times/{d}/{fn}")
    for fn in ("README.md", "LICENSE", "reddit/collage.py"):
        z.write(os.path.join(ROOT, fn), f"roman-travel-times/{fn}")
tex = open(f"{REL}/paper/{NAME}.tex", encoding="utf-8").read()
ab = re.search(r"\\begin\{center\}\\textbf\{Abstract\}\\end\{center\}\n(.*?)\n\n\\textbf\{Keywords", tex, re.S).group(1)
ab = ab.replace("\\%", "%").replace("\\&", "&").replace("\\emph{", "").replace("}", "")
zmeta = {"title": "By Road and by Sea: Fastest Travel Times from Rome in the Roman Empire, with Itiner-e Roads, Pleiades Ports and Casson's Sailing Speeds",
         "upload_type": "publication", "publication_type": "workingpaper",
         "description": f"<p>{ab}</p><p>Interactive version: <a href=\"{PAGE_URL}\">{PAGE_URL}</a>. Data and code: <a href=\"{REPO}\">{REPO}</a>. Blog post: {{https://blog.tristanhotham.com/2026/10/31/roman-travel-times/}}. Companion study: <a href=\"https://doi.org/{ROADS_DOI}\">Roads of the Roman Empire</a>.</p>"
                        f"<p>Data: Itiner-e static version 2024 (de Soto, Pažout, Brughmans et al. 2025, https://doi.org/{ITINERE_DOI}), CC BY 4.0. Ports: Pleiades (CC BY 3.0). Provinces: Digital Atlas of the Roman Empire (DARE, Johan Åhlfeldt, CC BY). Sailing speeds: Casson (1951), TAPA 82, 136-148. Land: Natural Earth (public domain). Derived data, figures and text: CC BY 4.0. Code: MIT.</p>",
         "creators": [{"name": "Hotham, Tristan", "affiliation": "Independent researcher", "orcid": "0000-0003-4931-9349"}],
         "keywords": ["Roman Empire", "travel time", "sea routes", "ancient shipping", "sailing speeds", "etesian winds", "Itiner-e", "Pleiades", "network analysis"],
         "license": "cc-by-4.0", "language": "eng",
         "related_identifiers": [{"identifier": REPO, "relation": "isSupplementedBy", "resource_type": "software"},
                                 {"identifier": PAGE_URL, "relation": "isSupplementedBy", "resource_type": "other"},
                                 {"identifier": f"https://doi.org/{ROADS_DOI}", "relation": "continues", "resource_type": "publication-workingpaper"},
                                 {"identifier": f"https://doi.org/{ITINERE_DOI}", "relation": "isDerivedFrom", "resource_type": "dataset"},
                                 {"identifier": "https://pleiades.stoa.org/", "relation": "isDerivedFrom", "resource_type": "dataset"},
                                 {"identifier": "https://www.naturalearthdata.com/", "relation": "isDerivedFrom", "resource_type": "dataset"}],
         "notes": AI}
s = _json.dumps(zmeta, ensure_ascii=False) + _json.dumps(meta, ensure_ascii=False)
visible_text_ok(s, "meta")
jsave(zmeta, f"{Zd}/metadata.json", indent=2)

# ---------- Reddit post ----------
pm = f"""## Title

[OC] Roman travel times by road against road and sea: Carthage was {C['carthago']['winter_foot']:.0f} days' walk from Rome by road, and {C['carthago']['summer_foot']:.0f} days with a ship

## Body

Follow-up to my map of Roman roads, where many of you pointed out that nobody walked to Carthage. I joined {R['n_ports']} ancient ports (Pleiades and the ancient voyage reports) to the {R['km_total']:,.0f} km of road in Itiner-e and to a {R['cell_km']:.0f} km grid of sea cells. Sailing speeds come from Casson's 1951 article on ancient voyages, calibrated to his table of estimated sailing times between {R['table1_B']['n']} pairs of ports: {R['params']['v_down']:.1f} knots running before the wind, {R['params']['v_neu']:.1f} where no prevailing wind is recorded, and {R['params']['v_up']:.1f} to {R['params']['v_up_e']:.1f} knots straight into the summer etesian winds. Rome to Alexandria comes out at {R['params']['ostia_alex_days']:.0f} days (Casson: 10 to 13). On foot on land: Carthage {C['carthago']['winter_foot']:.0f} to {C['carthago']['summer_foot']:.0f} days, Alexandria {C['alexandria']['winter_foot']:.0f} to {C['alexandria']['summer_foot']:.0f}, London {C['london']['winter_foot']:.0f} to {C['london']['summer_foot']:.0f}, Constantinople {C['constantinople']['winter_foot']:.0f} to {C['constantinople']['summer_foot']:.0f} (upwind all the way up the Aegean, and the least certain: {C['constantinople']['modelA_foot']:.0f} with Casson's slower median speeds). The share of the provinces' land within 30 days of Rome goes from {A['winter_foot']['30'] * 100:.1f}% to {A['summer_foot']['30'] * 100:.0f}%. Caveats: modelled times, one summer wind pattern, no storms or calms. The model lands within a quarter of Casson's estimate for {R['table1_B']['near'] * 100:.0f}% of his {R['table1_B']['n']} passages, but it is too quick on the long voyage home from the east (Alexandria to Rome in {R['params']['alex_ostia_days']:.0f} days against his 53 to 73). Interactive map where you can start anywhere: {PAGE_URL}

## Source comment

Source: Itiner-e static version 2024, de Soto, Pažout, Brughmans et al. (2025), Zenodo doi:10.5281/zenodo.17122148, CC BY 4.0 (roads). Pleiades gazetteer, CC BY 3.0 (ports). Casson, L. (1951) Speed under sail of ancient ships, TAPA 82: 136-148, online edition on LacusCurtius (sailing speeds and estimated voyage times). English Wikipedia 'Etesian' and 'Mare clausum' (winds and season), 'Roman roads' (land speeds). DARE (provinces). Natural Earth (land).

Tools: Python (geopandas, scipy, shapely, pyproj, matplotlib); Leaflet for the interactive map. Derived data and figures: CC BY 4.0.

Interactive version: {PAGE_URL}
Paper: {{https://doi.org/10.5281/zenodo.23863542}}
Blog post: {{https://blog.tristanhotham.com/2026/10/31/roman-travel-times/}}
"""
visible_text_ok(pm, "post")
open(os.path.join(ROOT, "reddit", "post.md"), "w", encoding="utf-8").write(pm)
print("blog words", words, "; figures", len(used), "; zenodo", sorted(os.listdir(Zd)), os.path.getsize(zp) // 1024, "KB zip")
