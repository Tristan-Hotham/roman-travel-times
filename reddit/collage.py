"""Reddit collage (r/dataisbeautiful style): the Roman Empire twice, side by side. Left, days on foot from Rome by road
alone; right, the fastest way by road and sea in summer, with the sea shaded by days and the sea routes to four cities
drawn. Labels sit only on unshaded sea (left map) or on the paper, with a halo. Checks at render time assert that no
label touches land, a road, a route line or another label, and that no leader line crosses a label.
Run: python3 reddit/collage.py   (after code/01 to 07)
"""
import os, sys, pickle
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "code"))
from figlib import *
import matplotlib.patheffects as pe
from matplotlib.patches import Rectangle
from shapely.geometry import Polygon, Point, LineString as LS, box as sbox
from shapely.ops import unary_union as uu, nearest_points
from shapely.strtree import STRtree

N = pickle.load(open(f"{WORK}/net.pkl", "rb")); SEAD = pickle.load(open(f"{WORK}/sea.pkl", "rb")); TR = pickle.load(open(f"{WORK}/travel.pkl", "rb"))
RS = pickle.load(open(f"{WORK}/rasters.pkl", "rb")); R = jload(f"{DATA}/results.json")
S = N["S"]; T = TR["T"]; k, npt = TR["k"], TR["npt"]; PT = SEAD["ports"]; C = R["city"]
OUT = os.path.join(ROOT, "reddit", "roman_travel_road_vs_sea.png")
XY = road_xy(S, simplify=0.004)
EXT = empire_extent()
W_IN, DPI = 15, 200
PW = 7.35; PH = PW * (EXT[3] - EXT[2]) / (EXT[1] - EXT[0])
TOP_IN, BOT_IN = 1.8, 2.05
H_IN = TOP_IN + PH + BOT_IN
fig = plt.figure(figsize=(W_IN, H_IN), facecolor=BG)
yb = lambda inch: inch / H_IN
halo = [pe.withStroke(linewidth=4, foreground=PAPER)]


def rgba(D, alpha, dist=None):
    fin = np.isfinite(D); rgb = ramp_rgb(np.where(fin, D, 0)); rgb[~fin & ~np.isnan(D)] = (.62, .6, .56)
    a = np.where(np.isnan(D), 0, alpha)
    if dist is not None:
        a = a * np.clip(1 - (dist - 30) / 25, .35, 1)
    return np.dstack([rgb, a])


def panel(x0, season):
    ax = fig.add_axes([x0 / W_IN, yb(BOT_IN), PW / W_IN, PH / H_IN])
    ax.set_facecolor(SEA); draw_land(ax, lw=.45)
    ax.set_xlim(EXT[0], EXT[1]); ax.set_ylim(EXT[2], EXT[3]); ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values(): s.set_color(RULE)
    if season == "summer":
        ax.imshow(rgba(RS["sea"], .62 * RS["seafade"]), extent=RS["ext"], origin="upper", zorder=1.5, interpolation="bilinear")
    ax.imshow(rgba(RS[season], .38, RS["dist"]), extent=RS["ext"], origin="upper", zorder=2, interpolation="bilinear")
    w = S.km.values / (MODES["foot"]["kmd"] * S.pas.values); t = T[(season, "foot")]
    mid = np.minimum(t[S.u.values] + w / 2, t[S.v.values] + w / 2)
    col = [tuple(ramp_rgb(d)) if np.isfinite(d) else (.55, .53, .5) for d in mid]
    main = (S.type == "Main Road").values
    for sel, lw in ((~main, .28), (main, .5)):
        idx = np.where(sel)[0]; ax.add_collection(LineCollection([XY[i] for i in idx], colors=[col[i] for i in idx], linewidths=lw, zorder=4))
    return ax


GAP = (W_IN - 2 * PW) / 3
axL = panel(GAP, "winter"); axR = panel(2 * GAP + PW, "summer")

# routes by road and sea to the four headline cities on the right map (from the model's predecessors)
SC = TR["SC"][("summer", "foot")]; t_, pred, (U, Vv, W, TT) = SC
lk = {(u, v): ty for u, v, ty in zip(U, Vv, TT)}


def ptxy(n):
    if n < k: return proj(N["nodes"].lon[n], N["nodes"].lat[n])
    if n < k + npt: return proj(PT.lon[n - k], PT.lat[n - k])
    return SEAD["C_x"][n - k - npt], SEAD["C_y"][n - k - npt]


route_lines = []
for key in HEADLINE:
    n = TR["CITY_N"][key]; seq = [n]
    while pred[seq[-1]] >= 0: seq.append(pred[seq[-1]])
    seq = seq[::-1]; cur = []; kind = None
    for a, b in zip(seq[:-1], seq[1:]):
        kk = "sea" if lk[(a, b)] >= 3 else "road"
        if kk != kind and cur:
            route_lines.append((kind, np.array(cur))); cur = []
        if not cur: cur = [ptxy(a)]
        cur.append(ptxy(b)); kind = kk
    if cur: route_lines.append((kind, np.array(cur)))
