"""Step 3. Fastest travel from Rome by road, and by road and sea together.
Graph: the Itiner-e junctions (roads exactly as in the roman-roads study: km / (speed x passability), four short
straits at one day each), the ports, and the sea cells. All times in days.
Sea model (summer, the etesian season, about mid-May to mid-September):
  speed in knots where there is no prevailing wind: V_NEU; in the wind basins V_UP + (V_DOWN - V_UP) x ((1 + cos a) / 2) ^ 2,
  where a is the angle between the ship's heading and the direction the wind blows towards.
  Model A (Casson's medians): V_DOWN = median of his favourable voyages, V_NEU = middle of his favourable and unfavourable
  medians, one V_UP fitted so that Alexandria to Rome takes 63 days (the middle of his Table 1 estimate, 53 to 73).
  Model B (headline, calibrated): V_DOWN and V_NEU scaled by one factor, and V_UP set separately for the central basin and for
  the Aegean and Levant basins, chosen together to fit all 57 of Casson's Table 1 estimates (least squares on log times).
  boarding a ship costs PORT_DAYS (waiting for a ship and a wind); landing costs nothing extra.
  A ship moves from a sea cell to one of its 16 neighbours; speed is set by the basin of the cell it leaves.
Winter (mare clausum, about November to March): roads only, as in roman-roads.
Writes WORK/travel.pkl, data/travel_from_rome.csv, data/network.json and the page lookup grids.
Run: python3 code/03_travel.py
"""
import os, sys, re, pickle
import numpy as np, pandas as pd
import scipy.sparse as sp
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

N = pickle.load(open(f"{WORK}/net.pkl", "rb")); SEA = pickle.load(open(f"{WORK}/sea.pkl", "rb"))
S, nodes, X = N["S"], N["nodes"], N["X"]; CAS = SEA["CAS"]; PT = SEA["ports"]
k = len(nodes); m = len(S); npt = len(PT); nc = len(SEA["C_lon"])
KT = 1.852 * 24                                   # 1 knot in km a day
V_DOWN = CAS["fav_median"]; V_NEU = (CAS["fav_median"] + CAS["unf_median"]) / 2
PORT_DAYS = 1.0
POLAR_P = 2.0     # shape of the speed curve between downwind and upwind (2: speed falls off quickly once the wind is abeam)
DEG = nodes.deg.values


def snap(lon, lat):
    d = haversine(lon, lat, nodes.lon.values, nodes.lat.values); d = np.where(nodes.net.values, d, np.inf)
    near = np.where(d <= 3)[0]
    i = int(near[np.lexsort((d[near], -DEG[near]))[0]]) if len(near) else int(np.argmin(d))
    return i, float(d[i])


ROME_N = snap(*ROME)[0]; assert nodes.name[ROME_N] == "Roma"
CITY_N = {key: snap(*xy)[0] for key, _, _, xy in CITIES}

# ---------- sea edges (geometry fixed; speed set per scenario) ----------
E = SEA["E"]; cl, ca = SEA["C_lon"], SEA["C_lat"]; cell = SEA["grid"]["cell"]
e_km = cell * np.hypot(E[:, 2], E[:, 3]) / 1000
la1, la2 = np.radians(ca[E[:, 0]]), np.radians(ca[E[:, 1]]); dl = np.radians(cl[E[:, 1]] - cl[E[:, 0]])
e_brg = np.degrees(np.arctan2(np.sin(dl) * np.cos(la2), np.cos(la1) * np.sin(la2) - np.sin(la1) * np.cos(la2) * np.cos(dl))) % 360
e_bas = SEA["basin"][E[:, 0]]
ST = SEA["STRAITS"]; st_km = np.array([cell / 1000 * 0 + haversine(cl[a], ca[a], cl[b], ca[b]) for _, a, b in ST])


