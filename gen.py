"""Generate a 2-layer DuPont hub PCB for ESP32 + TUF-2000M + RS485 + 2x DS18B20.
Outputs Gerbers, drill files, BOM and CPL for PCBWay, plus a geometry dump for DRC."""
import json, math, os, csv, zipfile
from HersheyFonts import HersheyFonts

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
os.makedirs(OUT, exist_ok=True)

P = 2.54
X0 = 8.0                 # first top-row column
TOP_Y, BOT_Y = 10.0, 40.0
H = 50.0
PAD_D, DRILL = 1.7, 1.0
VIA_D, VIA_DRILL = 0.8, 0.4
POWER = {"12V", "5V", "GND", "3V3"}
W_PWR, W_SIG = 0.8, 0.4
BUS_ORDER = ["12V", "5V", "GND", "3V3", "TX", "RX", "DE", "D1", "D2", "A", "B"]
BUS_Y = {n: 15.0 + 2.0 * i for i, n in enumerate(BUS_ORDER)}

font = HersheyFonts(); font.load_default_font("futural")

def text_strokes(s, h):
    font.normalize_rendering(h)
    segs = list(font.lines_for_text(s))
    xs = [c for seg in segs for p in seg for c in (p[0],)]
    return segs, (max(xs) - min(xs) if xs else 0), (min(xs) if xs else 0)

TOP = [
    ("J1", "ESP32", [("5V", "5V"), ("GND", "GND"), ("3V3", "3V3"), ("IO18", "TX"), ("IO19", "RX"),
                     ("IO23", "DE"), ("IO17", "D1"), ("IO15", "D2")]),
    ("J2", "BOOST IN", [("IN+", "5V"), ("IN-", "GND")]),
    ("J3", "BOOST OUT", [("OUT+", "12V"), ("OUT-", "GND")]),
    ("J4", "METER PWR", [("12V", "12V"), ("GND", "GND")]),
]
BOT = [
    ("J5", "METER 485", [("A+", "A"), ("B-", "B")]),
    ("J6", "RS485 LOGIC", [("RO", "RX"), ("RE", "DE"), ("DE", "DE"), ("DI", "TX")]),
    ("J7", "RS485 PWR", [("VCC", "3V3"), ("B", "B"), ("A", "A"), ("GND", "GND")]),
    ("J8", "TEMP OUTLET", [("GND", "GND"), ("VCC", "3V3"), ("DATA", "D1")]),
    ("J9", "TEMP INLET", [("GND", "GND"), ("VCC", "3V3"), ("DATA", "D2")]),
]
NAME_H, LABEL_H = 1.1, 0.9
FEMALE = {"J8", "J9"}   # DS18B20 probes plug in directly

def place_row(groups, start):
    """Place groups on a 2.54 grid, leaving room for each group name."""
    placed, x = [], start
    prev_right = None
    for ref, name, pins in groups:
        _, nw, _ = text_strokes(name, NAME_H)
        span = (len(pins) - 1) * P
        # need group-name extents not to collide with previous one
        if prev_right is not None:
            center = x + span / 2
            while center - nw / 2 < prev_right + 1.2 or x - prev_last < 2 * P:
                x += P; center = x + span / 2
        cols = [x + i * P for i in range(len(pins))]
        placed.append((ref, name, pins, cols))
        prev_right = x + span / 2 + nw / 2
        prev_last = cols[-1]
        x = cols[-1] + P
    return placed, x

top_placed, top_next = place_row(TOP, X0)
bot_placed, bot_next = place_row(BOT, X0 + P / 2)

# resistors after J4 on the top grid: pad A on a column, pad B 1.9mm right, stub jogs to next column
res_x = top_next + P
RES = [("R1", "3V3", "D1", res_x), ("R2", "3V3", "D2", res_x + 3 * P)]
W = max(res_x + 3 * P + P + 6, bot_next + 4)
W = math.ceil(W)

pads, traces, vias, silk, cpl = [], [], [], [], []
# pads: dict(x,y,net,kind:'tht'|'smd',w,h,shape,ref)

