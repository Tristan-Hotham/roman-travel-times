"""Step 9. README.md and LICENSE, numbers from data/results.json.
Run: python3 code/09_readme.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

R = jload(f"{DATA}/results.json"); C = R["city"]; P = R["params"]; A = R["area_share"]
kb = lambda f: f"{os.path.getsize(os.path.join(DATA, f)) // 1024:,} KB"
rows = "\n".join(f"| {C[k]['name']} | {C[k]['winter_foot']:.0f} | {C[k]['summer_foot']:.1f} ({C[k]['summer_foot_min']:.0f} to {C[k]['summer_foot_max']:.0f}) | {C[k]['winter_courier']:.0f} | {C[k]['summer_courier']:.1f} |" for k in R["compare"])
readme = f"""# By road and by sea

The fastest way from Rome to anywhere in the Roman Empire, by road and by sea. A follow-up to [Roads of the Roman Empire]({ROADS_PAGE}): the same Itiner-e road network ({R['km_total']:,.0f} km), plus {R['n_ports']} ancient ports and a {R['cell_km']:.0f} km sea grid, with sailing speeds from Casson's (1951) ancient voyage reports and the summer etesian winds. Winter (the closed sea) is roads only.

Interactive page: https://maps.tristanhotham.com/roman-travel-times/
Paper: https://doi.org/{{10.5281/zenodo.23863542}}
Blog post: {{https://blog.tristanhotham.com/2026/10/31/roman-travel-times/}}

## Headline results

- Carthage: {C['carthago']['winter_foot']:.0f} days on foot from Rome by road, {C['carthago']['summer_foot']:.1f} days with a ship in summer ({R['carthage_ratio']:.0f} times quicker).
- Alexandria {C['alexandria']['winter_foot']:.0f} to {C['alexandria']['summer_foot']:.0f} days; London {C['london']['winter_foot']:.0f} to {C['london']['summer_foot']:.0f}; Constantinople {C['constantinople']['winter_foot']:.0f} to {C['constantinople']['summer_foot']:.0f} (upwind in the Aegean; {C['constantinople']['modelA_foot']:.0f} with the slower model A; for a courier {C['constantinople']['winter_courier']:.0f} against {C['constantinople']['summer_courier']:.0f}).
- Share of the provinces' land within 7, 14 and 30 days of Rome on foot: {A['winter_foot']['7'] * 100:.1f}%, {A['winter_foot']['14'] * 100:.1f}% and {A['winter_foot']['30'] * 100:.1f}% by road alone; {A['summer_foot']['7'] * 100:.1f}%, {A['summer_foot']['14'] * 100:.1f}% and {A['summer_foot']['30'] * 100:.0f}% with the sea in summer.
- The sea brings the ports of Africa closest: Carthage {R['closest_ratio'][0]['ratio']:.0f} times, Hadrumetum and Hippo Regius about 30 times. {R['majors_no_gain']} of {R['n_majors']} major places, all in central Italy, gain nothing.
- Validation against Casson's Table 1 ({R['table1_B']['n']} estimated passages between named ports). Model B (calibrated, headlined): {R['table1_B']['n_inside']} inside his range ({R['table1_B']['inside'] * 100:.0f}%), {R['table1_B']['n_near']} within a quarter of it ({R['table1_B']['near'] * 100:.0f}%), median ratio {R['table1_B']['median_ratio']:.2f}. Model A (Casson's medians, speed into the wind fitted to Alexandria to Rome in 63 days): {R['table1_A']['n_inside']} inside ({R['table1_A']['inside'] * 100:.0f}%), {R['table1_A']['n_near']} near ({R['table1_A']['near'] * 100:.0f}%), median ratio {R['table1_A']['median_ratio']:.2f}.
- Model B sails Ostia to Alexandria in {P['ostia_alex_days']:.1f} days (Casson: 10 to 13) but back in {P['alex_ostia_days']:.0f} (Casson: 53 to 73): on the {R['table1_returns']['n']} long voyages home from the east it takes {R['table1_returns']['median_ratio_B']:.2f} times his estimate. On the {R['validation']['n']} recorded voyages its median is {R['validation']['median_ratio']:.2f} times the reported time (model A {R['validation_A']['median_ratio']:.2f}).

| City | Road only, on foot | Road and sea, on foot (range) | Road only, courier | Road and sea, courier |
|---|---|---|---|---|
{rows}

## Files

| File | What it is |
|---|---|
| `index.html` | The interactive page (built by `code/06_build_site.py`); loads `data/network.json`, `data/roads_site.json`, `data/places.json` and the lookup grids `data/grid_edge.png`, `data/grid_dist.png`, `data/grid_sea.png`, and reruns the model in the browser from any start. |
| `header.png` | Social card, 1200 x 630. |
| `data/ports.csv` | {R['n_ports']} ports: name, location, source (Pleiades type or record, or Itiner-e junction), nearest sea cell and road junction with distances. |
| `data/travel_from_rome.csv` | Days from Rome to every road junction: roads only and road and sea, on foot, by cart and by courier. |
| `data/major_places.csv` | {R['n_majors']} major ancient places (DARE) on the network: days by road only and with the sea, days saved, ratio. |
| `data/casson_voyages.csv`, `data/casson_validation.csv` | Casson's recorded voyages as used, and the time in models A and B for each. |
| `data/casson_table1_validation.csv` | Casson's Table 1 estimated passages, with the time in models A and B and whether each is inside or near his range. |
| `data/roads.geojson.gz`, `data/nodes.csv` | The Itiner-e sections (simplified, gzipped GeoJSON; uncompressed in the Zenodo zip) and junctions, as in the roads study. |
| `data/results.json` | Every number used in the page, paper, blog and collage. |
| `code/` | Scripts, run in order (below), and the page, paper and blog templates. |
| `release/` | Paper PDF and LaTeX source, blog figures and post, Zenodo files. |
| `reddit/` | Collage (`collage.py`, PNG) and post text. |

## Method in brief

- Roads: exactly as in the roads study (Itiner-e; {MODES['foot']['kmd']} km a day on foot, {MODES['cart']['kmd']:.0f} by cart, {MODES['courier']['kmd']:.0f} by courier, from Wikipedia's 'Roman roads'; slowed by the passability field; four straits at one day each).
- Ports: Pleiades places typed port, harbour or anchorage, plus the harbours of the voyage reports; kept within 25 km of the sea grid and 15 km of a road.
- Sea: {R['cell_km']:.0f} km cells (Natural Earth land as obstacle), 16 neighbours, Bosporus, Dardanelles, Kerch and Messina joined by hand. Red Sea and rivers left out (no checkable speeds).
- Speed: in the Aegean (wind from the north) and the central and eastern Mediterranean south of 38.6 N and east of 15.5 E (wind from the north-west; split at 28 E into central and Levant basins), v_up + (v_down - v_up) x ((1 + cos a) / 2)^2; elsewhere v_neu. Model B (headlined), calibrated to Casson's Table 1 by minimising the squared log error: Casson's favourable median and the middle of his two medians scaled by {P['mult']:.3f}, so v_down = {P['v_down']:.2f} and v_neu = {P['v_neu']:.2f} knots, with v_up = {P['v_up']:.2f} knots (central) and {P['v_up_e']:.2f} (Aegean and Levant), all within Casson's stated ranges. Model A (sensitivity): v_down = {P['A']['v_down']:.2f}, v_neu = {P['A']['v_neu']:.2f} and a single v_up = {P['A']['v_up']:.3f} knots, fitted so that Alexandria to Rome takes 63 days. One day to board a ship.
- Why B: it fits Casson's Table 1 far better and matches the outward voyages that journeys from Rome mostly involve; its weakness, the long voyage home from the east, matters least for travel from Rome. Model A's time for each city is in `data/results.json` (`modelA_foot`) and in the sensitivity ranges.
- Seasons: summer (etesians, about mid-May to mid-September) with the sea; winter (mare clausum, November to March) roads only.
- Sensitivity (on model B): both sailing speeds over the range implied by Casson's favourable interquartile range, the speeds into the wind from half to one and a half times, port wait 0.5 to 3 days, and model A.
- Caveats: one summer wind pattern, no calms, storms, currents or night stops; the voyage record is small and biased to fast passages; model B makes the long voyages home from the east about twice as quick as Casson estimates. Times are modelled, not recorded.

## How to rerun

Needs Python 3 with numpy, pandas, geopandas, shapely, pyproj, scipy, rasterio, matplotlib, fontTools and Pillow; xelatex and pdfinfo; Playwright with Chromium for the QA step. Raw inputs are read in place (paths in `code/common.py`): Itiner-e static version 2024 (`itinere_roads.gpkg`, https://doi.org/{ITINERE_DOI}), the Pleiades GIS tables (clone of https://github.com/isawnyu/pleiades.datasets, `data/gis/`), DARE (clone of https://github.com/klokantech/roman-empire), Casson's voyage tables (`casson1951_transcription.md`), saved English Wikipedia pages, and Natural Earth. Intermediate files go to `/home/claude/work/roman-travel-times` (set `ROMAN_WORK` to change).

```
python3 code/01_network.py      # roads and junctions
python3 code/02_sea.py          # Casson's speeds, sea grid, wind basins, ports
python3 code/03_travel.py       # the model, fits, sensitivity, validation
python3 code/04_pagedata.py     # page data and lookup grids
python3 code/05_results.py      # results.json
python3 code/06_build_site.py   # index.html
python3 code/07_figures.py      # header, blog and paper figures
python3 code/08_paper.py        # paper PDF
python3 code/09_readme.py       # README and LICENSE
python3 code/10_release.py      # blog post, Zenodo files, Reddit post
python3 reddit/collage.py       # collage
python3 code/11_qa.py           # screenshots and checks
```

## Sources and licences

- de Soto, P., Pažout, A., Brughmans, T. et al. (2025) Itiner-e static version 2024. Zenodo, https://doi.org/{ITINERE_DOI}; Scientific Data, https://doi.org/{ITINERE_PAPER_DOI}. CC BY 4.0.
- Pleiades: a gazetteer of past places, https://pleiades.stoa.org/ (GIS tables from https://github.com/isawnyu/pleiades.datasets). CC BY 3.0.
- Digital Atlas of the Roman Empire (DARE), Johan Åhlfeldt, via https://github.com/klokantech/roman-empire. CC BY.
- Casson, L. (1951) Speed under sail of ancient ships. Transactions and Proceedings of the American Philological Association 82, 136-148. Online edition: https://penelope.uchicago.edu/Thayer/E/Journals/TAPA/82/Speed_under_Sail_of_Ancient_Ships*.html
- English Wikipedia: 'Etesian', 'Mare clausum', 'Cura Annonae', 'Roman roads'. CC BY-SA 4.0.
- Natural Earth (public domain). Base map tiles on the page: © Esri.
- ORBIS (Scheidel and Meeks, orbis.stanford.edu) is mentioned for comparison only; none of its data is used.

## Citation

Hotham, T. (2026) By road and by sea: fastest travel times from Rome in the Roman Empire, with Itiner-e roads, Pleiades ports and Casson's sailing speeds. Zenodo. https://doi.org/{{10.5281/zenodo.23863542}}

Dr Tristan Hotham, Independent researcher. ORCID 0000-0003-4931-9349.

{AI}
"""
visible_text_ok(readme.replace("|---|---|---|---|---|", "").replace("|---|---|", ""), "readme")
open(os.path.join(ROOT, "README.md"), "w", encoding="utf-8").write(readme)
lic = open("/home/claude/studies/submarine-cables/LICENSE", encoding="utf-8").read().split("This MIT licence covers")[0]
lic += """This MIT licence covers the code in code/ and reddit/collage.py and the page
scripts only.

The data in data/, the figures (header.png, release/blog/, release/paper/,
reddit/), the collage and the text of the page, paper and blog post are shared
under Creative Commons Attribution 4.0 (CC BY 4.0,
https://creativecommons.org/licenses/by/4.0/). They are derived from Itiner-e
static version 2024 (de Soto, Pazout, Brughmans et al. 2025,
https://doi.org/10.5281/zenodo.17122148, CC BY 4.0), the Pleiades gazetteer
(CC BY 3.0) and the Digital Atlas of the Roman Empire (DARE, Johan Ahlfeldt, CC BY):
please credit them. Sailing speeds are from Casson (1951); land from Natural
Earth (public domain).
"""
open(os.path.join(ROOT, "LICENSE"), "w", encoding="utf-8").write(lic)
print("README and LICENSE written")
