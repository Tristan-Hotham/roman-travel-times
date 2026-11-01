"""Shared drawing helpers for the figures, the header and the collage: fonts, colours, a Lambert azimuthal equal-area
projection centred on the Mediterranean, Natural Earth land, the roads, and the days-from-Rome raster in that projection."""
import os, sys, pickle
import numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.collections import LineCollection
from matplotlib.path import Path
from matplotlib.patches import PathPatch
from pyproj import Transformer
from shapely.geometry import shape, box
from shapely.ops import unary_union
from scipy.spatial import cKDTree
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

FD = os.path.join(WORK, "fonts"); os.makedirs(FD, exist_ok=True)
if not os.path.exists(f"{FD}/Fraunces-Black.ttf"):
    from fontTools.ttLib import TTFont
    from fontTools.varLib import instancer
    instancer.instantiateVariableFont(TTFont(f"{FONTS}/FrauncesVar.ttf"), {"wght": 900, "opsz": 144, "SOFT": 0, "WONK": 0}).save(f"{FD}/Fraunces-Black.ttf")
    instancer.instantiateVariableFont(TTFont(f"{FONTS}/FrauncesVar.ttf"), {"wght": 700, "opsz": 48, "SOFT": 0, "WONK": 0}).save(f"{FD}/Fraunces-Bold.ttf")
    instancer.instantiateVariableFont(TTFont(f"{FONTS}/FrauncesVar.ttf"), {"wght": 400, "opsz": 48, "SOFT": 0, "WONK": 1}).save(f"{FD}/Fraunces-Italic.ttf")
for f in ["IBMPlexMono-Regular.ttf", "IBMPlexMono-Medium.ttf", "SourceSerif4-Regular.ttf", "SourceSerif4-Semibold.ttf", "SourceSerif4-It.ttf"]:
    fm.fontManager.addfont(os.path.join(FONTS, f))
DISP = fm.FontProperties(fname=f"{FD}/Fraunces-Black.ttf")
DISPB = fm.FontProperties(fname=f"{FD}/Fraunces-Bold.ttf")
SER, MONO = "Source Serif 4", "IBM Plex Mono"
plt.rcParams.update({"font.family": MONO, "font.size": 11})
BG, FG, MUT, RULE, PAPER = "#F6F1E7", "#1F1A17", "#6B625A", "#E2D9C9", "#FCFAF5"
SEA, LANDC, COAST = "#E3EBEC", "#EDE6D8", "#C4BBA9"
HOT, COOL = "#A8322D", "#1C3A5E"
LAEA = "+proj=laea +lat_0=40 +lon_0=16 +datum=WGS84 +units=m +no_defs"
FWD = Transformer.from_crs(4326, LAEA, always_xy=True)
INV = Transformer.from_crs(LAEA, 4326, always_xy=True)


def proj(lon, lat):
    return FWD.transform(np.asarray(lon, float), np.asarray(lat, float))


_LAND = {}


def land_rings(res="50m", bbox=(-25, 12, 60, 66)):
    """Natural Earth land clipped to a lon/lat box, densified and projected: list of ring lists (exterior first)."""
    key = (res, bbox)
    if key in _LAND:
        return _LAND[key]
    src = f"{GEO}/ne_50m_land.geojson" if res == "50m" else f"{GEO}/ne_10m_admin_0_countries.geojson"
    g = unary_union([shape(f["geometry"]).buffer(0) for f in jload(src)["features"]]).intersection(box(*bbox))
    out = []
    for p in getattr(g, "geoms", [g]):
        if p.geom_type != "Polygon" or p.area < 0.002:
            continue
        def dens(coords):
            a = np.array(coords); pts = [a[0]]
            for s, t in zip(a[:-1], a[1:]):
                n = max(1, int(np.ceil(np.hypot(*(t - s)) / .5)))
                for u in np.linspace(0, 1, n + 1)[1:]:
                    pts.append(s + (t - s) * u)
            a = np.array(pts); x, y = proj(a[:, 0], a[:, 1]); return np.column_stack([x, y])
        out.append([dens(p.exterior.coords)] + [dens(r.coords) for r in p.interiors])
    _LAND[key] = out
    return out


