#!/usr/bin/env python3
"""Generate the 15 traffic-flow files (5 density levels x 3 lane counts).

Single source of truth: the manuscript's **Table I** densities
(``paper/submitted/overleaf/.../main.tex`` lines 101-130, unit
``veh/(h*lane)``) together with the Gaussian headway of Eq. (1) in the same
file. Structure and every non-demand attribute are copied from
``scenarios/original/routes.rou.xml`` so that only the demand changes.

Conversion rule (author decision, 2026-11-07)
---------------------------------------------
* Table I gives two densities per level, both in ``veh/(h*lane)``:
  ``S`` for straight-through traffic and ``L = R`` for *each* turning
  direction (the ``L&R`` column); ``L : S : R = 1 : 2 : 1`` by construction;
* per approach and per direction the mean headway is Eq. (1) of the paper:
  ``mu = 3600 / (n_lanes * density)``  [s];
* the vehicle count follows from the 1000 s horizon:
  ``number = round(1000 / mu)`` (so ``number x mu`` stays ~1000 s);
* the spread of the Gaussian headway keeps the value used by the original file
  (``normal(mu, 1.0)``); the advisory at the end lists the files where this
  produces negative draws.

**Regenerated 2026-11-07.** The previous version derived the counts from
``scenarios/original/routes.txt`` (an untracked author memo) and therefore
realised 468/612/756/972/1188 veh/(h*lane) on the 2- and 4-lane networks
instead of Table I's 480/600/768/960/1200. The densities are now taken from
the manuscript, so all three lane configurations realise the *same* per-lane
demand — which is exactly what the paper claims. ``routes.txt`` is only
cross-checked (level ordering), never used as input.

Output: ``scenarios/flows/lanes{L}_density{D}.rou.xml`` (15 files).

Usage (from anywhere):
    python3 scenarios/flows/generate_flows.py
"""

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE_ROU = ROOT / "scenarios" / "original" / "routes.rou.xml"
OUT_DIR = ROOT / "scenarios" / "flows"
ROUTES_TXT = ROOT / "scenarios" / "original" / "routes.txt"   # cross-check only

HORIZON = 1000.0    # s, simulation window of every flow (main.tex line 491)
SIGMA = 1.0         # headway spread, same convention as routes.rou.xml
OPPOSITE = {("north", "south"), ("south", "north"),
            ("east", "west"), ("west", "east")}

# L : S : R parts.  1:2:1 is Table I / the manuscript ratio; the other two are
# the R1 turning-ratio sensitivity groups (author decision 2026-11-14).
RATIOS = {"121": (1, 2, 1), "111": (1, 1, 1), "122": (1, 2, 2)}

COMPASS = {"north": "N", "south": "S", "east": "E", "west": "W"}
# right-hand traffic: turning "to the right" is clockwise, i.e. N->W, W->S, ...
RIGHT_TURNS = {("N", "W"), ("W", "S"), ("S", "E"), ("E", "N")}

# Manuscript Table I (main.tex lines 101-120), unit veh/(h*lane).
# level -> (density of EACH turning direction, straight-through density)
TABLE1 = {
    1: (240, 480),      # MinD
    2: (300, 600),      # LowD
    3: (384, 768),      # MedD
    4: (480, 960),      # HigD
    5: (600, 1200),     # MaxD
}


def density_cell(level):
    """lanes -> headway / count / density for straight and for each turning way.

    ``mu = 3600 / (n_lanes * density)`` is the mean departure headway of
    Eq. (1) in the manuscript, so the realised per-lane demand equals Table I
    by construction; ``number`` only rounds the 1000 s horizon to vehicles.
    """
    turn_density, straight_density = TABLE1[level]
    cells = {}
    for lanes in (2, 3, 4):
        mu_s = 3600.0 / (lanes * straight_density)
        mu_t = 3600.0 / (lanes * turn_density)
        cells[lanes] = {
            "mu_straight": mu_s,
            "mu_turn": mu_t,
            "n_straight": int(round(HORIZON / mu_s)),
            "n_turn": int(round(HORIZON / mu_t)),
            "straight_density": straight_density,
            "turn_density": turn_density,
        }
    return cells