for kind, xy in route_lines:
    axR.plot(xy[:, 0], xy[:, 1], color=PAPER, lw=4.2, zorder=6, solid_capstyle="round")
    axR.plot(xy[:, 0], xy[:, 1], color="#14466B" if kind == "sea" else FG, lw=2, zorder=7, ls=(0, (3, 2)) if kind == "sea" else "solid")
for ax in (axL, axR):
    for key, _, _, xy in CITIES:
        if key in HEADLINE + ["rome"]:
            x, y = proj(*xy); ax.plot(x, y, "o", ms=6.5, mfc=PAPER, mec=FG, mew=1.5, zorder=9)

# ---------- labels on the left map (unshaded sea), with checks ----------
landpoly = uu([Polygon(r[0], r[1:]) for r in land_rings("50m")])
rl = [LS(xy) for xy in XY if len(xy) > 1]; rtree = STRtree(rl)
mapbox = sbox(EXT[0], EXT[2], EXT[1], EXT[3]).buffer(-60000)
fig.canvas.draw(); rend = fig.canvas.get_renderer(); inv = axL.transData.inverted()
boxes, leaders, MISSING = {}, {}, []
dots = {key: proj(*xy) for key, _, _, xy in CITIES if key in HEADLINE + ["rome"]}


def dbox(t, pad=3):
    bb = t.get_window_extent(rend); (x0, y0), (x1, y1) = inv.transform([[bb.x0 - pad, bb.y0 - pad], [bb.x1 + pad, bb.y1 + pad]])
    return sbox(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def ok_box(b, key):
    if os.environ.get("DBG") == key:
        print(key, round(b.bounds[2]-b.bounds[0]), round(b.bounds[3]-b.bounds[1]), mapbox.contains(b), b.intersects(landpoly), any(rl[i].intersects(b) for i in rtree.query(b)), [o for o, bb in boxes.items() if b.intersects(bb)], [o for o, L_ in leaders.items() if L_.intersects(b)], [kk for kk, d in dots.items() if kk != key and Point(d).buffer(25000).intersects(b)], [round(v, 1) for v in INV.transform(*b.centroid.coords[0])])
    if not mapbox.contains(b) or b.intersects(landpoly) or any(rl[i].intersects(b) for i in rtree.query(b)):
        return False
    if any(b.intersects(o) for o in boxes.values()) or any(L_.intersects(b) for L_ in leaders.values()):
        return False
    return not any(Point(d).buffer(25000).intersects(b) for kk, d in dots.items() if kk != key)


def place(key, txt, fs, anchor, radii=range(60, 1100, 15)):
    t = axL.text(0, 0, txt, ha="center", va="center", fontsize=fs, color=FG, zorder=10, path_effects=halo, linespacing=1.15, family=SER, fontweight="semibold")
    for rkm in radii:
        for ang in np.linspace(0, 2 * np.pi, 36, endpoint=False):
            t.set_position((anchor[0] + rkm * 1000 * np.cos(ang), anchor[1] + rkm * 1000 * np.sin(ang))); b = dbox(t)
            if not ok_box(b, key):
                continue
            p = nearest_points(b, Point(anchor))[0]; L_ = LS([anchor, (p.x, p.y)])
            if any(L_.intersects(o) for o in boxes.values()):
                continue
            boxes[key] = b; leaders[key] = L_
            return t
    t.remove(); MISSING.append(key)


LAB = {"rome": "ROMA", "london": "LONDINIUM", "constantinople": "BYZANTIUM", "alexandria": "ALEXANDRIA", "carthago": "CARTHAGO"}
for key in ["carthago", "alexandria", "constantinople", "london", "rome"]:
    c = C[key]
    txt = LAB[key]
    place(key, txt, 10.5, dots[key], radii=range(40, 900, 12))
for key, L_ in leaders.items():
    (x0, y0), (x1, y1) = L_.coords
    if Point(x0, y0).distance(Point(x1, y1)) > 1000:
        axL.plot([x0, x1], [y0, y1], color=FG, lw=.9, zorder=8)
BAD = []
for key, b in boxes.items():
    if b.intersects(landpoly): BAD.append(("label on land", key))
    if any(rl[i].intersects(b) for i in rtree.query(b)): BAD.append(("label over a road", key))
    for k2, b2 in boxes.items():
        if k2 != key and b.intersects(b2): BAD.append(("labels overlap", key, k2))
    for k2, L_ in leaders.items():
        if k2 != key and L_.intersects(b): BAD.append(("leader crosses label", k2, key))

# ---------- titles, panel heads on paper ----------
yt = lambda inch: 1 - inch / H_IN
fig.text(GAP / W_IN, yt(.2), "ALL ROADS LEAD TO ROME, BUT THE SEA WAS QUICKER", fontsize=12, color=HOT, fontweight="medium", va="top")
fig.text(GAP / W_IN, yt(.42), f"Carthage was {C['carthago']['winter_foot']:.0f} days' walk from Rome by road, and {C['carthago']['summer_foot']:.0f} days with a ship",
         fontproperties=DISPB, fontsize=25, va="top", color=FG)
fig.text(GAP / W_IN, yt(.92), "Modelled fastest journey from Rome, on foot on land, over the 299,171 km of road in Itiner-e and, in summer, by ship\nbetween "
         f"{R['n_ports']} ancient ports, at sailing speeds from Casson's ancient voyage reports and with the summer etesian winds.",
         fontsize=10.5, va="top", color=MUT, family=SER)
for x0, txt in ((GAP, "Roads only (and winter, when the sea was closed)"), (2 * GAP + PW, "Road and sea, summer: sea shaded by days, routes drawn")):
    fig.text(x0 / W_IN, yb(BOT_IN + PH) + .006, txt, fontsize=12.5, va="bottom", color=FG, fontweight="medium")

# ---------- legend band ----------
lx = fig.add_axes([GAP / W_IN, yb(.25), 0.4, yb(1.45)]); lx.axis("off"); lx.set_xlim(0, 1); lx.set_ylim(0, 1)
n_ = len(RAMP) - 1
for i in range(300):
    u = i / 300; j = min(int(u * n_), n_ - 1); tt = u * n_ - j; d = RAMP[j][0] + (RAMP[j + 1][0] - RAMP[j][0]) * tt
    lx.add_patch(Rectangle((u * .95, .66), .95 / 300 * 1.05, .13, fc=ramp_rgb(d), ec="none"))
for i, (d, _) in enumerate(RAMP):
    lx.text(i / n_ * .95, .61, f"{d}{'+' if d == RAMP[-1][0] else ''}", ha="center", va="top", fontsize=10)
lx.text(0, .85, "Days from Rome: road colour, land shading and (right) sea shading", fontsize=10.5, va="bottom", color=FG, fontweight="medium")
lx.plot([0, .06], [.26, .26], color=FG, lw=2); lx.text(.075, .26, "route by road", va="center", fontsize=9.5)
lx.plot([.32, .38], [.26, .26], color="#14466B", lw=2, ls=(0, (3, 2))); lx.text(.395, .26, "route by sea", va="center", fontsize=9.5)
lx.add_patch(Rectangle((.66, .19), .045, .14, fc=(.62, .6, .56), alpha=.7, ec="none")); lx.text(.715, .26, "no road link", va="center", fontsize=9.5)
lx.plot([0, .06], [.04, .04], color=FG, lw=2.2, alpha=.0); lx.plot(.03, .04, "o", ms=7, mfc=PAPER, mec=FG, mew=1.5); lx.text(.075, .04, "Rome and four cities", va="center", fontsize=9.5)

bx = fig.add_axes([0.50, yb(.42), 0.25, yb(1.2)]); bx.set_facecolor(BG)
ks = ["carthago", "alexandria", "london", "constantinople"]
for i, key in enumerate(ks):
    c = C[key]; y0 = (3 - i)
    bx.barh(y0 + .19, c["winter_foot"], height=.3, color="#9A9288", zorder=3); bx.barh(y0 - .19, c["summer_foot"], height=.3, color=ramp_rgb(c["summer_foot"]), zorder=3)
    bx.text(c["winter_foot"] + 3, y0 + .19, f"{c['winter_foot']:.0f} road", va="center", fontsize=8.2); bx.text(c["summer_foot"] + 3, y0 - .19, f"{c['summer_foot']:.0f} road and sea", va="center", fontsize=8.2)
bx.set_yticks(range(4)[::-1]); bx.set_yticklabels([C[key]["name"].replace(" (Istanbul)", "") for key in ks], fontsize=9.5); bx.set_xlim(0, 270)
bx.tick_params(axis="x", labelsize=8.5, colors=MUT)
for s_ in ("top", "right"): bx.spines[s_].set_visible(False)
for s_ in ("left", "bottom"): bx.spines[s_].set_color(MUT)
bx.set_title("Days on foot: road only, and with the sea", fontsize=10, loc="left", color=FG, fontweight="medium")
fig.text(.785, yb(1.85), "Sources and model", fontsize=10, color=FG, fontweight="medium", va="top")
fig.text(.785, yb(1.66), f"Roads: Itiner-e 2024, de Soto, Pažout,\nBrughmans et al. (2025), CC BY 4.0.\nPorts: Pleiades (CC BY 3.0) and DARE.\nSailing: Casson (1951), calibrated to his\nTable 1: {R['params']['v_down']:.1f} knots downwind, {R['params']['v_neu']:.1f} with\nno prevailing wind; 1 day to board.\nLand: Natural Earth. Modelled times.", fontsize=8.4, color=MUT, va="top", linespacing=1.3)
fig.text(.785, yb(.1), "maps.tristanhotham.com/roman-travel-times", fontsize=8.4, color=HOT, va="bottom", fontweight="medium")
fig.savefig(OUT, dpi=DPI, facecolor=BG)
print(OUT)
assert not BAD, BAD
assert not MISSING, MISSING
print("label checks passed")
