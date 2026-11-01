"""Step 7. Figures for the blog (release/blog/b_*.png), the paper (release/paper/fig_*.png, same images) and the header
card (header.png, 1200 x 630). Also writes WORK/rasters.pkl, the land and sea day rasters reused by the collage.
Run: python3 code/07_figures.py
"""
import os, sys, shutil, pickle
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figlib import *
import matplotlib.patheffects as pe
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

N = pickle.load(open(f"{WORK}/net.pkl", "rb")); SEAD = pickle.load(open(f"{WORK}/sea.pkl", "rb")); TR = pickle.load(open(f"{WORK}/travel.pkl", "rb"))
SM = pickle.load(open(f"{WORK}/samples.pkl", "rb")); R = jload(f"{DATA}/results.json")
S = N["S"]; T = TR["T"]; k, npt = TR["k"], TR["npt"]; PT = SEAD["ports"]
BLOG = os.path.join(ROOT, "release", "blog"); PAP = os.path.join(ROOT, "release", "paper")
os.makedirs(BLOG, exist_ok=True); os.makedirs(PAP, exist_ok=True)
XY = road_xy(S, simplify=0.003)
EXT = empire_extent()
halo = [pe.withStroke(linewidth=3.2, foreground=PAPER)]
RMAX = RAMP[-1][0]


def rasters(ext, res_m=6000):
    """Days from Rome on foot on land (roads only and road and sea) and at sea (road and sea), on a grid in the projection."""
    x0, x1, y0, y1 = ext; nx = int((x1 - x0) / res_m); ny = int((y1 - y0) / res_m)
    GX, GY = np.meshgrid(x0 + (np.arange(nx) + .5) * res_m, y1 - (np.arange(ny) + .5) * res_m)
    lon, lat = INV.transform(GX.ravel(), GY.ravel())
    se, sf, sx, sy = SM["samples"]
    P3 = lambda lo, la: np.column_stack([np.cos(np.radians(la)) * np.cos(np.radians(lo)), np.cos(np.radians(la)) * np.sin(np.radians(lo)), np.sin(np.radians(la))])
    chord, idx = cKDTree(P3(sx, sy)).query(P3(lon, lat)); dkm = 2 * 6371.0088 * np.arcsin(np.clip(chord / 2, 0, 1))
    import rasterio.features, rasterio.transform
    from shapely.geometry import Polygon
    tm = rasterio.transform.from_bounds(x0, y0, x1, y1, nx, ny)
    land = rasterio.features.rasterize(((Polygon(r[0], r[1:]), 1) for r in land_rings("50m")), out_shape=(ny, nx), transform=tm, fill=0).astype(bool).ravel()
    kmd = MODES["foot"]["kmd"]; e = se[idx]; f = sf[idx]; w = S.km.values[e] / (kmd * S.pas.values[e])
    out = {}
    for s_ in ("winter", "summer"):
        t = T[(s_, "foot")]
        tt = np.minimum(t[S.u.values[e]] + f * w, t[S.v.values[e]] + (1 - f) * w) + dkm / (kmd * OFFROAD_FACTOR)
        out[s_] = np.where(land & (dkm <= OFFROAD_MAX_KM), tt, np.nan).reshape(ny, nx)
    ds, isea = cKDTree(np.column_stack([SEAD["C_x"], SEAD["C_y"]])).query(np.column_stack([GX.ravel(), GY.ravel()]))
    out["seafade"] = SEAD["C_fade"][isea].reshape(ny, nx)
    out["sea"] = np.where(~land & (ds <= SEAD["grid"]["cell"] * .9), T[("summer", "foot")][k + npt + isea], np.nan).reshape(ny, nx)
    out["dist"] = dkm.reshape(ny, nx); out["ext"] = ext
    return out


RS = rasters(EXT)
pickle.dump(RS, open(f"{WORK}/rasters.pkl", "wb"))


def rgba(D, alpha, dist=None):
    fin = np.isfinite(D); rgb = ramp_rgb(np.where(fin, D, 0)); rgb[~fin & ~np.isnan(D)] = (.62, .6, .56)
    a = np.where(np.isnan(D), 0, alpha)
    if dist is not None:
        a = a * np.clip(1 - (dist - 30) / 25, .35, 1)
    return np.dstack([rgb, a])