def ratio_cell(level, lanes, ratio="121"):
    """Per-direction headway/count for one (level, lanes, L:S:R) cell.

    The **total** approach demand is held at the Table I 1:2:1 value
    ``lanes * (S + 2 * turn)`` veh/h, so a different ratio measures turnaround
    sensitivity only -- it does not change how much traffic arrives.
    """
    turn_density, straight_density = TABLE1[level]
    total_rate = lanes * (straight_density + 2.0 * turn_density)   # veh/h
    pl, ps, pr = RATIOS[ratio]
    parts = float(pl + ps + pr)
    out = {}
    for key, part, density in (("left", pl, None), ("straight", ps, straight_density),
                               ("right", pr, None)):
        rate = total_rate * part / parts
        mu = 3600.0 / rate
        out["mu_" + key] = mu
        out["n_" + key] = int(round(HORIZON / mu))
    out["ratio"] = ratio
    out["parts"] = (pl, ps, pr)
    out["total_rate_per_approach"] = total_rate
    out["turn_density"], out["straight_density"] = turn_density, straight_density
    return out


def turn_side(route_id):
    """'L' or 'R' for a turning route id (``north2east`` -> 'L')."""
    origin, _, destination = route_id.partition("2")
    pair = (COMPASS[origin], COMPASS[destination])
    return "R" if pair in RIGHT_TURNS else "L"


def cross_check_routes_txt():
    """Optional: compare with the author memo. Informational only, not an input."""
    if not ROUTES_TXT.exists():
        print("\ncross-check: %s absent, skipped" % ROUTES_TXT.name)
        return
    print("\ncross-check against %s (informational only):" % ROUTES_TXT.name)
    for line in ROUTES_TXT.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        level_text, rest = line.split(":", 1)
        for column, (straight, turn) in enumerate(
                re.findall(r"(\d+)/(\d+)", rest)):
            lanes = column + 2           # column 0 -> 2 lanes, 1 -> 3, 2 -> 4
            cell = density_cell(int(level_text))[lanes]
            memo_s, memo_t = int(straight) * 10, int(turn) * 10
            same = memo_s == cell["n_straight"] and memo_t == cell["n_turn"]
            print("  level %s lanes %d : memo x10 = %4d/%4d ; Table I = %4d/%4d"
                  "  %s"
                  % (level_text, lanes, memo_s, memo_t,
                     cell["n_straight"], cell["n_turn"],
                     "same" if same else "DIFFERS (memo not used)"))


def parse_base():
    root = ET.parse(BASE_ROU).getroot()
    routes = [(r.get("id"), r.get("edges")) for r in root.findall("route")]
    flows = [dict(f.attrib) for f in root.findall("flow")]
    return routes, flows


def is_straight(route_id):
    origin, _, destination = route_id.partition("2")
    return (origin, destination) in OPPOSITE