def add_label_vertical(s, x, y_anchor, direction):
    """Vertical text centred on column x. direction=-1 grows towards y=0 (top band), +1 towards y=H."""
    segs, w, x0 = text_strokes(s, LABEL_H)
    for seg in segs:
        pts = []
        for (tx, ty) in seg:
            tx -= x0
            # rotate 90 deg: text baseline runs along y
            if direction < 0:   # read bottom-to-top, starts near pad and goes up (towards 0)
                px = x + (ty - LABEL_H / 2) * -1 + 0.0
                py = y_anchor - tx
            else:
                px = x + (ty - LABEL_H / 2) * -1
                py = y_anchor + w - tx
            pts.append((px, py))
        silk.append(pts)

def add_text(s, cx, cy, h):
    segs, w, x0 = text_strokes(s, h)
    for seg in segs:
        silk.append([(cx - w / 2 + (tx - x0), cy + h / 2 - ty) for tx, ty in seg])

for placed, row_y, band in ((top_placed, TOP_Y, -1), (bot_placed, BOT_Y, +1)):
    for ref, name, pins, cols in placed:
        for i, ((lab, net), x) in enumerate(zip(pins, cols)):
            pads.append(dict(x=x, y=row_y, net=net, kind="tht", d=PAD_D, square=(i == 0), ref=f"{ref}.{i+1}"))
            traces.append(dict(layer="F", net=net, pts=[(x, row_y), (x, BUS_Y[net])]))
            vias.append(dict(x=x, y=BUS_Y[net], net=net))
            if band < 0:
                add_label_vertical(lab, x, row_y - 1.6, -1)
            else:
                add_label_vertical(lab, x, row_y + 1.6, +1)
        cx = (cols[0] + cols[-1]) / 2
        if band < 0:
            add_text(name, cx, 2.2, NAME_H)
        else:
            add_text(name, cx, H - 2.2, NAME_H)
        cpl.append(dict(ref=ref, x=cx, y=row_y, rot=0 if band < 0 else 180, layer="Top",
                        desc=f"{'Female' if ref in FEMALE else 'Pin'} header 1x{len(pins)} 2.54mm",
                        n=len(pins), female=ref in FEMALE, side=band))
        # outline box around header
        x1, x2 = cols[0] - 1.4, cols[-1] + 1.4
        silk.append([(x1, row_y - 1.4), (x2, row_y - 1.4), (x2, row_y + 1.4), (x1, row_y + 1.4), (x1, row_y - 1.4)])

for ref, na, nb, xa in RES:
    xb = xa + 1.9
    pads.append(dict(x=xa, y=TOP_Y, net=na, kind="smd", w=1.0, h=1.3, ref=f"{ref}.1"))
    pads.append(dict(x=xb, y=TOP_Y, net=nb, kind="smd", w=1.0, h=1.3, ref=f"{ref}.2"))
    traces.append(dict(layer="F", net=na, pts=[(xa, TOP_Y), (xa, BUS_Y[na])]))
    vias.append(dict(x=xa, y=BUS_Y[na], net=na))
    xc = xa + P
    traces.append(dict(layer="F", net=nb, pts=[(xb, TOP_Y), (xb, TOP_Y + 1.6), (xc, TOP_Y + 2.2), (xc, BUS_Y[nb])]))
    vias.append(dict(x=xc, y=BUS_Y[nb], net=nb))
    add_text(ref, (xa + xb) / 2, 6.6, LABEL_H)
    add_text("4K7", (xa + xb) / 2, 4.4, LABEL_H)
    silk.append([(xa - 0.9, TOP_Y - 1.1), (xb + 0.9, TOP_Y - 1.1)])
    cpl.append(dict(ref=ref, x=(xa + xb) / 2, y=TOP_Y, rot=0, layer="Top", desc="4.7k 0805", n=0, side=-1))

# buses on bottom copper
for net in BUS_ORDER:
    xs = sorted({v["x"] for v in vias if v["net"] == net})
    if len(xs) >= 2:
        traces.append(dict(layer="B", net=net, pts=[(xs[0], BUS_Y[net]), (xs[-1], BUS_Y[net])]))

# title + mounting holes
add_text("TUF2000 HUB V1", W - 14, 20.0, 1.2) if False else None
HOLES = [(3.5, 3.5), (W - 3.5, 3.5), (3.5, H - 3.5), (W - 3.5, H - 3.5)]
HOLE_D = 3.2

def width(net):
    return W_PWR if net in POWER else W_SIG

json.dump(dict(W=W, H=H, pads=pads, traces=[dict(t, w=width(t["net"])) for t in traces], vias=vias,
               silk=silk, holes=HOLES, hole_d=HOLE_D, bus_y=BUS_Y), open(os.path.join(OUT, "geometry.json"), "w"))