def base(ax, ext=EXT):
    ax.set_facecolor(SEA); draw_land(ax, lw=.4)
    ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3]); ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values(): s.set_color(RULE)


def road_cols(season):
    w = S.km.values / (MODES["foot"]["kmd"] * S.pas.values); t = T[(season, "foot")]
    mid = np.minimum(t[S.u.values] + w / 2, t[S.v.values] + w / 2)
    return [tuple(ramp_rgb(d)) if np.isfinite(d) else (.55, .53, .5) for d in mid]


def draw_days(ax, season, lw=(.32, .55), sea_alpha=.55):
    if season == "summer":
        ax.imshow(rgba(RS["sea"], sea_alpha * RS["seafade"]), extent=RS["ext"], origin="upper", zorder=1.5, interpolation="bilinear")
    ax.imshow(rgba(RS[season], .4, RS["dist"]), extent=RS["ext"], origin="upper", zorder=2, interpolation="bilinear")
    col = road_cols(season); main = (S.type == "Main Road").values
    for sel, w_ in ((~main, lw[0]), (main, lw[1])):
        idx = np.where(sel)[0]; ax.add_collection(LineCollection([XY[i] for i in idx], colors=[col[i] for i in idx], linewidths=w_, zorder=4))


def ramp_bar(fig, rect, label, fs=9):
    ax = fig.add_axes(rect); ax.axis("off"); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    n = len(RAMP) - 1
    for i in range(200):
        u = i / 200; j = min(int(u * n), n - 1); t = u * n - j; d = RAMP[j][0] + (RAMP[j + 1][0] - RAMP[j][0]) * t
        ax.add_patch(Rectangle((u, .45), 1 / 200 * 1.05, .35, fc=ramp_rgb(d), ec="none"))
    for i, (d, _) in enumerate(RAMP):
        ax.text(i / n, .38, f"{d}{'+' if d == RMAX else ''}", ha="center", va="top", fontsize=fs)
    ax.text(0, .88, label, fontsize=fs, color=MUT, va="bottom")


# ---------- 1. side by side ----------
fig = plt.figure(figsize=(14, 7.6), facecolor=BG)
for i, (season, title) in enumerate((("winter", "Roads only (and winter)"), ("summer", "Road and sea, summer"))):
    ax = fig.add_axes([0.01 + i * .495, .11, .485, .76]); base(ax); draw_days(ax, season)
    ax.text(.02, .97, title, transform=ax.transAxes, fontproperties=DISPB, fontsize=15, va="top", color=FG, path_effects=halo)
    for kk in ("carthago", "alexandria", "london", "constantinople"):
        c = R["city"][kk]; xy = [x for x in CITIES if x[0] == kk][0][3]; x, y = proj(*xy)
        ax.plot(x, y, "o", ms=4.5, mfc=PAPER, mec=FG, mew=1.2, zorder=8)
fig.text(.01, .97, "Days on foot from Rome: roads only, and with the sea", fontproperties=DISPB, fontsize=19, va="top", color=FG)
fig.text(.01, .925, f"Carthage {R['city']['carthago']['winter_foot']:.0f} days by road, {R['city']['carthago']['summer_foot']:.0f} with a ship. Alexandria {R['city']['alexandria']['winter_foot']:.0f} and {R['city']['alexandria']['summer_foot']:.0f}. London {R['city']['london']['winter_foot']:.0f} and {R['city']['london']['summer_foot']:.0f}.", fontsize=10.5, color=MUT, va="top")
ramp_bar(fig, [.01, .015, .4, .07], "days on foot from Rome (land shading, road colour and, in summer, the sea)")
fig.text(.99, .02, "Roads: Itiner-e (CC BY 4.0). Ports: Pleiades. Sailing speeds: Casson (1951). Modelled times.", ha="right", fontsize=8.5, color=MUT)
save(fig, f"{BLOG}/b_side_by_side.png", dpi=170)