def sea_knots(v_up, v_down=V_DOWN, v_neu=V_NEU, wind=True, v_up_e=None):
    """Knots on every sea edge. v_up: dead into the wind in the central basin (2); v_up_e: in the Aegean (1) and Levant (3)
    basins (the same as v_up unless given)."""
    if not wind:
        return np.full(len(E), v_neu)
    wt = np.array([SEA["WIND_TO"].get(int(b), 0.0) for b in range(4)])[e_bas]
    vu = np.where(e_bas == 2, v_up, v_up if v_up_e is None else v_up_e)
    f = ((1 + np.cos(np.radians(e_brg - wt))) / 2) ** POLAR_P
    return np.where(e_bas == 0, v_neu, vu + (v_down - vu) * f)


def build(kmd, season="summer", v_up=None, v_down=V_DOWN, v_neu=V_NEU, port_days=PORT_DAYS, wind=True, roads=True, use_pass=True, v_up_e=None):
    U, Vv, W, T_ = [], [], [], []     # T_: edge type 0 road section, 1 crossing, 2 port-road, 3 boarding, 4 landing, 5 sea, 6 strait
    if roads:
        sel = (S.u != S.v).values
        s = S[sel]; w = s.km.values / (kmd * (s.pas.values if use_pass else 1))
        for a, b in ((s.u.values, s.v.values), (s.v.values, s.u.values)):
            U.append(a); Vv.append(b); W.append(w); T_.append(np.zeros(len(w), int))
        cu = np.array([x["u"] for x in X]); cv = np.array([x["v"] for x in X])
        cw = np.array([x["km"] / kmd if x["bridge"] else CROSSING_DAYS for x in X])
        for a, b in ((cu, cv), (cv, cu)):
            U.append(a); Vv.append(b); W.append(cw); T_.append(np.ones(len(cw), int))
    if season == "summer":
        pn = k + np.arange(npt); pc = k + npt + PT.sea_cell.values
        wr = PT.node_km.values / kmd
        U += [PT.node.values, pn]; Vv += [pn, PT.node.values]; W += [wr, wr]; T_ += [np.full(npt, 2), np.full(npt, 2)]
        wsea = PT.sea_km.values / (v_neu * KT)
        U += [pn, pc]; Vv += [pc, pn]; W += [port_days + wsea, wsea]; T_ += [np.full(npt, 3), np.full(npt, 4)]
        kn = sea_knots(v_up, v_down, v_neu, wind, v_up_e)
        U.append(k + npt + E[:, 0]); Vv.append(k + npt + E[:, 1]); W.append(e_km / (kn * KT)); T_.append(np.full(len(E), 5))
        sa = np.array([a for _, a, _ in ST]); sb = np.array([b for _, _, b in ST]); sw = st_km / (v_neu * KT)
        U += [k + npt + sa, k + npt + sb]; Vv += [k + npt + sb, k + npt + sa]; W += [sw, sw]; T_ += [np.full(len(ST), 6)] * 2
    U, Vv, W, T_ = map(np.concatenate, (U, Vv, W, T_))
    nn = k + npt + nc
    key = U.astype(np.int64) * nn + Vv
    o = np.lexsort((W, key)); first = np.r_[True, key[o][1:] != key[o][:-1]]; o = o[first]
    A = sp.csr_matrix((W[o], (U[o], Vv[o])), shape=(nn, nn))
    return A, (U[o], Vv[o], W[o], T_[o])


def run(src, **kw):
    A, ed = build(**kw)
    t, pred = dijkstra(A, directed=True, indices=src, return_predecessors=True)
    return t, pred, ed


ALEX_P = int(PT.index[PT.name == "Alexandria"][0]); OSTIA_P = int(PT.index[PT.name == "Ostia"][0])


def alex_rome(v_up, **kw):
    """Alexandria to Rome in summer, sea only from the Alexandria port to the Ostia port (including the day of waiting)."""
    t, _, _ = run(k + ALEX_P, kmd=MODES["foot"]["kmd"], v_up=v_up, roads=False, **kw)
    return t[k + OSTIA_P]


def fit(target, **kw):
    lo, hi = 0.02, CAS["unf_median"] * 2
    for _ in range(30):
        mid = (lo + hi) / 2
        if alex_rome(mid, **kw) > target: lo = mid
        else: hi = mid
    return (lo + hi) / 2


