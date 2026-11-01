"""Step 1. Read Itiner-e, clean the fields, and build the road graph.
- Road sections: 14,769 Itiner-e records, reprojected from World Mercator (EPSG:3395) to WGS84; Z values dropped.
  Dates of 9999 mean 'not given'. Length is the dataset's geodesic Shape_Leng.
- Nodes: section end points closer than 1 m are one node (the dataset is topologically clean at that tolerance).
- Node names: the place name shared by the sections that meet there (section names are 'Start-End'), else the nearest
  DARE place within 5 km, else the free end of a section's name.
- Sea crossings: short straits from common.CROSSINGS join the nearest nodes on each side.
Writes WORK/net.pkl (sections, nodes, edges) and data/roads.geojson (simplified geometry, all cleaned fields).
Run: python3 code/01_network.py
"""
import os, sys, re, pickle, collections
import numpy as np, pandas as pd, geopandas as gpd
from shapely.geometry import LineString, mapping
from scipy.spatial import cKDTree
import scipy.sparse as sp, scipy.sparse.csgraph as cg
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

g = gpd.read_file(f"{ROMAN}/itinere_roads.gpkg").to_crs(4326)
assert len(g) == 14769
g = g.reset_index(drop=True)
assert (g.InLine_FID.values == np.arange(len(g))).all()
geom = [LineString([(x, y) for x, y, *_ in ml.geoms[0].coords]) for ml in g.geometry]
assert all(len(ml.geoms) == 1 for ml in g.geometry)
nan = lambda v: None if (v is None or (isinstance(v, float) and np.isnan(v)) or v == 9999) else v
clean = lambda v: None if v is None or (isinstance(v, float) and np.isnan(v)) or str(v).strip() == "" else " ".join(str(v).split())
S = pd.DataFrame({"id": g.InLine_FID.values, "name": [clean(v) for v in g.Name], "type": g.Type.values, "cert": g.Segment_s.values,
                  "lo": [nan(v) for v in g.Lower_Date], "lo_e": [nan(v) for v in g.Low_Date_E],
                  "up": [nan(v) for v in g.Upper_Date], "up_e": [nan(v) for v in g.Up_Date_E],
                  "cons": [clean(v) for v in g.Cons_per_e], "itin": [clean(v) for v in g.Itinerary], "desc": [clean(v) for v in g.Descriptio],
                  "cite": [clean(v) for v in g.Citation], "bib": [clean(v) for v in g.Bibliograp],
                  "km": g.Shape_Leng.values / 1000, "slope": g.Avg_Slope.values, "pas": g.passabilit.values})
assert set(S.cert) == {"Certain", "Conjectured", "Hypothetical"} and set(S.type) == {"Main Road", "Secondary Road"}
S["geom"] = geom

# ---------- nodes ----------
ends = np.array([[l.coords[0], l.coords[-1]] for l in geom])          # (n, 2, 2)
P = np.vstack([ends[:, 0], ends[:, 1]]); m = len(S)
lat = np.radians(P[:, 1]); XY = np.column_stack([np.radians(P[:, 0]) * 6371000 * np.cos(lat), lat * 6371000])
pairs = cKDTree(XY).query_pairs(1.0, output_type="ndarray")
k, lab = cg.connected_components(sp.coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(len(P), len(P))), directed=False)
S["u"] = lab[:m]; S["v"] = lab[m:]
node_xy = np.zeros((k, 2)); np.add.at(node_xy, lab, P); node_xy /= np.bincount(lab, minlength=k)[:, None]
print("nodes", k, "self loops", int((S.u == S.v).sum()))

# ---------- node names ----------
D = [f for z in ("low", "medium", "high") for f in jload(f"{DARE}/places_{z}.geojson")["features"]]
dn = [(f["properties"].get("latin") or "").strip() for f in D]
dxy = np.array([f["geometry"]["coordinates"][:2] for f in D], float)
keep = [i for i, n in enumerate(dn) if n]
dn = [dn[i] for i in keep]; dxy = dxy[keep]
proj = lambda xy: np.column_stack([np.radians(xy[:, 0]) * 6371 * np.cos(np.radians(xy[:, 1])), np.radians(xy[:, 1]) * 6371])
dt = cKDTree(proj(dxy))
parts = [[p.strip() for p in (n or "").split("-") if p.strip() and not re.search(r"\d", p)] for n in S.name]
inc = collections.defaultdict(list)
for i, (u, v) in enumerate(zip(S.u, S.v)):
    inc[u].append(i); inc[v].append(i)
nname = [None] * k; how = [None] * k
dd, di = dt.query(proj(node_xy))
for n in range(k):
    if dd[n] <= 2:
        nname[n] = dn[di[n]]; how[n] = "dare"
for n in range(k):
    if nname[n] is None:
        c = collections.Counter(p for i in inc[n] for p in set(parts[i]))
        if c:
            p, cnt = c.most_common(1)[0]
            if cnt >= 2 and cnt >= len(inc[n]) * .5:
                nname[n] = p; how[n] = "shared"
for n in range(k):
    if nname[n] is None and dd[n] <= 5:
        nname[n] = dn[di[n]]; how[n] = "dare 5 km"
