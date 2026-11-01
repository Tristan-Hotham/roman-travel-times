"""Step 2. The sea layer: Casson's voyage speeds, the sea grid, the summer wind basins and the ports.
- Casson (1951): the knots of every voyage in his favourable-wind and unfavourable-wind tables, from
  TRAVEL/casson1951_transcription.md (checked against the LacusCurtius online edition; read here, not retyped). Medians and quartiles give the model's speeds.
- Sea grid: 15 km cells in a Lambert azimuthal equal-area projection centred on the Mediterranean; a cell is sea if
  its centre is not on Natural Earth 50m land. Cells are joined to their 16 nearest neighbours when the straight line
  between them stays at sea. The Red Sea, the Baltic and the far Atlantic are left out. Narrow straits that the grid
  cannot see (Bosporus, Dardanelles, Kerch, Messina) are joined by explicit links.
- Wind basins (summer, the etesian season): the Aegean, where the etesians blow from the north, and the eastern and
  central Mediterranean south of 38.6 N (and the Ionian Sea up to the Strait of Otranto) and east of 15.5 E, where they blow from the north-west
  (split at 28 E into a central basin and a Levant basin, so that the speed into the wind can differ) (Wikipedia, 'Etesian';
  Casson's note that ships could not sail direct from Alexandria to Rome in summer). Elsewhere: no prevailing wind.
- Ports: every Pleiades place typed port, harbour or anchorage with a location, plus the ports of Casson's voyages and
  other major harbours, located by their Pleiades record or, failing that, by the Itiner-e junction of that name.
  A port is kept if it lies within 25 km of a sea cell and 15 km of a road junction.
Writes WORK/sea.pkl and data/ports.csv, data/casson_voyages.csv.
Run: python3 code/02_sea.py
"""
import os, sys, re, pickle
import numpy as np, pandas as pd
from math import gcd
from scipy.spatial import cKDTree
import scipy.sparse as sp, scipy.sparse.csgraph as cg
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
from figlib import proj, INV, land_rings
from shapely.geometry import Polygon, Point, box as sbox
from shapely.ops import unary_union
from shapely.prepared import prep

N = pickle.load(open(f"{WORK}/net.pkl", "rb")); nodes = N["nodes"]

# ---------- Casson's voyages ----------
md = open(f"{TRAVEL}/casson1951_transcription.md", encoding="utf-8").read()
fav_txt = md.split("Voyages with favourable winds")[1].split("Voyages with unfavourable winds")[0]
unf_txt = md.split("Voyages with unfavourable winds")[1].split("Also fetched")[0]


def rows(txt, kind):
    out = []
    for ln in txt.splitlines():
        p = [x.strip() for x in ln.split("|")]
        if len(p) != 5 or not re.search(r"\d", p[1]):
            continue
        nm = float(re.sub(r"[^\d.]", "", p[1].split("(")[0]))
        days = [float(x) for x in re.findall(r"[\d.]+", p[2])]
        kn = [float(x) for x in re.findall(r"[\d.]+", p[3])]
        out.append({"route": p[0], "nm": nm, "days": float(np.mean(days)), "knots": float(np.mean(kn)), "source": p[4], "wind": kind,
                    "days_text": p[2], "knots_text": p[3]})
    return out


V = pd.DataFrame(rows(fav_txt, "favourable") + rows(unf_txt, "unfavourable"))
assert (V.wind == "favourable").sum() == 24 and (V.wind == "unfavourable").sum() == 10, V.wind.value_counts()
fav = V[V.wind == "favourable"].knots.values; unf = V[V.wind == "unfavourable"].knots.values
CAS = {"fav_median": float(np.median(fav)), "fav_q1": float(np.percentile(fav, 25)), "fav_q3": float(np.percentile(fav, 75)),
       "unf_median": float(np.median(unf)), "unf_q1": float(np.percentile(unf, 25)), "unf_q3": float(np.percentile(unf, 75)),
       "n_fav": int(len(fav)), "n_unf": int(len(unf)), "fav_min": float(fav.min()), "fav_max": float(fav.max()),
       "unf_min": float(unf.min()), "unf_max": float(unf.max())}
for q in ("between 4 and 6 knots over open water", "3 to 4 knots while working through islands or along coasts",
          "from less than 2 to 2 1/2 knots against the wind", "Rome to Alexandria 10 to 13 days; Alexandria to Rome 53 to 73 days"):
    assert q in md, q
CAS["table1"] = {"rome_alex": [10, 13], "alex_rome": [53, 73]}
print("Casson favourable median", CAS["fav_median"], "IQR", CAS["fav_q1"], CAS["fav_q3"], "; unfavourable median", CAS["unf_median"], CAS["unf_q1"], CAS["unf_q3"])