V_UP = fit(63.0); V_UP_53 = fit(53.0); V_UP_73 = fit(73.0)
print(f"model A: V_DOWN {V_DOWN:.2f} kn, V_NEU {V_NEU:.2f} kn, V_UP fitted {V_UP:.3f} kn (53 days: {V_UP_53:.3f}, 73 days: {V_UP_73:.3f})")
t_ra = run(k + OSTIA_P, kmd=MODES["foot"]["kmd"], v_up=V_UP, roads=False)[0][k + ALEX_P]
PA = {"v_down": V_DOWN, "v_neu": V_NEU, "v_up": V_UP, "v_up_e": V_UP, "v_up_53": V_UP_53, "v_up_73": V_UP_73,
      "ostia_alex_days": float(t_ra), "alex_ostia_days": float(alex_rome(V_UP))}

# ---------- Casson's Table 1: estimated sailing times between ports ----------
from scipy.spatial import cKDTree
from scipy.optimize import minimize
from figlib import proj
t1txt = open(f"{TRAVEL}/casson1951_transcription.md", encoding="utf-8").read().split("Full Table 1")[1].split("Note 34")[0]
T1 = []
for ln in t1txt.splitlines():
    p_ = [x.strip() for x in ln.split("|")]
    if len(p_) == 3 and re.search(r"\d", p_[2]) and p_[0] != "From":
        v_ = [float(x) for x in re.findall(r"[\d.]+", p_[2])]
        T1.append({"from": p_[0], "to": re.sub(r"\s*\(.*", "", p_[1]), "to_text": p_[1], "lo": min(v_), "hi": max(v_)})
T1 = pd.DataFrame(T1); assert len(T1) == 57, len(T1)
LOC = {"Ostia": (12.2894, 41.7536), "Rome": (12.2894, 41.7536), "Africa (Cape Hermaeum)": (11.04, 37.08), "Messina": (15.557, 38.192),
       "Gibraltar": (-5.35, 36.13), "Tarraco": (1.254, 41.115), "Narbo": (3.004, 43.184), "Puteoli": (14.122, 40.826), "Naples": (14.25, 40.84),
       "Alexandria": (29.91, 31.20), "Egypt": (29.91, 31.20), "Corinth": (22.879, 37.931), "Rhegium": (15.644, 38.109), "Carthage": (10.323, 36.853),
       "Rhodes": (28.228, 36.443), "Ephesus": (27.341, 37.940), "Utica": (10.06, 37.056), "Epidamnus": (19.447, 41.316), "Byzantium": (28.977, 41.008),
       "Gaza": (34.452, 31.520), "Thessalonica": (22.953, 40.628), "Ascalon": (34.551, 31.665), "Massilia": (5.382, 43.297), "Caesarea": (34.892, 32.502),
       "Cyprus": (32.41, 34.76), "Sidon": (35.373, 33.562), "Chelidonian Isles": (30.42, 36.42), "Cyrene": (21.97, 32.905), "West Point of Crete": (23.55, 35.35),
       "Crete": (24.02, 35.52), "Syrtes": (19.5, 31.4), "Phycus": (21.55, 32.95), "Cimmerian Bosporus": (36.469, 45.351), "Tauromenium": (15.29, 37.85),
       "Pityuses": (1.43, 38.90), "Cape Samonium (Crete)": (26.30, 35.28), "Mouth of Danube": (29.75, 44.85), "Abdera": (24.974, 40.933),
       "Myra": (29.985, 36.259), "Berytus": (35.50, 33.895), "Tyre": (35.20, 33.27)}
ctree = cKDTree(np.column_stack([SEA["C_x"], SEA["C_y"]]))
CELL_OF = {nm: int(ctree.query(proj(*xy))[1]) for nm, xy in LOC.items()}


def sea_times(pairs, **kw):
    """Sea-only times (no waiting) between the sea cells nearest each pair of places."""
    A, _ = build(MODES["foot"]["kmd"], season="summer", roads=False, **kw)
    out = {}
    for o in sorted({a for a, b in pairs}):
        d = dijkstra(A, directed=True, indices=k + npt + CELL_OF[o])
        for a, b in pairs:
            if a == o:
                out[(a, b)] = float(d[k + npt + CELL_OF[b]])
    return out