# ---------- 2. city dumbbell ----------
K = sorted(R["compare"], key=lambda c: -R["city"][c]["winter_foot"])
fig, ax = plt.subplots(figsize=(10, 6.6), facecolor=BG); ax.set_facecolor(BG)
y = np.arange(len(K))[::-1]
for yi, kk in zip(y, K):
    c = R["city"][kk]
    ax.plot([c["summer_foot"], c["winter_foot"]], [yi, yi], color=RULE, lw=3, zorder=2)
    ax.plot([c["summer_foot_min"], c["summer_foot_max"]], [yi, yi], color=ramp_rgb(c["summer_foot"]), lw=8, alpha=.45, zorder=3, solid_capstyle="butt")
    ax.plot(c["winter_foot"], yi, "o", ms=8, color="#9A9288", zorder=4)
    ax.plot(c["summer_foot"], yi, "o", ms=9, mfc=ramp_rgb(c["summer_foot"]), mec=FG, mew=.9, zorder=5)
    ax.text(c["winter_foot"] + 4, yi, f"{c['winter_foot']:.0f}", va="center", fontsize=9, color=MUT)
    ax.text(c["summer_foot"] - 4, yi, f"{c['summer_foot']:.0f}", va="center", ha="right", fontsize=9.5, color=FG, fontweight="medium")
ax.set_yticks(y); ax.set_yticklabels([R["city"][kk]["name"] for kk in K]); ax.set_xlim(-8, 245); style(ax)
ax.set_xlabel("days from Rome on foot (land legs)", color=MUT)
hs = [Line2D([], [], marker="o", ls="", color="#9A9288", ms=8, label="Roads only (and winter)"), Line2D([], [], marker="o", ls="", mfc=ramp_rgb(20), mec=FG, ms=9, label="Road and sea, summer (band: sensitivity range)")]
ax.legend(handles=hs, loc="lower right", frameon=False, fontsize=9.5)
ax.set_title("Road only against road and sea", loc="left", fontproperties=DISPB, fontsize=17, color=FG, pad=12)
fig.tight_layout(); save(fig, f"{BLOG}/b_cities.png", dpi=170)

# ---------- 3. validation ----------
V = TR["VAL"]; T1 = pd.DataFrame(R["table1_rows"])
fig, axs = plt.subplots(1, 2, figsize=(12.6, 6.4), facecolor=BG)
ticks = [1, 2, 5, 10, 20, 50]
for ax in axs:
    ax.set_facecolor(BG); ax.plot([1, 80], [1, 80], color=FG, ls="--", lw=1); ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlim(1, 80); ax.set_ylim(1, 80)
    ax.set_xticks(ticks); ax.set_xticklabels(ticks); ax.set_yticks(ticks); ax.set_yticklabels(ticks); ax.minorticks_off(); style(ax, axis="both"); ax.set_ylabel("days in the model", color=MUT)
ax = axs[0]
for col_, A_, lab_ in (("#B9B1A6", "modelA_days", f"slower model: {R['table1_A']['n_inside']} inside, {R['table1_A']['n_near']} within a quarter"),
                       ("#1F5F8B", "model_days", f"calibrated model: {R['table1_B']['n_inside']} inside, {R['table1_B']['n_near']} within a quarter")):
    for _, r in T1.iterrows():
        ax.plot([r.lo, max(r.hi, r.lo * 1.04)], [r[A_]] * 2, color=col_, lw=4, solid_capstyle="round", alpha=.85, zorder=3 if A_ == "model_days" else 2)
    ax.plot([], [], color=col_, lw=4, label=lab_)
ax.set_xlabel("days estimated by Casson (Table 1; bar = his range)", color=MUT); ax.legend(frameon=False, loc="upper left", fontsize=9.5)
ax.set_title(f"Casson's {R['table1_B']['n']} estimated passages", loc="left", fontproperties=DISPB, fontsize=15, color=FG, pad=10)
ax = axs[1]
for wind, col in (("favourable", "#1F5F8B"), ("unfavourable", HOT)):
    s_ = V[V.wind == wind]; ax.scatter(s_.reported_days, s_.model_days, s=46, color=col, alpha=.85, label=f"{wind} wind ({len(s_)})", zorder=3)
