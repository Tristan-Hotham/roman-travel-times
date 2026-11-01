"""Step 4. Page data: data/network.json (roads, crossings, ports, sea cells and every model parameter, so that the page can
rerun the model from any start), data/roads_site.json (compact road lines), and three lookup grids in Web Mercator:
grid_edge.png and grid_dist.png (nearest road point and distance, for land) and grid_sea.png (nearest sea cell, for sea).
Run: python3 code/04_pagedata.py
"""
import os, sys, pickle
import numpy as np
from scipy.spatial import cKDTree
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
from figlib import proj

N = pickle.load(open(f"{WORK}/net.pkl", "rb")); SEA = pickle.load(open(f"{WORK}/sea.pkl", "rb")); TR = pickle.load(open(f"{WORK}/travel.pkl", "rb"))
S, nodes, X = N["S"], N["nodes"], N["X"]; PT = SEA["ports"]; PAR = TR["PAR"]
k = len(nodes)
cert_i = {c: i for i, (c, *_ ) in enumerate(CERT)}

net = {"nodes": [[round(float(x), 4), round(float(y), 4)] for x, y in zip(nodes.lon, nodes.lat)], "names": list(nodes.name),
       "edges": [[int(u), int(v), round(float(km), 3), round(float(p), 3)] for u, v, km, p in zip(S.u, S.v, S.km, S.pas)],
       "crossings": [[x["u"], x["v"], round(x["km"], 1), 1 if x["bridge"] else 0, x["label"], x["a"], x["b"]] for x in X],
       "rome": TR["res"]["rome_node"], "cities": [[key, lat_name, en, TR["CITY_N"][key]] for key, lat_name, en, xy in CITIES if key != "ostia"],
       "modes": [[md, MODES[md]["label"], MODES[md]["kmd"]] for md in MODE_ORDER], "cross_days": CROSSING_DAYS,
       "off_factor": OFFROAD_FACTOR, "off_max": OFFROAD_MAX_KM,
       "ports": [[r.name, round(r.lon, 4), round(r.lat, 4), int(r.node), round(r.node_km, 3), int(r.sea_cell), round(r.sea_km, 3)] for r in PT.itertuples()],
       "cells": [[round(float(a), 3), round(float(b), 3), int(c)] for a, b, c in zip(SEA["C_lon"], SEA["C_lat"], SEA["basin"])],
       "cell_ij": [[int(i), int(j)] for i, j in zip(SEA["ix"], SEA["iy"])], "cell_km": SEA["grid"]["cell"] / 1000,
       "straits": [[nm, int(a), int(b)] for nm, a, b in SEA["STRAITS"]],
       "wind_to": {str(b): v for b, v in SEA["WIND_TO"].items()},
       "sea": {"v_down": PAR["v_down"], "v_neu": PAR["v_neu"], "v_up": {"1": PAR["v_up_e"], "2": PAR["v_up"], "3": PAR["v_up_e"]}, "polar_p": PAR["polar_p"], "port_days": PAR["port_days"], "kt_kmd": PAR["kt_kmd"]}}

# ---------- land lookup grid (as in roman-roads) ----------
LON0, LON1, LAT0, LAT1 = -12.0, 47.0, 21.5, 58.5
NX = 1000; R_E = 6378137.0
merc = lambda lat: R_E * np.log(np.tan(np.pi / 4 + np.radians(lat) / 2))
X0, X1 = np.radians(LON0) * R_E, np.radians(LON1) * R_E; Y0, Y1 = merc(LAT0), merc(LAT1)
NY = int(round(NX * (Y1 - Y0) / (X1 - X0)))
xs = X0 + (np.arange(NX) + .5) * (X1 - X0) / NX; ys = Y1 - (np.arange(NY) + .5) * (Y1 - Y0) / NY
glon = np.degrees(xs / R_E); glat = np.degrees(2 * np.arctan(np.exp(ys / R_E)) - np.pi / 2)
se, sf, sx, sy = [], [], [], []
for i, gm in enumerate(S.geom):
    L = gm.length; n = max(2, int(np.ceil(S.km[i] / 1.0)) + 1)
    for f in np.linspace(0, 1, n):
        p = gm.interpolate(f * L); se.append(i); sf.append(f); sx.append(p.x); sy.append(p.y)