# ---------- sea grid ----------
CELL = 15000.0
LON0, LON1, LAT0, LAT1 = -19.0, 42.5, 28.0, 57.5
corners = [proj(lo, la) for lo in np.linspace(LON0, LON1, 30) for la in (LAT0, LAT1)] + [proj(lo, la) for lo in (LON0, LON1) for la in np.linspace(LAT0, LAT1, 30)]
xs_, ys_ = np.array(corners)[:, 0], np.array(corners)[:, 1]
X0, X1, Y0, Y1 = xs_.min(), xs_.max(), ys_.min(), ys_.max()
nx = int((X1 - X0) / CELL); ny = int((Y1 - Y0) / CELL)
gx = X0 + (np.arange(nx) + .5) * CELL; gy = Y0 + (np.arange(ny) + .5) * CELL
GX, GY = np.meshgrid(gx, gy)
lon, lat = INV.transform(GX.ravel(), GY.ravel()); lon = lon.reshape(ny, nx); lat = lat.reshape(ny, nx)
import rasterio.features, rasterio.transform
tm = rasterio.transform.from_bounds(X0, Y0, X1, Y1, nx, ny)
landp = [Polygon(r[0], r[1:]) for r in land_rings("50m", bbox=(-25, 15, 60, 66))]
land = rasterio.features.rasterize(((p, 1) for p in landp), out_shape=(ny, nx), transform=tm, fill=0).astype(bool)[::-1]   # row 0 = south
sea = ~land
excl = ((lat < 30.6) & (lon > 32.0)) | ((lon > 9.6) & (lat > 53.6)) | (lon < LON0) | (lon > LON1) | (lat < LAT0) | (lat > LAT1) | ((lat > 46.8) & (lon > 36))
sea &= ~excl
lab, ncomp = __import__("scipy.ndimage", fromlist=["label"]).label(sea, structure=np.ones((3, 3)))
sizes = np.bincount(lab.ravel()); keep_c = [c for c in range(1, ncomp + 1) if sizes[c] >= 50]
sea &= np.isin(lab, keep_c)
iy, ix = np.where(sea)
cid = -np.ones((ny, nx), int); cid[iy, ix] = np.arange(len(iy))
# display only: shading at sea fades out far from land and towards the edge of the modelled sea (the grid's bounding box and the
# excluded waters), so that no straight cut-offs show on the maps
from scipy.ndimage import distance_transform_edt
C_coast_km = distance_transform_edt(~land)[iy, ix] * CELL / 1000
outside = np.pad((~land) & excl, 1, constant_values=True)     # the grid border and the excluded waters (not small lagoons)
C_edge_km = distance_transform_edt(~outside)[1:-1, 1:-1][iy, ix] * CELL / 1000
sm_ = lambda t: np.clip(t, 0, 1) ** 2 * (3 - 2 * np.clip(t, 0, 1))
C_fade = np.minimum(sm_((500 - C_coast_km) / 200), sm_((C_edge_km - 15) / 220))
C_lon, C_lat = lon[iy, ix], lat[iy, ix]
C_x, C_y = gx[ix], gy[iy]
from scipy.ndimage import distance_transform_edt
print("sea cells", len(iy), "components kept", len(keep_c))

# ---------- basins and summer wind ----------
aeg = (C_lon >= 22.5) & (C_lon <= 28.5) & (C_lat >= 35.8) & (C_lat <= 41.0) & ~((C_lat > 40.25) & (C_lon > 26.2))
east = (C_lon >= 15.5) & (C_lon <= 36.5) & ((C_lat < 38.6) | ((C_lon < 21.0) & (C_lat < 39.9))) & ~aeg     # south of 38.6 N, and the Ionian Sea up to the Strait of Otranto
basin = np.zeros(len(iy), int); basin[east] = 2; basin[east & (C_lon >= 28.0)] = 3; basin[aeg] = 1
# 0: no prevailing wind; 1: Aegean, from N; 2: central Mediterranean (15.5 to 28 E), from NW; 3: Levant basin (east of 28 E), from NW
WIND_TO = {1: 180.0, 2: 135.0, 3: 135.0}                            # bearing the wind blows towards (degrees from north)
BASINS = {0: "No prevailing summer wind in the sources used", 1: "Aegean: etesians from the north",
          2: "Central Mediterranean: etesians from the north-west", 3: "Levant basin: etesians from the north-west"}