ax.set_xlabel("days reported (Casson 1951)", color=MUT); ax.legend(frameon=False, loc="upper left", fontsize=9.5)
ax.set_title(f"{R['validation']['n']} recorded voyages, calibrated model", loc="left", fontproperties=DISPB, fontsize=15, color=FG, pad=10)
fig.tight_layout(); save(fig, f"{BLOG}/b_validation.png", dpi=170)

# ---------- 4. shares ----------
fig, ax = plt.subplots(figsize=(10, 4.8), facecolor=BG); ax.set_facecolor(BG)
D = ["7", "14", "30"]; rows = [("winter_foot", "Roads only, on foot", "#9A9288", 1), ("summer_foot", "Road and sea, on foot", "#1F5F8B", 1),
                              ("winter_courier", "Roads only, courier", "#9A9288", .5), ("summer_courier", "Road and sea, courier", "#1F5F8B", .5)]
wdt = .2
for j, (kk, lab, col, al) in enumerate(rows):
    v = [R["area_share"][kk][d] * 100 for d in D]
    b = ax.bar(np.arange(3) + (j - 1.5) * wdt, v, wdt * .92, color=col, alpha=al, label=lab, zorder=3)
    for xx, vv in zip(np.arange(3) + (j - 1.5) * wdt, v):
        ax.text(xx, vv + 1.2, f"{vv:.0f}%" if vv >= 10 else f"{vv:.1f}%", ha="center", fontsize=8.5)
ax.set_xticks(range(3)); ax.set_xticklabels([f"within {d} days" for d in D]); ax.set_ylim(0, 100); style(ax, axis="y")
ax.set_ylabel("% of the provinces' land", color=MUT); ax.legend(frameon=False, fontsize=9, ncol=2, loc="upper left")
ax.set_title("How much of the empire was close to Rome", loc="left", fontproperties=DISPB, fontsize=16, color=FG, pad=10)
fig.tight_layout(); save(fig, f"{BLOG}/b_shares.png", dpi=170)

# ---------- 5. the wind model ----------
fig = plt.figure(figsize=(12, 8.2), facecolor=BG); ax = fig.add_axes([.01, .01, .98, .9]); ext2 = (proj(-6, 38)[0], proj(37, 38)[0], proj(16, 29.5)[1], proj(16, 46.5)[1]); base(ax, ext2)
bcol = {0: None, 1: "#BFD6E6", 2: "#D7E6EF", 3: "#C9DDEA"}
for b in (1, 2, 3):
    sel = SEAD["basin"] == b
    ax.scatter(SEAD["C_x"][sel], SEAD["C_y"][sel], s=6, marker="s", color=bcol[b], zorder=1.2, lw=0)
for b, to in SEAD["WIND_TO"].items():
    sel = np.where((SEAD["basin"] == b) & (SEAD["ix"] % 5 == 0) & (SEAD["iy"] % 5 == 0))[0]
    for i in sel:
        x, y = SEAD["C_x"][i], SEAD["C_y"][i]; dx, dy = np.sin(np.radians(to)) * 30000, np.cos(np.radians(to)) * 30000
        ax.annotate("", (x + dx, y + dy), (x - dx, y - dy), arrowprops=dict(arrowstyle="-|>", color="#1F5F8B", lw=1, mutation_scale=8), zorder=3)
px, py = proj(PT.lon.values, PT.lat.values); ax.scatter(px, py, s=10, color=FG, zorder=5)
# Rome to Alexandria and back, as routed by the model (sea only)
import scipy.sparse.csgraph as csg
sys.path.insert(0, os.path.join(ROOT, "code"))
def seapath(a_name, b_name):
    A, (U, Vv, W, TT) = TRB
    ia = k + int(PT.index[PT.name == a_name][0]); ib = k + int(PT.index[PT.name == b_name][0])
    d, pred = csg.dijkstra(A, directed=True, indices=ia, return_predecessors=True)
    path = [ib]
    while pred[path[-1]] >= 0: path.append(pred[path[-1]])
    pts = []
    for n in path[::-1]:
        if n >= k + npt: pts.append((SEAD["C_x"][n - k - npt], SEAD["C_y"][n - k - npt]))
        elif n >= k: pts.append(proj(PT.lon[n - k], PT.lat[n - k]))
    return np.array(pts), d[ib]