se, sf, sx, sy = map(np.array, (se, sf, sx, sy))
P3 = lambda lon, lat: np.column_stack([np.cos(np.radians(lat)) * np.cos(np.radians(lon)), np.cos(np.radians(lat)) * np.sin(np.radians(lon)), np.sin(np.radians(lat))])
tree = cKDTree(P3(sx, sy))
GL, GA = np.meshgrid(glon, glat)
chord, idx = tree.query(P3(GL.ravel(), GA.ravel()))
dkm = 2 * 6371.0088 * np.arcsin(np.clip(chord / 2, 0, 1))
import rasterio.features, rasterio.transform
from shapely.geometry import shape, box
from shapely.ops import transform as stransform
land = [shape(f["geometry"]) for f in jload(f"{GEO}/ne_10m_admin_0_countries.geojson")["features"]]
tm = rasterio.transform.from_bounds(X0, Y0, X1, Y1, NX, NY)
to_m = lambda x, y, z=None: (np.radians(np.asarray(x)) * R_E, merc(np.clip(np.asarray(y), -85, 85)))
clipb = box(LON0 - 1, LAT0 - 1, LON1 + 1, LAT1 + 1)
shapes = [stransform(to_m, g_.intersection(clipb)) for g_ in land if g_.intersects(clipb)]
mask = rasterio.features.rasterize(((s_, 1) for s_ in shapes if not s_.is_empty), out_shape=(NY, NX), transform=tm, fill=0, all_touched=True).astype(bool)
ok = mask.ravel() & (dkm <= OFFROAD_MAX_KM)
code = np.where(ok, (se[idx].astype(np.int64) << 8) | np.round(sf[idx] * 255).astype(np.int64), 0xFFFFFF)
Image.fromarray(np.stack([(code >> 16) & 255, (code >> 8) & 255, code & 255], -1).reshape(NY, NX, 3).astype(np.uint8), "RGB").save(f"{DATA}/grid_edge.png", optimize=True)
Image.fromarray(np.where(ok, np.clip(np.round(dkm * 4), 0, 200), 255).reshape(NY, NX).astype(np.uint8), "L").save(f"{DATA}/grid_dist.png", optimize=True)
# ---------- sea lookup grid ----------
mask_strict = rasterio.features.rasterize(((s_, 1) for s_ in shapes if not s_.is_empty), out_shape=(NY, NX), transform=tm, fill=0, all_touched=False).astype(bool)
px, py = proj(GL.ravel(), GA.ravel())
ctree = cKDTree(np.column_stack([SEA["C_x"], SEA["C_y"]]))
dsea, isea = ctree.query(np.column_stack([px, py]))
oks = (~mask_strict.ravel()) & (dsea <= SEA["grid"]["cell"] * 0.9)
c2 = np.where(oks, (np.round(SEA["C_fade"][isea] * 254).astype(np.int64) << 16) | isea, 0xFFFFFF)     # R: display fade 0 to 254 (open ocean and edge of the modelled sea), G B: cell
Image.fromarray(np.stack([(c2 >> 16) & 255, (c2 >> 8) & 255, c2 & 255], -1).reshape(NY, NX, 3).astype(np.uint8), "RGB").save(f"{DATA}/grid_sea.png", optimize=True)
net["grid"] = {"lon0": LON0, "lon1": LON1, "lat0": LAT0, "lat1": LAT1, "nx": NX, "ny": NY, "dist_scale": 4}
jsave(net, f"{DATA}/network.json")
pickle.dump({"samples": (se, sf, sx, sy)}, open(f"{WORK}/samples.pkl", "wb"))

# ---------- compact road lines ----------
rows, geo, names, nix = [], [], [], {}
for r in S.itertuples():
    gs = r.geom.simplify(0.0012, preserve_topology=False)
    co = np.array(gs.coords); co[0] = r.geom.coords[0]; co[-1] = r.geom.coords[-1]
    q = np.round(co * 1e4).astype(int); geo.append(np.vstack([q[:1], np.diff(q, axis=0)]).ravel().tolist())
    nm = r.name if isinstance(r.name, str) else ""
    if nm not in nix:
        nix[nm] = len(names); names.append(dash(nm))
    rows.append([0 if r.type == "Main Road" else 1, cert_i[r.cert], nix[nm], round(float(r.slope), 1)])
jsave({"cols": ["type", "cert", "name", "slope"], "rows": rows, "geo": geo, "name": names}, f"{DATA}/roads_site.json")
for f in ("network.json", "roads_site.json", "grid_edge.png", "grid_dist.png", "grid_sea.png"):
    print(f, os.path.getsize(f"{DATA}/{f}") // 1024, "KB")