def draw_land(ax, fc=LANDC, ec=COAST, lw=.5, z=1, res="50m"):
    for rings in land_rings(res):
        verts = np.concatenate(rings); codes = []
        for r in rings:
            codes += [Path.MOVETO] + [Path.LINETO] * (len(r) - 2) + [Path.CLOSEPOLY]
        ax.add_patch(PathPatch(Path(verts, codes), fc=fc, ec=ec if lw else "none", lw=lw, zorder=z))


def load():
    N = pickle.load(open(f"{WORK}/net.pkl", "rb")); TR = pickle.load(open(f"{WORK}/travel.pkl", "rb")); AN = pickle.load(open(f"{WORK}/analysis.pkl", "rb"))
    return N, TR, AN, jload(f"{DATA}/results.json")


_ROADXY = None


def road_xy(S, simplify=0.004):
    """Projected coordinates of every section (lightly simplified for drawing)."""
    global _ROADXY
    if _ROADXY is None or len(_ROADXY) != len(S):
        out = []
        for gm in S.geom:
            co = np.array(gm.simplify(simplify).coords) if simplify else np.array(gm.coords)
            x, y = proj(co[:, 0], co[:, 1]); out.append(np.column_stack([x, y]))
        _ROADXY = out
    return _ROADXY


def sec_mid_days(S, T, md="foot"):
    w = S.km.values / (MODES[md]["kmd"] * S.pas.values)
    return np.minimum(T[md][S.u.values] + w / 2, T[md][S.v.values] + w / 2)


def days_raster(TR, S, extent, res_m=4000, md="foot", t=None):
    """Days from the source to every cell of a grid in the projection (NaN off land or more than 50 km from a road)."""
    x0, x1, y0, y1 = extent
    nx = int((x1 - x0) / res_m); ny = int((y1 - y0) / res_m)
    xs = x0 + (np.arange(nx) + .5) * res_m; ys = y1 - (np.arange(ny) + .5) * res_m
    GX, GY = np.meshgrid(xs, ys); lon, lat = INV.transform(GX.ravel(), GY.ravel())
    se, sf, sx, sy = TR["samples"]
    P3 = lambda lo, la: np.column_stack([np.cos(np.radians(la)) * np.cos(np.radians(lo)), np.cos(np.radians(la)) * np.sin(np.radians(lo)), np.sin(np.radians(la))])
    tree = cKDTree(P3(sx, sy)); chord, idx = tree.query(P3(lon, lat))
    dkm = 2 * 6371.0088 * np.arcsin(np.clip(chord / 2, 0, 1))
    t = TR["T"][md] if t is None else t; kmd = MODES[md]["kmd"]
    e = se[idx]; f = sf[idx]; w = S.km.values[e] / (kmd * S.pas.values[e])
    tt = np.minimum(t[S.u.values[e]] + f * w, t[S.v.values[e]] + (1 - f) * w) + dkm / (kmd * OFFROAD_FACTOR)
    # land mask
    import rasterio.features, rasterio.transform
    from shapely.geometry import Polygon
    tm = rasterio.transform.from_bounds(x0, y0, x1, y1, nx, ny)
    shapes = []
    for rings in land_rings("50m"):
        shapes.append(Polygon(rings[0], rings[1:]))
    mask = rasterio.features.rasterize(((s, 1) for s in shapes), out_shape=(ny, nx), transform=tm, fill=0).astype(bool)
    out = np.where(mask.ravel() & (dkm <= OFFROAD_MAX_KM), tt, np.nan).reshape(ny, nx)
    dist = dkm.reshape(ny, nx)
    return out, dist, (x0, x1, y0, y1)


def save(fig, path, dpi=200):
    fig.savefig(path, dpi=dpi, facecolor=fig.get_facecolor())
    plt.close(fig)


def style(ax, grid=True, axis="x"):
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    for s in ("left", "bottom"): ax.spines[s].set_color(MUT)
    ax.tick_params(colors=FG, labelsize=10)
    if grid: ax.grid(axis=axis, color=RULE, lw=.8); ax.set_axisbelow(True)


EMPIRE = None


def empire_extent(pad=0.04):
    """Projected box round the whole network (Britain to Egypt, Portugal to the Euphrates)."""
    x0, y0 = proj(-10.5, 36)[0], proj(16, 21.5)[1]
    x1, y1 = proj(44.5, 36)[0], proj(16, 59.6)[1]
    return (x0, x1, y0, y1)