def table1(**kw):
    tt = sea_times(list(zip(T1["from"], T1["to"])), **kw)
    D = T1.copy(); D["model_days"] = [tt[(a, b)] for a, b in zip(D["from"], D["to"])]
    D["ratio"] = D.model_days / ((D.lo + D.hi) / 2)
    D["inside"] = (D.model_days >= D.lo) & (D.model_days <= D.hi)
    D["near"] = (D.model_days >= D.lo / 1.25) & (D.model_days <= D.hi * 1.25)
    return D


def calib_loss(x):
    m, uc, ue = np.exp(x)
    D = table1(v_down=V_DOWN * m, v_neu=V_NEU * m, v_up=uc, v_up_e=ue)
    return float(np.mean(np.log(D.ratio) ** 2))


opt = minimize(calib_loss, np.log([1.1, 1.0, 1.6]), method="Nelder-Mead", options={"maxfev": 60, "xatol": 0.02, "fatol": 1e-3})
M_CAL, UC_CAL, UE_CAL = map(float, np.exp(opt.x))
PB = {"mult": M_CAL, "v_down": V_DOWN * M_CAL, "v_neu": V_NEU * M_CAL, "v_up": UC_CAL, "v_up_e": UE_CAL, "loss": float(opt.fun)}
KW_B = {"v_down": PB["v_down"], "v_neu": PB["v_neu"], "v_up": PB["v_up"], "v_up_e": PB["v_up_e"]}
KW_A = {"v_down": PA["v_down"], "v_neu": PA["v_neu"], "v_up": PA["v_up"], "v_up_e": PA["v_up_e"]}
PB["ostia_alex_days"] = float(run(k + OSTIA_P, kmd=MODES["foot"]["kmd"], roads=False, **KW_B)[0][k + ALEX_P])
PB["alex_ostia_days"] = float(run(k + ALEX_P, kmd=MODES["foot"]["kmd"], roads=False, **KW_B)[0][k + OSTIA_P])
print("model B (calibrated, headline):", {k_: round(v, 3) for k_, v in PB.items()})
T1A = table1(**KW_A); T1B = table1(**KW_B)
t1sum = lambda D: {"n": int(len(D)), "inside": float(D.inside.mean()), "near": float(D.near.mean()), "median_ratio": float(D.ratio.median()),
                   "rmse_log": float(np.sqrt(np.mean(np.log(D.ratio) ** 2))), "n_inside": int(D.inside.sum()), "n_near": int(D.near.sum())}
PAR = {**PB, "port_days": PORT_DAYS, "polar_p": POLAR_P, "kt_kmd": KT, "A": PA, "table1_A": t1sum(T1A), "table1_B": t1sum(T1B)}
print("Table 1, model A", PAR["table1_A"], "; model B", PAR["table1_B"])
# ---------- all scenarios from Rome ----------
SC = {}
for md in MODE_ORDER:
    kmd = MODES[md]["kmd"]
    SC[("winter", md)] = run(ROME_N, kmd=kmd, season="winter")
    SC[("summer", md)] = run(ROME_N, kmd=kmd, season="summer", **KW_B)
SC[("calm", "foot")] = run(ROME_N, kmd=MODES["foot"]["kmd"], season="summer", wind=False, **KW_B)
SC[("caseA", "foot")] = run(ROME_N, kmd=MODES["foot"]["kmd"], season="summer", **KW_A)
T = {key: v[0] for key, v in SC.items()}


def legs(key, dst):
    """Route to node dst as a list of (type, from, to, days)."""
    t, pred, (U, Vv, W, TT) = SC[key]
    lk = {}
    for u, v, w, ty in zip(U, Vv, W, TT):
        lk[(u, v)] = ty
    out = []; n = dst
    while pred[n] >= 0:
        p = pred[n]; out.append((int(lk[(p, n)]), int(p), int(n), float(t[n] - t[p]))); n = p
    return out[::-1]


