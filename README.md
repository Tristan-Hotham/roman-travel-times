# By road and by sea

The fastest way from Rome to anywhere in the Roman Empire, by road and by sea. A follow-up to [Roads of the Roman Empire](https://maps.tristanhotham.com/roman-roads/): the same Itiner-e road network (299,171 km), plus 211 ancient ports and a 15 km sea grid, with sailing speeds from Casson's (1951) ancient voyage reports and the summer etesian winds. Winter (the closed sea) is roads only.

Interactive page: https://maps.tristanhotham.com/roman-travel-times/
Paper: https://doi.org/10.5281/zenodo.23863542
Blog post: https://blog.tristanhotham.com/2026/10/31/roman-travel-times/

## Headline results

- Carthage: 210 days on foot from Rome by road, 5.8 days with a ship in summer (36 times quicker).
- Alexandria 180 to 12 days; London 81 to 30; Constantinople 75 to 17 (upwind in the Aegean; 36 with the slower model A; for a courier 22 against 16).
- Share of the provinces' land within 7, 14 and 30 days of Rome on foot: 0.5%, 1.4% and 3.9% by road alone; 1.2%, 10.8% and 59% with the sea in summer.
- The sea brings the ports of Africa closest: Carthage 37 times, Hadrumetum and Hippo Regius about 30 times. 54 of 919 major places, all in central Italy, gain nothing.
- Validation against Casson's Table 1 (57 estimated passages between named ports). Model B (calibrated, headlined): 14 inside his range (25%), 36 within a quarter of it (63%), median ratio 1.01. Model A (Casson's medians, speed into the wind fitted to Alexandria to Rome in 63 days): 12 inside (21%), 25 near (44%), median ratio 1.38.
- Model B sails Ostia to Alexandria in 11.0 days (Casson: 10 to 13) but back in 30 (Casson: 53 to 73): on the 4 long voyages home from the east it takes 0.46 times his estimate. On the 34 recorded voyages its median is 1.01 times the reported time (model A 1.49).

| City | Road only, on foot | Road and sea, on foot (range) | Road only, courier | Road and sea, courier |
|---|---|---|---|---|
| London | 81 | 29.9 (28 to 35) | 23 | 20.3 |
| Constantinople (Istanbul) | 75 | 17.3 (15 to 36) | 22 | 16.4 |
| Alexandria | 180 | 12.2 (11 to 14) | 51 | 11.3 |
| Carthage | 210 | 5.8 (5 to 8) | 60 | 4.9 |
| Antioch (Antakya) | 128 | 16.8 (16 to 19) | 37 | 15.0 |
| Jerusalem | 157 | 17.3 (16 to 20) | 45 | 14.3 |
| Cádiz | 116 | 13.3 (12 to 16) | 33 | 12.5 |
| Marseille | 45 | 6.2 (6 to 8) | 13 | 5.3 |
| Leptis Magna | 231 | 8.6 (8 to 11) | 66 | 7.8 |
| Athens | 67 | 11.5 (11 to 18) | 20 | 10.4 |
| York | 94 | 40.4 (39 to 45) | 27 | 24.1 |
| Paris | 67 | 37.0 (35 to 41) | 19 | 15.2 |

## Files

| File | What it is |
|---|---|
| `index.html` | The interactive page (built by `code/06_build_site.py`); loads `data/network.json`, `data/roads_site.json`, `data/places.json` and the lookup grids `data/grid_edge.png`, `data/grid_dist.png`, `data/grid_sea.png`, and reruns the model in the browser from any start. |
| `header.png` | Social card, 1200 x 630. |
| `data/ports.csv` | 211 ports: name, location, source (Pleiades type or record, or Itiner-e junction), nearest sea cell and road junction with distances. |
| `data/travel_from_rome.csv` | Days from Rome to every road junction: roads only and road and sea, on foot, by cart and by courier. |
| `data/major_places.csv` | 919 major ancient places (DARE) on the network: days by road only and with the sea, days saved, ratio. |
| `data/casson_voyages.csv`, `data/casson_validation.csv` | Casson's recorded voyages as used, and the time in models A and B for each. |
| `data/casson_table1_validation.csv` | Casson's Table 1 estimated passages, with the time in models A and B and whether each is inside or near his range. |
| `data/roads.geojson.gz`, `data/nodes.csv` | The Itiner-e sections (simplified, gzipped GeoJSON; uncompressed in the Zenodo zip) and junctions, as in the roads study. |
| `data/results.json` | Every number used in the page, paper, blog and collage. |
| `code/` | Scripts, run in order (below), and the page, paper and blog templates. |
| `release/` | Paper PDF and LaTeX source, blog figures and post, Zenodo files. |
| `reddit/` | Collage (`collage.py`, PNG) and post text. |

