"""Step 5. data/results.json: every number quoted in the page, paper, blog, collage and post, with the facts stated in words
checked by asserts. Also the share of the empire's land (DARE provinces of about AD 117) within 7, 14 and 30 days.
Run: python3 code/05_results.py
"""
import os, sys, re, pickle, html as _html
import numpy as np, pandas as pd, geopandas as gpd
from scipy.spatial import cKDTree
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
from figlib import proj, INV

N = pickle.load(open(f"{WORK}/net.pkl", "rb")); SEA = pickle.load(open(f"{WORK}/sea.pkl", "rb")); TR = pickle.load(open(f"{WORK}/travel.pkl", "rb"))
SM = pickle.load(open(f"{WORK}/samples.pkl", "rb"))
S, nodes = N["S"], N["nodes"]; RS = TR["res"]; PAR = TR["PAR"]; CAS = SEA["CAS"]; PT = SEA["ports"]; T = TR["T"]
R = {"meta": {"itinere_doi": ITINERE_DOI, "itinere_paper_doi": ITINERE_PAPER_DOI, "page": PAGE_URL, "repo": REPO, "roads_page": ROADS_PAGE,
              "roads_doi": ROADS_DOI, "roads_blog": ROADS_BLOG, "year": 2026}}


def wtext(name):
    d = jload(f"{TRAVEL}/wiki_{name}.json")
    return d["revid"], re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", "", re.sub(r"<style.*?</style>", "", d["html"], flags=re.S))).replace("\xa0", " "))


# ---------- quotes the text relies on (checked against the saved pages) ----------
QUOTES = {"Etesian": ["are the strong, dry north winds of the Aegean Sea, which blow periodically from about mid-May to mid-September",
                      "in the southern Aegean, the Cretan and the Carpathian sea, they blow as northwesterlies"],
          "Mare_clausum": ["the period between November and March was considered the most dangerous for navigation"],
          "Cura_Annonae": ["Sailing time one-way from Sicily to Rome's port of Ostia Antica was about four days", "From Carthage sailing time was about nine days",
                           "would first steer north east to Cyprus, then follow the south coast of Asia Minor"],
          "Roman_roads": ["pedestrians traveled 20 to 25 kilometres", "a relay of horses could carry a letter 80 kilometres"]}
R["wiki"] = {}
for nm, qs in QUOTES.items():
    rv, t = wtext(nm)
    for q in qs:
        assert q in t, (nm, q)
    R["wiki"][nm] = rv

# ---------- parameters ----------
R["casson"] = CAS
R["params"] = {k_: (float(v) if isinstance(v, (int, float, np.floating)) else v) for k_, v in PAR.items()}
for k_ in ("v_down", "v_neu", "v_up", "v_up_e"):
    R["params"][k_ + "_kmd"] = PAR[k_] * PAR["kt_kmd"]
R["table1_A"] = PAR["table1_A"]; R["table1_B"] = PAR["table1_B"]; R["validation_A"] = RS["validation_A"]
R["table1_rows"] = RS["table1_rows"]
R["modes"] = {k_: {"label": v["label"], "kmd": v["kmd"]} for k_, v in MODES.items()}
R["sens_params"] = RS["sens_params"]
R["n_ports"] = len(PT); R["n_ports_typed"] = int(PT.source.str.startswith("Pleiades port").sum()); R["n_ports_extra"] = R["n_ports"] - R["n_ports_typed"]
R["n_sea_cells"] = len(SEA["C_lon"]); R["cell_km"] = SEA["grid"]["cell"] / 1000
R["n_cells_basin"] = {str(b): int((SEA["basin"] == b).sum()) for b in (0, 1, 2)}
R["n_straits"] = len(SEA["STRAITS"])
R["km_total"] = RS["km_total"]; R["n_sections"] = len(S); R["n_nodes"] = len(nodes)