for _ in range(2):
    for n in range(k):
        if nname[n] is None and len(inc[n]) == 1:
            i = inc[n][0]; other = S.v[i] if S.u[i] == n else S.u[i]
            ps = [p for p in parts[i] if p != nname[other]]
            if ps:
                nname[n] = ps[-1] if S.v[i] == n else ps[0]; how[n] = "free end"
for n in range(k):
    if nname[n] is None:
        nname[n] = f"road junction near {dn[di[n]]}"; how[n] = "near"
nname = [dash(n) for n in nname]
print("node names by method", collections.Counter(how))

# ---------- components and crossings ----------
kc, lc = cg.connected_components(sp.coo_matrix((np.ones(m), (S.u, S.v)), shape=(k, k)), directed=False)
comp_km = collections.Counter()
for u, km in zip(S.u, S.km):
    comp_km[lc[u]] += km
main = comp_km.most_common(1)[0][0]


DEG = np.array([len(inc[n]) for n in range(k)])


def nearest_node(lon, lat, not_comp=None):
    """Best-connected node within 3 km of the point (not in component not_comp), else the nearest such node."""
    d = haversine(lon, lat, node_xy[:, 0], node_xy[:, 1])
    if not_comp is not None:
        d = np.where(lc == not_comp, np.inf, d)
    near = np.where(d <= 3)[0]
    i = int(near[np.lexsort((d[near], -DEG[near]))[0]]) if len(near) else int(np.argmin(d))
    return i, float(d[i])


X = []
for key, label, a, axy, b, bxy in CROSSINGS:
    ia, da = nearest_node(*axy); ib, db = nearest_node(*bxy, not_comp=lc[ia])
    if db > 12:          # both shores in the same component (Otranto, Gibraltar)
        ib, db = nearest_node(*bxy)
    assert da < 12 and db < 12, (key, da, db, nname[ia], nname[ib])
    km = float(haversine(*node_xy[ia], *node_xy[ib]))
    X.append({"key": key, "label": label, "a": a, "b": b, "u": ia, "v": ib, "km": km, "bridge": key in BRIDGES,
              "snap_km": [round(da, 2), round(db, 2)], "names": [nname[ia], nname[ib]]})
    print(f"crossing {key}: {nname[ia]} ({da:.1f} km off) to {nname[ib]} ({db:.1f} km off), {km:.0f} km")
# components after crossings
U = np.concatenate([S.u.values, [x["u"] for x in X]]); V = np.concatenate([S.v.values, [x["v"] for x in X]])
kc2, lc2 = cg.connected_components(sp.coo_matrix((np.ones(len(U)), (U, V)), shape=(k, k)), directed=False)
main2 = lc2[S.u[S.km.idxmax()]]
comps = []
for c in range(kc):
    s = S[[lc[u] == c for u in S.u]]
    b = np.array([l.bounds for l in s.geom]); cx = (b[:, 0].min() + b[:, 2].max()) / 2; cy = (b[:, 1].min() + b[:, 3].max()) / 2
    comps.append({"comp": c, "n": len(s), "km": float(s.km.sum()), "lon": cx, "lat": cy, "joined": bool(lc2[s.u.iloc[0]] == main2)})
comps.sort(key=lambda c: -c["km"])
for c in comps:
    print("component", c)

nodes = pd.DataFrame({"lon": node_xy[:, 0], "lat": node_xy[:, 1], "name": nname, "how": how, "comp": lc, "net": lc2 == main2,
                      "deg": [len(inc[n]) for n in range(k)]})
pickle.dump({"S": S, "nodes": nodes, "X": X, "comps": comps, "main": int(main)}, open(f"{WORK}/net.pkl", "wb"))

# ---------- reusable GeoJSON (lightly simplified) ----------
feats = []
nn = lambda x: None if x is None or (isinstance(x, float) and np.isnan(x)) else x
for r in S.itertuples():
    gs = r.geom.simplify(0.0005, preserve_topology=False)
    co = [[round(x, 5), round(y, 5)] for x, y in gs.coords]
    co[0] = [round(x, 5) for x in r.geom.coords[0]]; co[-1] = [round(x, 5) for x in r.geom.coords[-1]]
    feats.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": co},
                  "properties": {"id": int(r.id), "name": nn(r.name), "type": r.type, "certainty": r.cert,
                                 "lower_date": nn(r.lo), "lower_date_error": nn(r.lo_e), "upper_date": nn(r.up), "upper_date_error": nn(r.up_e),
                                 "construction_period": nn(r.cons), "itinerary": nn(r.itin), "description": nn(r.desc),
                                 "digitised_by": nn(r.cite), "bibliography": nn(r.bib), "km": round(float(r.km), 3),
                                 "avg_slope_deg": round(float(r.slope), 3), "passability": round(float(r.pas), 4),
                                 "from_node": int(r.u), "to_node": int(r.v)}})
jsave({"type": "FeatureCollection", "name": "itinere_roads_simplified",
       "source": f"Itiner-e static version 2024, https://doi.org/{ITINERE_DOI}, CC BY 4.0; geometry simplified to about 50 m",
       "features": feats}, f"{DATA}/roads.geojson")
nodes.assign(node=np.arange(k))[["node", "name", "lon", "lat", "deg", "comp", "net"]].round(5).to_csv(f"{DATA}/nodes.csv", index=False)
print("roads.geojson", os.path.getsize(f"{DATA}/roads.geojson") // 1024, "KB")
