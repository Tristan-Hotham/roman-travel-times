"""Shared paths, assumptions and helpers for the roman-travel-times study ("By road and by sea"), which extends the
roman-roads study (https://maps.tristanhotham.com/roman-roads/) with sea routes.

Raw inputs (read in place, never copied into the repo):
  ROMAN    /home/claude/newdata/raw8/roman/
             itinere_roads.gpkg                     Itiner-e static version 2024 (de Soto, Pazout, Brughmans et al. 2025),
                                                    Zenodo 10.5281/zenodo.17122148, CC BY 4.0. 14,769 road sections,
                                                    EPSG:3395, fields described in the .docx below.
             itinere_data_field_description.docx    the dataset's field description
             itinere_zenodo_record.json             the Zenodo record (creators, version, files)
             wiki_Roman_roads.json                  English Wikipedia 'Roman roads' (travel speeds quoted from it)
  DARE     /home/claude/work/roman-roads/ext/roman-empire/data/  (git clone of github.com/klokantech/roman-empire, which
             packages the Digital Atlas of the Roman Empire, DARE, by Johan Ahlfeldt): provinces.geojson (provinces of
             about AD 117 and the regions of Italy) and places_high.geojson (ancient places with Latin names).
  PLEIADES /home/claude/work/roman-roads/ext/pleiades.datasets/data/gis/  (sparse clone of github.com/isawnyu/pleiades.datasets,
             CC BY 3.0): places.csv and places_place_types.csv, for ports, harbours and anchorages.
  TRAVEL   /home/claude/newdata/raw11/roman_travel/
             casson1951_transcription.md   Casson (1951) "Speed under sail of ancient ships", TAPA 82: 136-148, voyage tables
                                           checked against the LacusCurtius online edition, with his Table 1 of estimated times
             wiki_*.json                   English Wikipedia pages (Etesian, Mare clausum, ...), CC BY-SA 4.0
  GEO      /home/claude/newdata/raw/geo/  Natural Earth 50m land and 10m countries (public domain).
Intermediates are written to WORK (outside the repo)."""
import json, os, re, math

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROMAN = os.environ.get("ROMAN_RAW", "/home/claude/newdata/raw8/roman")
DARE = os.environ.get("ROMAN_DARE", "/home/claude/work/roman-roads/ext/roman-empire/data")
GEO = os.environ.get("ROMAN_GEO", "/home/claude/newdata/raw/geo")
PLEIADES = os.environ.get("ROMAN_PLEIADES", "/home/claude/work/roman-roads/ext/pleiades.datasets/data/gis")
TRAVEL = os.environ.get("ROMAN_TRAVEL", "/home/claude/newdata/raw11/roman_travel")
FONTS = os.environ.get("FONT_DIR", "/home/claude/ref/fonts")
DATA = os.path.join(ROOT, "data")
WORK = os.environ.get("ROMAN_WORK", "/home/claude/work/roman-travel-times")
for d in (DATA, WORK):
    os.makedirs(d, exist_ok=True)

SLUG = "roman-travel-times"
PAGE_URL = "https://maps.tristanhotham.com/roman-travel-times/"
REPO = "https://github.com/Tristan-Hotham/roman-travel-times"
ROADS_PAGE = "https://maps.tristanhotham.com/roman-roads/"
ROADS_DOI = "10.5281/zenodo.23857866"
ROADS_BLOG = "https://blog.tristanhotham.com/2026/10/31/roman-roads/"
ITINERE_DOI = "10.5281/zenodo.17122148"
ITINERE_PAPER_DOI = "10.1038/s41597-025-06140-z"
AI = ("I wrote the text, with drafting and editing assistance from Claude (Anthropic), which also helped "
      "prepare the analysis code. I reviewed and checked all text and results.")
CREDIT = "Itiner-e static version 2024 (de Soto, Pažout, Brughmans et al. 2025), CC BY 4.0"

# ---------- travel assumptions (all stated on the page, in the paper and the blog) ----------
# English Wikipedia, 'Roman roads': "Horse-drawn carts could travel up to 40 to 50 kilometres per day, while pedestrians
# traveled 20 to 25 kilometres per day" and "On average a relay of horses could carry a letter 80 kilometres in a day".
# I use the middle of each range; the low and high ends give the ranges quoted for the three cities.
MODES = {"foot": {"label": "On foot", "kmd": 22.5, "lo": 20, "hi": 25},
         "cart": {"label": "Horse-drawn cart", "kmd": 45.0, "lo": 40, "hi": 50},
         "courier": {"label": "Courier (relay of horses)", "kmd": 80.0, "lo": 80, "hi": 80}}