# ---------- edges between sea cells ----------
offs = sorted({(dx, dy) for dx in range(-2, 3) for dy in range(-2, 3) if (dx, dy) != (0, 0) and gcd(abs(dx), abs(dy)) == 1})
E = []
for dx, dy in offs:
    ok = sea.copy()
    a = np.zeros_like(sea); b = np.zeros_like(sea)
    ys0, ys1 = max(0, -dy), ny - max(0, dy); xs0, xs1 = max(0, -dx), nx - max(0, dx)
    src = np.zeros_like(sea); src[ys0:ys1, xs0:xs1] = sea[ys0:ys1, xs0:xs1] & sea[ys0 + dy:ys1 + dy, xs0 + dx:xs1 + dx]
    if abs(dx) == 2 or abs(dy) == 2:      # knight moves: the two cells the line passes must be sea too
        hx, hy = (dx // 2 if abs(dx) == 2 else 0), (dy // 2 if abs(dy) == 2 else 0)
        m1 = np.zeros_like(sea); m2 = np.zeros_like(sea)
        sx, sy_ = (np.sign(dx), 0) if abs(dx) == 2 else (0, np.sign(dy))
        ax_, ay_ = (dx - sx, dy - sy_)
        sh = lambda ddx, ddy: np.pad(sea, 2)[2 + ddy:2 + ddy + ny, 2 + ddx:2 + ddx + nx]
        src &= sh(int(sx), int(sy_)) & sh(int(ax_), int(ay_))
    yy, xx = np.where(src)
    E.append(np.column_stack([cid[yy, xx], cid[yy + dy, xx + dx], np.full(len(yy), dx), np.full(len(yy), dy)]))
E = np.vstack(E)
# explicit strait links (lon, lat on each side)
STRAITS = [("Bosporus", (29.15, 41.30), (28.98, 40.95)), ("Dardanelles", (26.70, 40.45), (26.15, 40.00)),
           ("Kerch Strait", (36.65, 45.45), (36.55, 45.15)), ("Strait of Messina", (15.62, 38.30), (15.60, 38.05))]
tree = cKDTree(np.column_stack([C_x, C_y]))
SL = []
for nm, a, b in STRAITS:
    ia = int(tree.query(proj(*a))[1]); ib = int(tree.query(proj(*b))[1])
    SL.append((nm, ia, ib))
comp_n, comp = cg.connected_components(sp.coo_matrix((np.ones(len(E) + len(SL)), (np.r_[E[:, 0], [s[1] for s in SL]], np.r_[E[:, 1], [s[2] for s in SL]])), shape=(len(iy), len(iy))), directed=False)
big = np.bincount(comp).argmax()
print("sea components after straits", comp_n, "main has", (comp == big).sum(), "cells; outside main:", (comp != big).sum())

# ---------- ports ----------
pl = pd.read_csv(f"{PLEIADES}/places.csv"); pt = pd.read_csv(f"{PLEIADES}/places_place_types.csv")
typed = pt[pt.place_type.isin(["port", "harbor", "anchorage"])].groupby("place_id").place_type.first()
P = pl[pl.id.isin(typed.index) & pl.representative_latitude.notna()][["id", "title", "representative_longitude", "representative_latitude", "location_precision"]].copy()
P.columns = ["pleiades", "name", "lon", "lat", "precision"]; P["source"] = "Pleiades port type: " + P.pleiades.map(typed)
# major harbours of the ancient sources (Casson's voyages, the grain routes, fleet bases), by Pleiades id where it has one
EXTRA_PL = {422995: "Ostia", 432815: "Puteoli", 256177: "Gades", 148127: "Massilia", 246347: "Narbo", 462538: "Messana", 481818: "Dyrrachium",
            687839: "Ascalon", 109008: "Gesoriacum", 79664: "Rutupiae", 79574: "Londinium", 265849: "Carthago Nova", 187290: "Aquileia",
            727192: "Pelusium", 580062: "Piraeus", 570567: "Patrae", 217016: "Tomis", 256338: "Olisipo", 138248: "Burdigala", 256063: "Carteia",
            305090: "Hippo Regius", 344456: "Oea", 344448: "Lepcis Magna", 707617: "Salamis (Cyprus)", 639105: "Side", 639005: "Myra",
            599636: "Halicarnassus", 216882: "Mesembria", 854719: "Pantikapaion", 197488: "Salona", 393379: "Ariminum", 462503: "Syracusae",
            462281: "Lilybaeum", 471899: "Caralis", 275736: "Tingi", 403253: "Pisae", 246382: "Emporiae", 266090: "Valentia", 491741: "Thessalonica",
            590030: "Rhodos", 678393: "Sidon", 678437: "Tyrus", 687902: "Gaza", 678010: "Ptolemais (Ake)", 658483: "Seleucia Pieria",
            315248: "Utica", 442810: "Tarentum", 442509: "Brundisium", 393480: "Ravenna", 857321: "Sinope", 857359: "Trapezus",
            550434: "Alexandria Troas", 501609: "Sestos", 501325: "Abydos", 216706: "Apollonia Pontica", 324716: "Hadrumetum",
            344282: "Sabratha", 373757: "Berenice (Cyrenaica)", 589886: "Kydonia", 570483: "Methone", 197312: "Iader", 187578: "Tergeste",
            295279: "Iol Caesarea", 285512: "Rusaddir", 727070: "Alexandria", 314921: "Carthago", 79646: "Portus Dubris"}
ex = pl[pl.id.isin(EXTRA_PL)][["id", "representative_longitude", "representative_latitude", "location_precision"]].copy()
ex.columns = ["pleiades", "lon", "lat", "precision"]; ex["name"] = ex.pleiades.map(EXTRA_PL); ex["source"] = "Pleiades record (major harbour in the ancient sources)"
assert len(ex) == len(EXTRA_PL), set(EXTRA_PL) - set(ex.pleiades)
# not found as single places in Pleiades: the Itiner-e junction of that name
EXTRA_NODE = {"Byzantium": (28.977, 41.008), "Ephesos": (27.341, 37.940), "Tarraco": (1.254, 41.115), "Caesarea Maritima": (34.892, 32.502),
              "Nicomedia": (29.920, 40.765), "Cyzicus": (27.885, 40.388), "Berytus": (35.500, 33.895),
              "Ioppe": (34.752, 32.054), "Paraetonium": (27.240, 31.355), "Apollonia (Cyrenaica)": (21.970, 32.905), "Lechaion": (22.879, 37.931),
              "Kenchreai": (22.993, 37.882), "Rhegium": (15.644, 38.109), "Centumcellae": (11.795, 42.093), "Neapolis": (14.250, 40.840),
              "Hydruntum": (18.491, 40.146), "Ancona": (13.515, 43.623), "Antium": (12.629, 41.448), "Eboracum": (-1.082, 53.962)}
rows_ = []
for nm, xy in EXTRA_NODE.items():
    d = haversine(*xy, nodes.lon.values, nodes.lat.values); i = int(np.argmin(d))
    if d[i] >= 6:
        print("no Itiner-e junction within 6 km, left out:", nm); continue
    rows_.append({"pleiades": None, "name": nm, "lon": float(nodes.lon[i]), "lat": float(nodes.lat[i]), "precision": "Itiner-e junction",
                  "source": f"Itiner-e junction '{nodes.name[i]}'"})
P = pd.concat([P, ex, pd.DataFrame(rows_)], ignore_index=True)
P = P[(P.lon.between(LON0, LON1)) & (P.lat.between(LAT0, LAT1))]
P["name"] = [dash(re.sub(r"\s+", " ", str(n))) for n in P.name]
P["name"] = P.name.replace({"Trajanic harbor": "Portus (Trajan's harbour)"})
# dedupe: one port per 3 km (keep the named extra over the typed record)
P = P.sort_values("source", key=lambda s: s.str.startswith("Pleiades port"), kind="stable").reset_index(drop=True)
keep = []; kt = []
for r in P.itertuples():
    if kt and min(haversine(r.lon, r.lat, np.array([k[0] for k in kt]), np.array([k[1] for k in kt]))) < 3:
        continue
    keep.append(r.Index); kt.append((r.lon, r.lat))
P = P.loc[keep].reset_index(drop=True)
px, py = proj(P.lon.values, P.lat.values)
dsea, isea = tree.query(np.column_stack([px, py]))
dn = [haversine(lo, la, nodes.lon.values, nodes.lat.values) for lo, la in zip(P.lon, P.lat)]
dn = np.array(dn); dnode = dn.min(1); inode = dn.argmin(1)
P["sea_cell"] = isea; P["sea_km"] = dsea / 1000; P["node"] = inode; P["node_km"] = dnode; P["node_name"] = nodes.name.values[inode]
P["in_main_sea"] = comp[isea] == big
P["net"] = nodes.net.values[inode]
Pk = P[(P.sea_km <= 25) & (P.node_km <= 15)].reset_index(drop=True)
print("ports: candidates", len(P), "kept", len(Pk), "dropped (far from sea or roads)", len(P) - len(Pk))
Pk.round({"lon": 5, "lat": 5, "sea_km": 2, "node_km": 2}).to_csv(f"{DATA}/ports.csv", index=False)
V.to_csv(f"{DATA}/casson_voyages.csv", index=False)
pickle.dump({"CAS": CAS, "V": V, "grid": {"X0": X0, "Y0": Y0, "nx": nx, "ny": ny, "cell": CELL}, "iy": iy, "ix": ix, "cid": cid,
             "C_lon": C_lon, "C_coast_km": C_coast_km, "C_edge_km": C_edge_km, "C_fade": C_fade, "C_lat": C_lat, "C_x": C_x, "C_y": C_y, "basin": basin, "WIND_TO": WIND_TO, "BASINS": BASINS,
             "E": E, "STRAITS": SL, "comp": comp, "main": big, "ports": Pk, "sea": sea}, open(f"{WORK}/sea.pkl", "wb"))
print({b: int((basin == b).sum()) for b in (0, 1, 2, 3)})