def build_file(lanes, level, cell, routes, flows):
    lines = [
        "<?xml version='1.0' encoding='UTF-8'?>",
        "",
        "<!--",
        "  DSIP-RR demand file generated by scenarios/flows/generate_flows.py",
        "  DO NOT EDIT BY HAND - edit this generator and regenerate.",
        "",
        "  source      : manuscript Table I, veh/(h*lane)   (level %d)" % level,
        "  lanes       : %d per approach (two-way %d-lane)" % (lanes, lanes * 2),
        "  horizon     : 0-1000 s",
        "  density     : L/S/R split %s (parts %d:%d:%d) of the Table I total"
        % (cell["ratio"], *cell["parts"]),
        "  per-approach: left %d, straight %d, right %d  (vehicles)"
        % (cell["n_left"], cell["n_straight"], cell["n_right"]),
        "  headway     : left %.6f s, straight %.6f s, right %.6f s"
        % (cell["mu_left"], cell["mu_straight"], cell["mu_right"]),
        "  conversion  : mu = 3600 / (n_lanes * density)   [Eq. (1), main.tex]",
        "  ratio       : L : S : R = %d : %d : %d" % cell["parts"],
        "  total       : %.0f veh/h per approach (held fixed across ratios)"
        % cell["total_rate_per_approach"],
        "  spread      : normal(mu, %.1f), the same convention as the original" % SIGMA,
        "                scenarios/original/routes.rou.xml",
        "",
        "  Regenerated 2026-11-07: the per-lane demand now follows Table I for",
        "  every lane count (the previous version was derived from the untracked",
        "  scenarios/original/routes.txt and was ~2.5 % low on 2 and 4 lanes).",
        "  Still open: the step length (1 s vs 0.1 s); see scenarios/flows/README.md.",
        "-->",
        "",
        "<routes>",
    ]
    for rid, edges in routes:
        lines.append('    <route edges="%s" id="%s" />' % (edges, rid))
    lines.append("")
    for flow in flows:
        rid = flow["route"]
        if is_straight(rid):
            mu, number = cell["mu_straight"], cell["n_straight"]
        elif turn_side(rid) == "L":
            mu, number = cell["mu_left"], cell["n_left"]
        else:
            mu, number = cell["mu_right"], cell["n_right"]
        lines.append(
            '    <flow begin="%s" departInterval="normal(%.10g, %.1f)" '
            'departPos="%s" departSpeed="%s" end="%s" id="%s" number="%d" '
            'route="%s" seed="%s" type="%s" />'
            % (flow["begin"], mu, SIGMA, flow["departPos"],
               flow["departSpeed"], flow["end"], flow["id"],
               number, rid, flow["seed"], flow["type"]))
    lines += ["</routes>", ""]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Generate the DSIP-RR traffic-flow files.")
    ap.add_argument("--ratios", default="121",
                    help="comma list of L:S:R codes from %s (default 121)"
                         % ",".join(sorted(RATIOS)))
    ap.add_argument("--only-cells", default="",
                    help="restrict to lanes:level pairs, e.g. '3:3' (default: all)")
    args = ap.parse_args(argv)

    routes, flows = parse_base()
    if len(routes) != 12 or len(flows) != 12:
        raise SystemExit("expected 12 routes and 12 flows in the base file")
    if sum(1 for rid, _ in routes if is_straight(rid)) != 4:
        raise SystemExit("expected 4 straight routes in the base file")

    ratios = [r.strip() for r in args.ratios.split(",") if r.strip()]
    for r in ratios:
        if r not in RATIOS:
            raise SystemExit("unknown ratio %r (known: %s)"
                             % (r, ",".join(sorted(RATIOS))))
    wanted = set()
    if args.only_cells:
        for tok in args.only_cells.split(","):
            lanes_text, level_text = tok.split(":")
            wanted.add((int(lanes_text), int(level_text)))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("%-30s %-5s %-2s %5s %11s %12s %12s %13s"
          % ("file", "ratio", "lv", "lanes", "N(L/S/R)", "h(L/S/R)",
             "total veh/h", "S real veh/h/lane"))
    written = []
    for ratio in ratios:
        for level in sorted(TABLE1):
            for lanes in (2, 3, 4):
                if wanted and (lanes, level) not in wanted:
                    continue
                cell = ratio_cell(level, lanes, ratio)
                name = ("lanes%d_density%d.rou.xml" % (lanes, level)
                        if ratio == "121"
                        else "lanes%d_density%d_r%s.rou.xml"
                             % (lanes, level, ratio))
                path = OUT_DIR / name
                path.write_text(build_file(lanes, level, cell, routes, flows),
                                encoding="utf-8")
                written.append(path)
                realised = cell["n_straight"] * 3600.0 / (lanes * HORIZON)
                print("%-30s %-5s %-2d %5d %5d/%3d/%3d %4.2f/%4.2f/%4.2f %12.0f %13.1f"
                      % (path.name, ratio, level, lanes, cell["n_left"],
                         cell["n_straight"], cell["n_right"], cell["mu_left"],
                         cell["mu_straight"], cell["mu_right"],
                         cell["total_rate_per_approach"], realised))

    print()
    print("written: %d files in %s" % (len(written), OUT_DIR))
    cross_check_routes_txt()

    tight = []
    for ratio in ratios:
        for level in sorted(TABLE1):
            for lanes in (2, 3, 4):
                if wanted and (lanes, level) not in wanted:
                    continue
                cell = ratio_cell(level, lanes, ratio)
                if min(cell["mu_left"], cell["mu_straight"],
                       cell["mu_right"]) < 3 * SIGMA:
                    tight.append((ratio, level, lanes, cell))

    print()
    print("ADVISORY: headway spread is fixed at sigma=%.1f s (original convention)."
          % SIGMA)
    print("  Files whose mean headway is below %.1f s will draw negative"
          % (3 * SIGMA))
    print("  intervals; SUMO turns those into immediate departures. Affected:")
    for ratio, level, lanes, cell in tight:
        print("    lanes%d_density%d%s : L %.3f s, S %.3f s, R %.3f s"
              % (lanes, level, "" if ratio == "121" else "_r" + ratio,
                 cell["mu_left"], cell["mu_straight"], cell["mu_right"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