MODE_ORDER = ["foot", "cart", "courier"]
OFFROAD_FACTOR = 0.5      # off the mapped network, the last stretch is counted at half the road speed
OFFROAD_MAX_KM = 50       # beyond this distance from any mapped road the map shows no time
CROSSING_DAYS = 1.0       # each short sea crossing counts as one day, whatever the mode
# Short sea crossings that join the road network across straits (snapped to the best-connected node within 3 km of each
# point). The Bosporus and Hellespont ferries are already in Itiner-e as road sections ('Byzantium ferry', 'Abydos ferry').
CROSSINGS = [("channel", "English Channel", "Gesoriacum (Boulogne)", (1.607, 50.727), "Dubris (Dover)", (1.312, 51.126)),
             ("messina", "Strait of Messina", "Rhegium", (15.646, 38.110), "Messana", (15.554, 38.193)),
             ("otranto", "Strait of Otranto", "Brundisium", (17.943, 40.639), "Dyrrachium", (19.447, 41.313)),
             ("gibraltar", "Strait of Gibraltar", "Baelo Claudia", (-5.774, 36.090), "Tingi", (-5.807, 35.777)),
             ("euripus", "Euripus (bridge)", "Aulis", (23.590, 38.430), "Chalcis", (23.596, 38.464))]
BRIDGES = {"euripus"}     # the Euripus was bridged: counted as road, not as a day's crossing

ROME = (12.4853, 41.8925)  # the Forum (golden milestone)
# Destinations reported in the text, and the start cities offered on the page (lon, lat of the ancient city centre).
CITIES = [("rome", "Roma", "Rome", (12.4853, 41.8925)),
          ("london", "Londinium", "London", (-0.0915, 51.5125)),
          ("constantinople", "Byzantium", "Constantinople (Istanbul)", (28.977, 41.008)),
          ("alexandria", "Alexandria", "Alexandria", (29.906, 31.197)),
          ("eboracum", "Eboracum", "York", (-1.0817, 53.9620)),
          ("lutetia", "Lutetia", "Paris", (2.3470, 48.8530)),
          ("lugdunum", "Lugdunum", "Lyon", (4.8200, 45.7600)),
          ("colonia", "Colonia Agrippina", "Cologne", (6.9580, 50.9380)),
          ("treveri", "Augusta Treverorum", "Trier", (6.6400, 49.7550)),
          ("tarraco", "Tarraco", "Tarragona", (1.2540, 41.1150)),
          ("emerita", "Emerita Augusta", "Mérida", (-6.3440, 38.9160)),
          ("gades", "Gades", "Cádiz", (-6.2920, 36.5300)),
          ("carthago", "Carthago", "Carthage", (10.3230, 36.8530)),
          ("mediolanum", "Mediolanum", "Milan", (9.1890, 45.4640)),
          ("aquileia", "Aquileia", "Aquileia", (13.3700, 45.7700)),
          ("sirmium", "Sirmium", "Sremska Mitrovica", (19.6100, 44.9700)),
          ("athenae", "Athenae", "Athens", (23.7260, 37.9750)),
          ("ephesus", "Ephesus", "Ephesus", (27.3410, 37.9400)),
          ("antiochia", "Antiochia", "Antioch (Antakya)", (36.1600, 36.2020)),
          ("hierosolyma", "Hierosolyma", "Jerusalem", (35.2300, 31.7770)),
          ("lepcis", "Lepcis Magna", "Leptis Magna", (14.2900, 32.6380)),
          ("massilia", "Massilia", "Marseille", (5.3700, 43.2960)),
          ("ostia", "Ostia", "Ostia", (12.2894, 41.7536))]
HEADLINE = ["london", "constantinople", "alexandria", "carthago"]
COMPARE = ["london", "constantinople", "alexandria", "carthago", "antiochia", "hierosolyma", "gades", "massilia", "lepcis", "athenae", "eboracum", "lutetia"]

CERT = [("Certain", "Certain", "#123F7A"), ("Conjectured", "Conjectured", "#DA8A5B"), ("Hypothetical", "Hypothetical", "#A3967E")]
CERT_COL = {k: c for k, _, c in CERT}
TYPES = [("Main Road", "Main road"), ("Secondary Road", "Secondary road")]
# Date bands for the roads that have a start date (Lower_Date; 9999 = not given).
DATEBANDS = [("rep", "Before 27 BCE (Republic)", -9999, -28, "#6A3D9A"),
             ("jc", "27 BCE to 68 CE (Augustus to Nero)", -27, 68, "#1F78B4"),
             ("hi", "69 to 192 CE (Flavians to Antonines)", 69, 192, "#33A02C"),
             ("late", "193 CE and later", 193, 9998, "#E08B00")]