def summarise(key, dst):
    L = legs(key, dst)
    road_d = sum(d for ty, a, b, d in L if ty in (0, 1, 2)); sea_d = sum(d for ty, a, b, d in L if ty in (3, 4, 5, 6))
    ports = [PT.name[a - k] for ty, a, b, d in L if ty == 3]
    landings = [PT.name[b - k] for ty, a, b, d in L if ty == 4]
    sea_km = sum(e_km_lookup.get((a, b), 0) for ty, a, b, d in L if ty == 5)
    return {"road_days": road_d, "sea_days": sea_d, "boardings": len(ports), "ports_from": ports, "ports_to": landings, "sea_km": sea_km}


e_km_lookup = {(k + npt + a, k + npt + b): km for (a, b), km in zip(E[:, :2], e_km)}
res = {"rome_node": ROME_N, "params": PAR, "city": {}}
for key_, lat_name, en, xy in CITIES:
    n = CITY_N[key_]
    r = {"key": key_, "latin": lat_name, "name": en, "node": n, "node_name": nodes.name[n]}
    for md in MODE_ORDER:
        r[f"winter_{md}"] = float(T[("winter", md)][n]); r[f"summer_{md}"] = float(T[("summer", md)][n])
    r["calm_foot"] = float(T[("calm", "foot")][n]); r["modelA_foot"] = float(T[("caseA", "foot")][n])
    r["route"] = summarise(("summer", "foot"), n)
    r["route_courier"] = summarise(("summer", "courier"), n)
    res["city"][key_] = r
    print(f"{en:26s} road {r['winter_foot']:6.1f}  sea+road {r['summer_foot']:6.1f}  courier {r['winter_courier']:5.1f}/{r['summer_courier']:5.1f}  calm {r['calm_foot']:5.1f}  via {r['route']['ports_from']} -> {r['route']['ports_to']}")

# ---------- sensitivity (one parameter at a time, summer, on foot) ----------
SENS = {"speeds": [CAS["fav_q1"] / CAS["fav_median"], CAS["fav_q3"] / CAS["fav_median"]], "upwind": [0.5, 1.5], "port_days": [0.5, 3.0], "model_A": [None, None]}
sens = {}
for p_, (lo_, hi_) in SENS.items():
    for tag, val in (("lo", lo_), ("hi", hi_)):
        kw = dict(KW_B); kw["port_days"] = PORT_DAYS
        if p_ == "speeds": kw["v_down"] *= val; kw["v_neu"] *= val
        elif p_ == "upwind": kw["v_up"] *= val; kw["v_up_e"] *= val
        elif p_ == "port_days": kw["port_days"] = val
        else: kw = dict(KW_A); kw["port_days"] = PORT_DAYS
        t = run(ROME_N, kmd=MODES["foot"]["kmd"], season="summer", **kw)[0]
        for c in COMPARE:
            sens.setdefault(c, {}).setdefault(p_, {})[tag] = float(t[CITY_N[c]])
for c in COMPARE:
    allv = [v for p_ in sens[c].values() for v in p_.values()]
    res["city"][c]["summer_foot_min"] = float(min(allv)); res["city"][c]["summer_foot_max"] = float(max(allv))
res["sens"] = sens; res["sens_params"] = SENS

# ---------- section times and shares ----------
mid = {}
for key in T:
    md = key[1]; w = S.km.values / (MODES[md]["kmd"] * S.pas.values)
    mid[key] = np.minimum(T[key][S.u.values] + w / 2, T[key][S.v.values] + w / 2)
tot = float(S.km.sum())
res["km_within"] = {f"{s_}_{md}": {str(d): float(S.km[mid[(s_, md)] <= d].sum()) for d in (7, 14, 30, 60)} for s_, md in mid}
res["share_within"] = {kk: {d: v / tot for d, v in vv.items()} for kk, vv in res["km_within"].items()}
res["km_total"] = tot

# ---------- the places sea travel brings closest: major ancient places (DARE 'low' zoom places) on the network ----------
D = jload(f"{DARE}/places_low.geojson")["features"]
majors = []
for f in D:
    nm = (f["properties"].get("latin") or "").strip()
    if not nm:
        continue
    lo_, la_ = f["geometry"]["coordinates"][:2]
    d = haversine(lo_, la_, nodes.lon.values, nodes.lat.values); i = int(np.argmin(d))
    if d[i] <= 3 and nodes.net[i]:
        majors.append({"name": dash(nm), "modern": dash(f["properties"].get("modern") or ""), "node": i, "lon": lo_, "lat": la_})