# rebuild the sea-only graph with the fitted parameters (same rules as step 3)
NS = {"__file__": os.path.join(ROOT, "code", "03_travel.py")}
exec(open(NS["__file__"]).read().split("V_UP = fit(63.0)")[0], NS)
TRB = NS["build"](MODES["foot"]["kmd"], season="summer", roads=False, **{k_: R["params"][k_] for k_ in ("v_down", "v_neu", "v_up", "v_up_e")})
out, d_out = seapath("Ostia", "Alexandria"); back, d_back = seapath("Alexandria", "Ostia")
ax.plot(out[:, 0], out[:, 1], color=HOT, lw=2.2, zorder=6)
ax.plot(back[:, 0], back[:, 1], color=FG, lw=2.2, ls=(0, (4, 2.5)), zorder=6)
hs = [Line2D([], [], color=HOT, lw=2.2, label=f"Ostia to Alexandria: {d_out:.0f} days (Casson: 10 to 13)"),
      Line2D([], [], color=FG, lw=2.2, ls=(0, (4, 2.5)), label=f"Alexandria to Ostia: {d_back:.0f} days (Casson: 53 to 73; the model is too quick)"),
      Line2D([], [], color="#1F5F8B", marker=r"$\rightarrow$", ls="", ms=12, label="summer wind (etesians)"),
      Line2D([], [], color=FG, marker="o", ls="", ms=4, label=f"port ({R['n_ports']})")]
lg = ax.legend(handles=hs, loc="lower left", fontsize=9.5, frameon=True); lg.get_frame().set_facecolor(PAPER); lg.get_frame().set_edgecolor(RULE)
fig.text(.01, .975, "The summer wind model: fast out, slower home", fontproperties=DISPB, fontsize=18, va="top", color=FG)
fig.text(.01, .935, f"Calibrated to Casson's Table 1: downwind {R['params']['v_down']:.1f} knots, no prevailing wind {R['params']['v_neu']:.1f}, dead into the wind {R['params']['v_up']:.1f} (central) and {R['params']['v_up_e']:.1f} (Aegean and Levant).", fontsize=10, color=MUT, va="top")
save(fig, f"{BLOG}/b_wind.png", dpi=170)

# ---------- header ----------
fig = plt.figure(figsize=(12, 6.3), facecolor=BG)
ax = fig.add_axes([0.38, 0.0, 0.62, 1.0]); ext3 = (proj(-10.5, 44)[0], proj(41, 44)[0], proj(16, 25)[1], proj(16, 56.5)[1]); base(ax, ext3); draw_days(ax, "summer", lw=(.25, .45))
fx = fig.add_axes([0, 0, .38, 1]); fx.axis("off"); fx.set_xlim(0, 1); fx.set_ylim(0, 1)
fx.text(.08, .86, "DATA STUDY · HISTORY", fontsize=10, color=HOT, fontweight="medium")
fx.text(.08, .80, "By road\nand by sea", fontproperties=DISP, fontsize=42, va="top", color=FG, linespacing=.95)
fx.text(.08, .47, "The fastest way from Rome\nto anywhere in the empire", fontsize=13, va="top", color=FG, family=SER, linespacing=1.3)
fx.text(.08, .30, f"Carthage {R['city']['carthago']['winter_foot']:.0f} days by road,\n{R['city']['carthago']['summer_foot']:.0f} with a ship\nAlexandria {R['city']['alexandria']['winter_foot']:.0f} days, or {R['city']['alexandria']['summer_foot']:.0f}", fontsize=11.5, va="top", color=FG, linespacing=1.45)
fx.text(.08, .05, "maps.tristanhotham.com/roman-travel-times", fontsize=9, color=MUT)
fig.savefig(os.path.join(ROOT, "header.png"), dpi=100, facecolor=BG); plt.close(fig)
for fn in os.listdir(BLOG):
    if fn.startswith("b_") and fn.endswith(".png"):
        shutil.copyfile(f"{BLOG}/{fn}", f"{PAP}/fig_{fn[2:]}")
print("figures done", d_out, d_back)