# Days-from-Rome bands (on foot) used in figures and the collage: 0 to 10, 10 to 20, ... days, and 120 and more.
DAYBREAKS = [0, 10, 20, 30, 40, 50, 60, 75, 90, 120]
ITALY_REG = {"I": "Latium et Campania", "II": "Apulia et Calabria", "III": "Lucania et Bruttii", "IV": "Samnium",
             "V": "Picenum", "VI": "Umbria", "VII": "Etruria", "VIII": "Aemilia", "IX": "Liguria",
             "X": "Venetia et Histria", "XI": "Transpadana"}


def dash(v):
    """House style: no em or en dashes, no double hyphens, in anything written to data/."""
    if isinstance(v, str):
        v = re.sub(r"(\d)\s*[–—]\s*(\d)", r"\1 to \2", v)
        v = v.replace(" — ", ", ").replace("—", ", ").replace(" – ", ", ").replace("–", "-")
        while "--" in v:
            v = v.replace("--", "-")
        return v
    if isinstance(v, (list, tuple)):
        return [dash(x) for x in v]
    if isinstance(v, dict):
        return {k: dash(x) for k, x in v.items()}
    return v


def _np(o):
    import numpy as np
    if isinstance(o, np.integer): return int(o)
    if isinstance(o, np.floating): return float(o)
    if isinstance(o, np.bool_): return bool(o)
    if isinstance(o, np.ndarray): return o.tolist()
    raise TypeError(type(o))


def jsave(obj, path, indent=None):
    if os.path.abspath(path).startswith(DATA):
        obj = dash(obj)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=indent, separators=None if indent else (",", ":"), default=_np, allow_nan=path.endswith("travel.json"))


def jload(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get(R, path):
    v = R
    for k in path.split("."):
        v = v[int(k)] if isinstance(v, list) else v[k]
    return v


def fmt(v, f):
    if f is None or f == "raw": return str(v)
    if f == "int": return f"{round(v):,}"
    if f == "k": return f"{round(v / 1000):,}"
    if f == "pct": return f"{round(v * 100)}%"
    if f == "pct1": return f"{v * 100:.1f}%"
    if f == "f1": return f"{v:.1f}"
    if f == "f2": return f"{v:.2f}"
    raise ValueError(f)


def fill(text, R, keep=("DOI", "DOI_URL", "BLOG_URL")):
    """Replace {{path|fmt}} tokens from results.json, leaving the publisher's placeholders and IMG tokens alone."""
    def rep(m):
        k = m.group(1)
        if k in keep or k.startswith("IMG"):
            return m.group(0)
        return fmt(get(R, k), m.group(3))
    return re.sub(r"\{\{([^}|]+)(\|(\w+))?\}\}", rep, text)


def visible_text_ok(s, where=""):
    for bad in ("—", "–", "--", "DSIT", "DCMS", "civil serv", "Civil Serv"):
        assert bad not in s, (where, bad)


def haversine(lon1, lat1, lon2, lat2):
    import numpy as np
    lon1, lat1, lon2, lat2 = map(np.radians, (lon1, lat1, lon2, lat2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371.0088 * np.arcsin(np.sqrt(a))

# Days ramp, shared by the page, the figures and the collage: (days, colour), interpolated linearly in RGB.
RAMP = [(0, "#7A0F2E"), (3, "#B3262E"), (7, "#DB5A26"), (12, "#EE9A2E"), (18, "#C9B634"), (25, "#7FAF4A"),
        (35, "#3C9A6E"), (50, "#22818C"), (75, "#2A5F9E"), (120, "#3B3A8C")]


def ramp_rgb(days):
    """Colour for a number of days (array or scalar), as floats 0 to 1, shape (..., 3)."""
    import numpy as np
    d = np.clip(np.asarray(days, float), 0, RAMP[-1][0])
    xs = np.array([a for a, _ in RAMP], float)
    cs = np.array([[int(c[i:i + 2], 16) / 255 for i in (1, 3, 5)] for _, c in RAMP])
    return np.stack([np.interp(d, xs, cs[:, j]) for j in range(3)], -1)