# ---------- cities ----------
R["city"] = {}
for key_, c in RS["city"].items():
    r = {k_: v for k_, v in c.items() if k_ not in ("route", "route_courier")}
    r["ports_from"] = c["route"]["ports_from"]; r["ports_to"] = c["route"]["ports_to"]; r["sea_days"] = c["route"]["sea_days"]; r["road_days"] = c["route"]["road_days"]
    r["boardings"] = c["route"]["boardings"]
    r["saved"] = c["winter_foot"] - c["summer_foot"]; r["ratio"] = c["winter_foot"] / c["summer_foot"] if c["summer_foot"] > 0 else None
    r["saved_courier"] = c["winter_courier"] - c["summer_courier"]
    R["city"][key_] = r
R["compare"] = COMPARE
car, alx, lon_, con = (R["city"][k_] for k_ in ("carthago", "alexandria", "london", "constantinople"))
R["carthage_ratio"] = car["ratio"]

# ---------- shares of the network and of the land within 7, 14, 30 days ----------
R["share_within"] = RS["share_within"]; R["km_within"] = RS["km_within"]
P = gpd.read_file(f"{DARE}/provinces.geojson").set_crs(4326, allow_override=True)
prov = P.to_crs("+proj=laea +lat_0=40 +lon_0=16 +datum=WGS84 +units=m").unary_union
from figlib import empire_extent
import rasterio.features, rasterio.transform
x0, x1, y0, y1 = empire_extent(); res_m = 5000
nx_, ny_ = int((x1 - x0) / res_m), int((y1 - y0) / res_m)
inprov = rasterio.features.rasterize([(prov, 1)], out_shape=(ny_, nx_), transform=rasterio.transform.from_bounds(x0, y0, x1, y1, nx_, ny_), fill=0).astype(bool)
GX, GY = np.meshgrid(x0 + (np.arange(nx_) + .5) * res_m, y1 - (np.arange(ny_) + .5) * res_m)
glon, glat = INV.transform(GX[inprov], GY[inprov])
se, sf, sx, sy = SM["samples"]
P3 = lambda lo, la: np.column_stack([np.cos(np.radians(la)) * np.cos(np.radians(lo)), np.cos(np.radians(la)) * np.sin(np.radians(lo)), np.sin(np.radians(la))])
chord, idx = cKDTree(P3(sx, sy)).query(P3(glon, glat)); dkm = 2 * 6371.0088 * np.arcsin(np.clip(chord / 2, 0, 1))
area_share = {}
for key in (("winter", "foot"), ("summer", "foot"), ("winter", "courier"), ("summer", "courier")):
    kmd = MODES[key[1]]["kmd"]; t = T[key]; e = se[idx]; f = sf[idx]; w = S.km.values[e] / (kmd * S.pas.values[e])
    tt = np.minimum(t[S.u.values[e]] + f * w, t[S.v.values[e]] + (1 - f) * w) + dkm / (kmd * OFFROAD_FACTOR)
    tt = np.where(dkm <= OFFROAD_MAX_KM, tt, np.inf)
    area_share[f"{key[0]}_{key[1]}"] = {str(d): float((tt <= d).mean()) for d in (7, 14, 30, 60)}
R["area_share"] = area_share; R["area_km2"] = float(inprov.sum() * 25)
# ---------- places sea travel brings closest ----------
R["closest_saved"] = RS["closest_saved"]; R["closest_ratio"] = RS["closest_ratio"]; R["n_majors"] = RS["n_majors"]
R["majors_faster_by_sea"] = RS["majors_faster_by_sea"]; R["majors_median_road"] = RS["majors_median_road"]; R["majors_median_sea"] = RS["majors_median_sea"]
R["share_majors_faster"] = R["majors_faster_by_sea"] / R["n_majors"]
MJ = TR["MJ"]; R["majors_no_gain"] = int((MJ.saved <= 0.5).sum()); R["majors_no_gain_max_road"] = float(MJ[MJ.saved <= 0.5].road.max())
assert R["closest_saved"][0]["saved"] > 200 and "Lepcis Magna" in [r["name"] for r in R["closest_saved"][:6]] and "Berenice" in [r["name"] for r in R["closest_saved"][:8]]
# ---------- validation ----------
R["validation"] = RS["validation"]
VAL = TR["VAL"]
R["val_rows"] = VAL.round(2).to_dict("records")
R["sens"] = RS["sens"]