# ---------------- Gerber writer ----------------
def fmt(v):
    return str(int(round(v * 1e6)))

def g(x, y):
    return f"X{fmt(x)}Y{fmt(H - y)}"

class Gerber:
    def __init__(self, name, func):
        self.name, self.lines, self.aps, self.next = name, [], {}, 10
        self.head = ["%TF.GenerationSoftware,claude,hubgen,1.0*%", f"%TF.FileFunction,{func}*%",
                     "%FSLAX46Y46*%", "%MOMM*%", "%LPD*%"]
    def ap(self, key, spec):
        if key not in self.aps:
            self.aps[key] = (self.next, spec); self.next += 1
        return f"D{self.aps[key][0]}"
    def flash(self, apcode, x, y):
        self.lines += [f"{apcode}*", f"{g(x, y)}D03*"]
    def path(self, apcode, pts):
        self.lines += [f"{apcode}*", f"{g(*pts[0])}D02*"] + [f"{g(*p)}D01*" for p in pts[1:]]
    def save(self):
        body = self.head + [f"%ADD{n}{spec}*%" for n, spec in self.aps.values()] + self.lines + ["M02*"]
        open(os.path.join(OUT, self.name), "w").write("\n".join(body) + "\n")

def copper(layer, fname, func):
    gb = Gerber(fname, func)
    for p in pads:
        if p["kind"] == "smd" and layer == "B":
            continue
        if p["kind"] == "tht":
            a = gb.ap(("sq" if p["square"] else "c", p["d"]),
                      f"R,{p['d']:.3f}X{p['d']:.3f}" if p["square"] else f"C,{p['d']:.3f}")
        else:
            a = gb.ap(("r", p["w"], p["h"]), f"R,{p['w']:.3f}X{p['h']:.3f}")
        gb.flash(a, p["x"], p["y"])
    for v in vias:
        gb.flash(gb.ap(("via",), f"C,{VIA_D:.3f}"), v["x"], v["y"])
    for t in traces:
        if t["layer"] == layer:
            w = width(t["net"])
            gb.path(gb.ap(("tr", w), f"C,{w:.3f}"), t["pts"])
    gb.save()

def mask(layer, fname, func):
    gb = Gerber(fname, func)
    e = 0.1
    for p in pads:
        if p["kind"] == "smd" and layer == "B":
            continue
        if p["kind"] == "tht":
            d = p["d"] + e
            a = gb.ap(("sq" if p["square"] else "c", d), f"R,{d:.3f}X{d:.3f}" if p["square"] else f"C,{d:.3f}")
        else:
            a = gb.ap(("r", p["w"] + e, p["h"] + e), f"R,{p['w']+e:.3f}X{p['h']+e:.3f}")
        gb.flash(a, p["x"], p["y"])
    for hx, hy in HOLES:
        gb.flash(gb.ap(("hole",), f"C,{HOLE_D + 0.2:.3f}"), hx, hy)
    gb.save()

def paste(fname):
    gb = Gerber(fname, "Paste,Top")
    for p in pads:
        if p["kind"] == "smd":
            gb.flash(gb.ap(("r", p["w"], p["h"]), f"R,{p['w']:.3f}X{p['h']:.3f}"), p["x"], p["y"])
    gb.save()

def silkscreen(fname):
    gb = Gerber(fname, "Legend,Top")
    a = gb.ap(("s",), "C,0.150")
    for pts in silk:
        gb.path(a, pts)
    gb.save()

def outline(fname):
    gb = Gerber(fname, "Profile,NP")
    r = 1.0
    a = gb.ap(("o",), "C,0.100")
    # rounded rectangle via line + arc approximations
    pts = []
    for cx, cy, a0 in ((W - r, r, -90), (W - r, H - r, 0), (r, H - r, 90), (r, r, 180)):
        for k in range(0, 91, 10):
            ang = math.radians(a0 + k)
            pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    pts.append(pts[0])
    gb.path(a, pts)
    gb.save()

