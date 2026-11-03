import json, sys, itertools
from shapely.geometry import Point, LineString, box
from shapely.ops import unary_union

G = json.load(open(sys.argv[1]))
W, H = G["W"], G["H"]
errs = []

def pad_shape(p):
    if p["kind"] == "tht":
        return box(p["x"] - p["d"]/2, p["y"] - p["d"]/2, p["x"] + p["d"]/2, p["y"] + p["d"]/2) if p["square"] \
            else Point(p["x"], p["y"]).buffer(p["d"]/2)
    return box(p["x"] - p["w"]/2, p["y"] - p["h"]/2, p["x"] + p["w"]/2, p["y"] + p["h"]/2)

items = {"F": [], "B": []}   # (net, shape, id)
for p in G["pads"]:
    s = pad_shape(p)
    items["F"].append((p["net"], s, p["ref"]))
    if p["kind"] == "tht":
        items["B"].append((p["net"], s, p["ref"]))
for i, v in enumerate(G["vias"]):
    s = Point(v["x"], v["y"]).buffer(0.4)
    for L in "FB":
        items[L].append((v["net"], s, f"via{i}"))
for i, t in enumerate(G["traces"]):
    items[t["layer"]].append((t["net"], LineString(t["pts"]).buffer(t["w"]/2), f"tr{i}"))

# clearance between different nets
CLR = 0.2
for L, its in items.items():
    for (n1, s1, a), (n2, s2, b) in itertools.combinations(its, 2):
        if n1 != n2:
            d = s1.distance(s2)
            if d < CLR:
                errs.append(f"{L}: clearance {d:.3f} {a}({n1}) vs {b}({n2})")
# edge + holes
edge = box(0, 0, W, H).exterior
holes = [Point(x, y).buffer(G["hole_d"]/2) for x, y in G["holes"]]
for L, its in items.items():
    for n, s, a in its:
        if s.distance(edge) < 0.3:
            errs.append(f"{L}: {a} too close to edge")
        if not box(0, 0, W, H).contains(s):
            errs.append(f"{L}: {a} outside board")
        for h in holes:
            if s.distance(h) < 0.4:
                errs.append(f"{L}: {a} too close to mounting hole")

# connectivity: each net single component across layers
nets = {}
for L, its in items.items():
    for n, s, a in its:
        nets.setdefault(n, []).append((L, s, a))
pad_nets = {}
for p in G["pads"]:
    pad_nets.setdefault(p["net"], []).append(p["ref"])
for n, lst in nets.items():
    # union-find on items touching on same layer, plus same id across layers (vias/tht)
    parent = list(range(len(lst)))
    def f(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    for i, j in itertools.combinations(range(len(lst)), 2):
        (L1, s1, a1), (L2, s2, a2) = lst[i], lst[j]
        if (L1 == L2 and s1.intersects(s2)) or (a1 == a2):
            parent[f(i)] = f(j)
    comps = {f(i) for i in range(len(lst))}
    if len(comps) != 1:
        errs.append(f"net {n} split into {len(comps)} pieces")

# silk over exposed copper
silk = unary_union([LineString(s).buffer(0.075) for s in G["silk"] if len(s) > 1])
for p in G["pads"]:
    if silk.distance(pad_shape(p).buffer(0.05)) < 0.1:
        errs.append(f"silk too close to pad {p['ref']}")
for h in holes:
    if silk.distance(h) < 0.3:
        errs.append("silk over mounting hole")
if not box(0.3, 0.3, W-0.3, H-0.3).contains(silk):
    errs.append("silk too close to board edge")

# expected netlist from the wiring diagram
EXPECT = {
    "5V": {"J1.1", "J2.1"}, "12V": {"J3.1", "J4.1"},
    "GND": {"J1.2", "J2.2", "J3.2", "J4.2", "J7.4", "J8.1", "J9.1"},
    "3V3": {"J1.3", "J7.1", "J8.2", "J9.2", "R1.1", "R2.1"},
    "TX": {"J1.4", "J6.4"}, "RX": {"J1.5", "J6.1"}, "DE": {"J1.6", "J6.2", "J6.3"},
    "D1": {"J1.7", "J8.3", "R1.2"}, "D2": {"J1.8", "J9.3", "R2.2"},
    "A": {"J5.1", "J7.3"}, "B": {"J5.2", "J7.2"},
}
got = {n: set(v) for n, v in pad_nets.items()}
if got != EXPECT:
    errs.append(f"netlist mismatch: {got} vs {EXPECT}")

print("\n".join(errs) if errs else "DRC OK: clearances, edge, holes, silk, connectivity and netlist all pass")