# ---------- facts stated in words ----------
assert car["winter_foot"] > 200 and car["summer_foot"] < 8 and car["ratio"] > 25
assert alx["winter_foot"] > 170 and alx["summer_foot"] < 15 and alx["ports_to"] == ["Alexandria"]
assert 10 <= PAR["ostia_alex_days"] <= 13 and PAR["alex_ostia_days"] < 53 and abs(PAR["A"]["alex_ostia_days"] - 63) < .5
assert all(3 <= PAR[k_] <= 6 for k_ in ("v_down", "v_neu")) and 4 <= PAR["v_down"] <= 6 and 3 <= PAR["v_neu"] <= 4 and max(PAR["v_up"], PAR["v_up_e"]) <= 2.5
assert R["table1_B"]["near"] > R["table1_A"]["near"] and abs(np.log(R["table1_B"]["median_ratio"])) < abs(np.log(R["table1_A"]["median_ratio"]))
assert con["summer_foot"] < con["winter_foot"] and con["modelA_foot"] > 2 * con["summer_foot"]
assert lon_["summer_foot"] < lon_["winter_foot"] / 2
assert 0.8 < R["validation"]["median_ratio"] < 1.25 and R["validation_A"]["median_ratio_fav"] > 1.25
for k_ in COMPARE:
    assert R["city"][k_]["summer_foot"] <= R["city"][k_]["winter_foot"] + 1e-9, k_
assert R["closest_ratio"][0]["name"] == "Carthago" and {"Hadrumetum", "Hippo Regius"} <= {r["name"] for r in R["closest_ratio"][:4]}
assert R["closest_ratio"][3]["ratio"] < R["closest_ratio"][1]["ratio"]
assert con["ports_to"] == ["Byzantium"]
R["n_compare_faster"] = sum(1 for k_ in COMPARE if R["city"][k_]["saved"] > 0.5)
# Table 1: the long westward voyages home (from the east to Italy or Gaul), where model B is too quick
WEST = {("Alexandria", "Rome"), ("Alexandria", "Naples"), ("Alexandria", "Massilia"), ("Rhodes", "Rome")}
rws = [r for r in R["table1_rows"] if (r["from"], r["to"]) in WEST]
R["table1_returns"] = {"n": len(rws), "median_ratio_B": float(np.median([r["model_days"] / ((r["lo"] + r["hi"]) / 2) for r in rws])),
                       "median_ratio_A": float(np.median([r["modelA_days"] / ((r["lo"] + r["hi"]) / 2) for r in rws])),
                       "n_inside_A": int(sum(r["lo"] <= r["modelA_days"] <= r["hi"] for r in rws))}
oth = [r for r in R["table1_rows"] if (r["from"], r["to"]) not in WEST]
R["table1_B_other"] = {"n": len(oth), "near": float(np.mean([r["near"] for r in oth])), "inside": float(np.mean([r["inside"] for r in oth]))}
R["table1_A_rows_near"] = int(sum(r["modelA_days"] >= r["lo"] / 1.25 and r["modelA_days"] <= r["hi"] * 1.25 for r in R["table1_rows"]))
assert R["table1_A_rows_near"] == R["table1_A"]["n_near"]
assert len(rws) == 4 and R["table1_returns"]["median_ratio_B"] < .6 and R["table1_returns"]["n_inside_A"] >= 2
R["headline_model"] = "B (calibrated to Casson's Table 1)"
jsave(R, f"{DATA}/results.json", indent=1)
for k_ in COMPARE:
    c = R["city"][k_]; print(f"{c['name']:24s} road {c['winter_foot']:6.1f} sea {c['summer_foot']:5.1f} ({c['summer_foot_min']:.0f} to {c['summer_foot_max']:.0f})  courier {c['winter_courier']:5.1f}/{c['summer_courier']:5.1f}")
print("area share", area_share); print("road share", {k_: R["share_within"][k_] for k_ in ("winter_foot", "summer_foot")})
print("closest by days saved", [(r["name"], round(r["saved"])) for r in R["closest_saved"][:8]])
print("by ratio", [(r["name"], round(r["ratio"], 1)) for r in R["closest_ratio"][:8]])