def drill(fname, plated):
    tools = {}
    if plated:
        for p in pads:
            if p["kind"] == "tht":
                tools.setdefault(DRILL, []).append((p["x"], p["y"]))
        for v in vias:
            tools.setdefault(VIA_DRILL, []).append((v["x"], v["y"]))
    else:
        tools[HOLE_D] = HOLES
    lines = ["M48", "; DRILL file " + ("PTH" if plated else "NPTH"), "FMAT,2",
             "; TYPE=" + ("PLATED" if plated else "NON_PLATED"), "METRIC,TZ", "G90"]
    for i, d in enumerate(tools, 1):
        lines.append(f"T{i}C{d:.3f}")
    lines += ["%", "G05"]
    for i, (d, pts) in enumerate(tools.items(), 1):
        lines.append(f"T{i}")
        lines += [f"X{x:.3f}Y{H - y:.3f}" for x, y in pts]
    lines += ["T0", "M30"]
    open(os.path.join(OUT, fname), "w").write("\n".join(lines) + "\n")

copper("F", "hub-F_Cu.gtl", "Copper,L1,Top")
copper("B", "hub-B_Cu.gbl", "Copper,L2,Bot")
mask("F", "hub-F_Mask.gts", "Soldermask,Top")
mask("B", "hub-B_Mask.gbs", "Soldermask,Bot")
paste("hub-F_Paste.gtp")
silkscreen("hub-F_SilkS.gto")
outline("hub-Edge_Cuts.gm1")
drill("hub-PTH.drl", True)
drill("hub-NPTH.drl", False)

# ---------------- BOM + CPL ----------------
WURTH = {2: "61300211121", 3: "61300311121", 4: "61300411121", 8: "61300811121"}
WURTH_F = {3: "61300311821"}
groups = {}
for c in cpl:
    key = c["desc"]
    groups.setdefault(key, []).append(c)
with open(os.path.join(OUT, "hub-BOM.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Item", "Designator", "Qty", "Description", "Manufacturer", "Mfr Part Number",
                "Package", "Type", "Note"])
    for i, (desc, cs) in enumerate(groups.items(), 1):
        refs = ",".join(c["ref"] for c in cs)
        if cs[0]["n"]:
            n = cs[0]["n"]
            f = cs[0]["female"]
            w.writerow([i, refs, len(cs), f"{'Female socket' if f else 'Male pin'} header 1x{n}, 2.54mm, straight, gold",
                        "Wurth Elektronik", (WURTH_F if f else WURTH)[n], f"THT 1x{n} P2.54", "THT",
                        "Equivalent generic header OK"])
        else:
            w.writerow([i, refs, len(cs), "Resistor 4.7k 1% 1/8W", "Yageo", "RC0805FR-074K7L",
                        "0805", "SMD", "Equivalent OK"])
with open(os.path.join(OUT, "hub-CPL.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Designator", "Mid X(mm)", "Mid Y(mm)", "Layer", "Rotation"])
    for c in cpl:
        w.writerow([c["ref"], f"{c['x']:.3f}", f"{H - c['y']:.3f}", c["layer"], c["rot"]])

# JLCPCB assembly: XFCN PZ254V-11 headers + UNI-ROYAL basic-library resistor
LCSC_HDR = {2: "C492401", 3: "C2937625", 4: "C2691448", 8: "C492407"}
LCSC_HDR_F = {3: "C146243"}   # BOOMELE 2.54-1*3PFemale
with open(os.path.join(OUT, "hub-BOM-JLCPCB.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
    for desc, cs in groups.items():
        refs = ",".join(c["ref"] for c in cs)
        n = cs[0]["n"]
        if n:
            if cs[0]["female"]:
                w.writerow([f"Female header 1x{n} 2.54mm", refs, f"HDR-TH_{n}P-P2.54-V-F", LCSC_HDR_F[n]])
            else:
                w.writerow([f"Pin header 1x{n} 2.54mm", refs, f"HDR-TH_{n}P-P2.54-V-M", LCSC_HDR[n]])
        else:
            w.writerow(["4.7k", refs, "R0805", "C17673"])
with open(os.path.join(OUT, "hub-CPL-JLCPCB.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
    for c in cpl:
        w.writerow([c["ref"], f"{c['x']:.3f}mm", f"{H - c['y']:.3f}mm", c["layer"], c["rot"]])

with zipfile.ZipFile(os.path.join(OUT, "tuf2000-hub-gerbers.zip"), "w") as z:
    for fn in sorted(os.listdir(OUT)):
        if fn.startswith("hub-") and not fn.endswith(".csv"):
            z.write(os.path.join(OUT, fn), fn)
print(f"board {W} x {H} mm, pads {len(pads)}, vias {len(vias)}")