MJ = pd.DataFrame(majors).drop_duplicates("node")
MJ["road"] = T[("winter", "foot")][MJ.node.values]; MJ["sea"] = T[("summer", "foot")][MJ.node.values]
MJ = MJ[np.isfinite(MJ.road)]
MJ["saved"] = MJ.road - MJ.sea; MJ["ratio"] = MJ.road / MJ.sea
res["n_majors"] = int(len(MJ))
res["closest_saved"] = MJ.sort_values("saved", ascending=False).head(12)[["name", "modern", "road", "sea", "saved", "ratio"]].to_dict("records")
res["closest_ratio"] = MJ[MJ.road >= 10].sort_values("ratio", ascending=False).head(12)[["name", "modern", "road", "sea", "saved", "ratio"]].to_dict("records")
res["majors_faster_by_sea"] = int((MJ.saved > 0.5).sum())
res["majors_median_road"] = float(MJ.road.median()); res["majors_median_sea"] = float(MJ.sea.median())
MJ.round(2).to_csv(f"{DATA}/major_places.csv", index=False)

# ---------- Casson's voyages: model against the record ----------
pairs = [tuple(x.strip() for x in r.route.split("-", 1)) for r in SEA["V"].itertuples()]
assert all(a in LOC and b in LOC for a, b in pairs)
VA = sea_times(pairs, **KW_A); VB = sea_times(pairs, **KW_B)
val = [{"route": r.route, "wind": r.wind, "reported_days": r.days, "model_days": VB[p_], "modelA_days": VA[p_], "nm": r.nm, "source": r.source}
       for r, p_ in zip(SEA["V"].itertuples(), pairs)]
VAL = pd.DataFrame(val); VAL["ratio"] = VAL.model_days / VAL.reported_days
VAL.round(2).to_csv(f"{DATA}/casson_validation.csv", index=False)
VAL["ratioA"] = VAL.modelA_days / VAL.reported_days
res["validation_A"] = {"median_ratio": float(VAL.ratioA.median()), "median_ratio_fav": float(VAL[VAL.wind == "favourable"].ratioA.median()),
                       "median_ratio_unf": float(VAL[VAL.wind == "unfavourable"].ratioA.median())}
res["table1_rows"] = T1B.assign(modelA_days=T1A.model_days.values).round(2).to_dict("records")
T1B.assign(modelA_days=T1A.model_days.values).round(2).to_csv(f"{DATA}/casson_table1_validation.csv", index=False)
res["validation"] = {"n": int(len(VAL)), "median_ratio": float(VAL.ratio.median()),
                     "median_ratio_fav": float(VAL[VAL.wind == "favourable"].ratio.median()), "median_ratio_unf": float(VAL[VAL.wind == "unfavourable"].ratio.median()),
                     "within_factor_1_5": float(((VAL.ratio > 1 / 1.5) & (VAL.ratio < 1.5)).mean()),
                     "corr_log": float(np.corrcoef(np.log(VAL.model_days), np.log(VAL.reported_days))[0, 1])}
print(VAL.round(1).to_string()); print(res["validation"])

# ---------- per-node table ----------
tab = nodes[["name", "lon", "lat"]].copy(); tab.insert(0, "node", np.arange(k))
for s_ in ("winter", "summer"):
    for md in MODE_ORDER:
        v = T[(s_, md)][:k]; tab[f"days_{'road_only' if s_ == 'winter' else 'road_and_sea'}_{md}"] = np.where(np.isfinite(v), np.round(v, 2), np.nan)
tab.round({"lon": 5, "lat": 5}).to_csv(f"{DATA}/travel_from_rome.csv", index=False)
pickle.dump({"T": T, "SC": SC, "res": res, "mid": mid, "CITY_N": CITY_N, "VAL": VAL, "MJ": MJ, "PAR": PAR, "k": k, "npt": npt, "nc": nc,
             "e_km": e_km, "e_brg": e_brg}, open(f"{WORK}/travel.pkl", "wb"))
jsave(res, f"{WORK}/travel.json", indent=1)
