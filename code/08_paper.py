"""Step 8. Paper PDF: fill code/paper_template.tex from data/results.json (with three tables built here), write
release/paper/Hotham_By_Road_and_by_Sea.tex and compile it with xelatex (figures from step 6). The DOI line keeps the
publisher's 10.5281/zenodo.23863542 placeholder unless ROMAN_DOI is set.
Run: python3 code/08_paper.py
"""
import os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *

R = jload(f"{DATA}/results.json")
OUT = os.path.join(ROOT, "release", "paper"); NAME = "Hotham_By_Road_and_by_Sea"
DOI = os.environ.get("ROMAN_TRAVEL_DOI", "10.5281/zenodo.23863542")
tex = lambda s: str(s).replace("&", "\\&").replace("%", "\\%").replace("_", "\\_").replace("#", "\\#")


def ffmt(v, f):
    if f == "pct": return f"{round(v * 100)}\\%"
    if f == "pct1": return f"{v * 100:.1f}\\%"
    if f in (None, "raw"): return tex(v)
    return fmt(v, f)


rows = []
for k in R["compare"]:
    c = R["city"][k]
    rows.append(f"{tex(c['name'])} & {c['winter_foot']:.0f} & {c['summer_foot']:.1f} & {c['summer_foot_min']:.0f} to {c['summer_foot_max']:.0f} & {c['modelA_foot']:.1f} & {c['winter_courier']:.0f} & {c['summer_courier']:.1f} & {tex(c['ports_from'][0]) if c['ports_from'] else ''}\\\\")
T_CITIES = ("\\begin{table}[tbp]\\centering\\small\\caption{Modelled days from Rome: roads only (and winter) against road and sea in summer, on foot and by courier on land. Road and sea: model B. Range: the sensitivity tests, model A included. Model A: road and sea with Casson's median speeds. Port: where the ship is boarded.}\\label{tab:cities}"
            "\\begin{tabular}{lrrrrrrl}\\toprule & \\multicolumn{4}{c}{On foot} & \\multicolumn{2}{c}{Courier} & \\\\ City & Road & Road and sea & Range & Model A & Road & Road and sea & Port\\\\\\midrule\n" + "\n".join(rows) + "\n\\bottomrule\\end{tabular}\\end{table}")
rows = []
for c in R["closest_ratio"][:10]:
    rows.append(f"{tex(c['name'])} & {tex(c['modern'])} & {c['road']:.0f} & {c['sea']:.1f} & {c['ratio']:.1f}\\\\")
T_CLOSEST = ("\\begin{table}[tbp]\\centering\\small\\caption{The major places the sea brought closest to Rome (days on foot; places at least 10 days from Rome by road).}\\label{tab:closest}"
             "\\begin{tabular}{llrrr}\\toprule Place & Modern & Road & Road and sea & Times quicker\\\\\\midrule\n" + "\n".join(rows) + "\n\\bottomrule\\end{tabular}\\end{table}")

ab = [r for r in R["table1_rows"] if r["from"] == "Alexandria" and r["to"] == "Byzantium"][0]
assert (ab["lo"], ab["hi"], f"{ab['model_days']:.1f}", round(ab["modelA_days"])) == (17, 20, "16.5", 59), ab   # quoted in the text
assert 0.4 < R["table1_returns"]["median_ratio_B"] < 0.6   # "about twice as quick"
A_, B_, P_ = R["table1_A"], R["table1_B"], R["params"]
mrow = lambda lab, a, b: f"{lab} & {a} & {b}\\\\"
T_MODELS = ("\\begin{table}[tbp]\\centering\\small\\caption{The two sea models: speeds (knots) and fit to Casson (1951). Inside: the model's time is within Casson's range; near: within a quarter of it. Ratios are model time over the middle of his range (Table 1) or over the reported time (voyages).}\\label{tab:models}"
            "\\begin{tabular}{lrr}\\toprule & Model A (medians) & Model B (calibrated)\\\\\\midrule\n" + "\n".join([
    mrow("Downwind speed", f"{P_['A']['v_down']:.1f}", f"{P_['v_down']:.1f}"),
    mrow("No prevailing wind", f"{P_['A']['v_neu']:.2f}", f"{P_['v_neu']:.1f}"),
    mrow("Into the wind, central basin", f"{P_['A']['v_up']:.2f}", f"{P_['v_up']:.1f}"),
    mrow("Into the wind, Aegean and Levant", f"{P_['A']['v_up_e']:.2f}", f"{P_['v_up_e']:.1f}"),
    mrow("Ostia to Alexandria (days; Casson 10 to 13)", f"{P_['A']['ostia_alex_days']:.1f}", f"{P_['ostia_alex_days']:.1f}"),
    mrow("Alexandria to Ostia (days; Casson 53 to 73)", f"{P_['A']['alex_ostia_days']:.1f}", f"{P_['alex_ostia_days']:.1f}"),
    "\\midrule",
    mrow(f"Table 1 passages inside his range (of {B_['n']})", f"{A_['n_inside']} ({A_['inside'] * 100:.0f}\\%)", f"{B_['n_inside']} ({B_['inside'] * 100:.0f}\\%)"),
    mrow("Table 1 passages inside or near", f"{A_['n_near']} ({A_['near'] * 100:.0f}\\%)", f"{B_['n_near']} ({B_['near'] * 100:.0f}\\%)"),
    mrow("Table 1 median ratio", f"{A_['median_ratio']:.2f}", f"{B_['median_ratio']:.2f}"),
    mrow(f"Table 1 long voyages home from the east ({R['table1_returns']['n']}), median ratio", f"{R['table1_returns']['median_ratio_A']:.2f}", f"{R['table1_returns']['median_ratio_B']:.2f}"),
    mrow(f"Recorded voyages ({R['validation']['n']}), median ratio", f"{R['validation_A']['median_ratio']:.2f}", f"{R['validation']['median_ratio']:.2f}")]) +
            "\n\\bottomrule\\end{tabular}\\end{table}")


def sub(m):
    k = m.group(1)
    if k.startswith("TABLE_"):
        return {"TABLE_CITIES": T_CITIES, "TABLE_CLOSEST": T_CLOSEST, "TABLE_MODELS": T_MODELS}[k]
    return ffmt(get(R, k), m.group(3))


src = open(os.path.join(ROOT, "code", "paper_template.tex"), encoding="utf-8").read()
out = re.sub(r"\{\{([^{}|]+)(\|(\w+))?\}\}", sub, src).replace("DOIVALUE", DOI)
assert "{{" not in out.replace("10.5281/zenodo.23863542", "")
body = re.sub(r"(?m)^%.*$", "", out)
for bad in ("—", "–", "DSIT", "DCMS", "--"):
    assert bad not in body, bad
os.makedirs(OUT, exist_ok=True)
open(f"{OUT}/{NAME}.tex", "w", encoding="utf-8").write(out)
for _ in range(2):
    r = subprocess.run(["xelatex", "-interaction=nonstopmode", f"{NAME}.tex"], cwd=OUT, capture_output=True, text=True)
pdf = f"{OUT}/{NAME}.pdf"
assert os.path.exists(pdf), r.stdout[-3000:]
n = int(re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout).group(1))
txt = subprocess.run(["pdftotext", pdf, "-"], capture_output=True, text=True).stdout
for bad in ("—", "–", "??"):
    assert bad not in txt, ("pdf", bad)
print(NAME, n, "pages")
assert 8 <= n <= 15, n
for ext in ("aux", "log", "out"):
    if os.path.exists(f"{OUT}/{NAME}.{ext}"):
        os.remove(f"{OUT}/{NAME}.{ext}")