## Method in brief

- Roads: exactly as in the roads study (Itiner-e; 22.5 km a day on foot, 45 by cart, 80 by courier, from Wikipedia's 'Roman roads'; slowed by the passability field; four straits at one day each).
- Ports: Pleiades places typed port, harbour or anchorage, plus the harbours of the voyage reports; kept within 25 km of the sea grid and 15 km of a road.
- Sea: 15 km cells (Natural Earth land as obstacle), 16 neighbours, Bosporus, Dardanelles, Kerch and Messina joined by hand. Red Sea and rivers left out (no checkable speeds).
- Speed: in the Aegean (wind from the north) and the central and eastern Mediterranean south of 38.6 N and east of 15.5 E (wind from the north-west; split at 28 E into central and Levant basins), v_up + (v_down - v_up) x ((1 + cos a) / 2)^2; elsewhere v_neu. Model B (headlined), calibrated to Casson's Table 1 by minimising the squared log error: Casson's favourable median and the middle of his two medians scaled by 1.105, so v_down = 5.19 and v_neu = 3.70 knots, with v_up = 1.00 knots (central) and 1.60 (Aegean and Levant), all within Casson's stated ranges. Model A (sensitivity): v_down = 4.70, v_neu = 3.35 and a single v_up = 0.374 knots, fitted so that Alexandria to Rome takes 63 days. One day to board a ship.
- Why B: it fits Casson's Table 1 far better and matches the outward voyages that journeys from Rome mostly involve; its weakness, the long voyage home from the east, matters least for travel from Rome. Model A's time for each city is in `data/results.json` (`modelA_foot`) and in the sensitivity ranges.
- Seasons: summer (etesians, about mid-May to mid-September) with the sea; winter (mare clausum, November to March) roads only.
- Sensitivity (on model B): both sailing speeds over the range implied by Casson's favourable interquartile range, the speeds into the wind from half to one and a half times, port wait 0.5 to 3 days, and model A.
- Caveats: one summer wind pattern, no calms, storms, currents or night stops; the voyage record is small and biased to fast passages; model B makes the long voyages home from the east about twice as quick as Casson estimates. Times are modelled, not recorded.

## How to rerun

Needs Python 3 with numpy, pandas, geopandas, shapely, pyproj, scipy, rasterio, matplotlib, fontTools and Pillow; xelatex and pdfinfo; Playwright with Chromium for the QA step. Raw inputs are read in place (paths in `code/common.py`): Itiner-e static version 2024 (`itinere_roads.gpkg`, https://doi.org/10.5281/zenodo.17122148), the Pleiades GIS tables (clone of https://github.com/isawnyu/pleiades.datasets, `data/gis/`), DARE (clone of https://github.com/klokantech/roman-empire), Casson's voyage tables (`casson1951_transcription.md`), saved English Wikipedia pages, and Natural Earth. Intermediate files go to `/home/claude/work/roman-travel-times` (set `ROMAN_WORK` to change).

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

- de Soto, P., Pažout, A., Brughmans, T. et al. (2025) Itiner-e static version 2024. Zenodo, https://doi.org/10.5281/zenodo.17122148; Scientific Data, https://doi.org/10.1038/s41597-025-06140-z. CC BY 4.0.
- Pleiades: a gazetteer of past places, https://pleiades.stoa.org/ (GIS tables from https://github.com/isawnyu/pleiades.datasets). CC BY 3.0.
- Digital Atlas of the Roman Empire (DARE), Johan Åhlfeldt, via https://github.com/klokantech/roman-empire. CC BY.
- Casson, L. (1951) Speed under sail of ancient ships. Transactions and Proceedings of the American Philological Association 82, 136-148. Online edition: https://penelope.uchicago.edu/Thayer/E/Journals/TAPA/82/Speed_under_Sail_of_Ancient_Ships*.html
- English Wikipedia: 'Etesian', 'Mare clausum', 'Cura Annonae', 'Roman roads'. CC BY-SA 4.0.
- Natural Earth (public domain). Base map tiles on the page: © Esri.
- ORBIS (Scheidel and Meeks, orbis.stanford.edu) is mentioned for comparison only; none of its data is used.

## Citation

Hotham, T. (2026) By road and by sea: fastest travel times from Rome in the Roman Empire, with Itiner-e roads, Pleiades ports and Casson's sailing speeds. Zenodo. https://doi.org/10.5281/zenodo.23863542

Dr Tristan Hotham, Independent researcher. ORCID 0000-0003-4931-9349.

I wrote the text, with drafting and editing assistance from Claude (Anthropic), which also helped prepare the analysis code. I reviewed and checked all text and results.
