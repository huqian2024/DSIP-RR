#!/usr/bin/env python3
"""Independent validation of the 15 generated traffic-flow files.

Re-derives every expected number from the manuscript's Table I densities and
Eq. (1) and compares it with what is actually written in
``scenarios/flows/*.rou.xml``. It does not import the generator, so a bug in
the generator cannot hide itself.

Checks per file:
  * 12 <route> and 12 <flow> elements
  * one number / headway for all straight flows and one for all turning flows
  * headway == 3600 / (n_lanes * density)  [Eq. (1), unit veh/(h*lane)]
  * number == round(1000 / headway)        [1000 s horizon]
  * realised per-lane density within 0.5 % of Table I
  * straight : each turning direction = 2 : 1 in rate (L:S:R = 1:2:1)

Regenerated 2026-11-07 together with the generator: ``routes.txt`` is no longer
an input, only an informational cross-check in the generator itself.

Exit code 0 = all consistent.

Usage:
    python3 scenarios/flows/validate_flows.py
"""

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "scenarios" / "flows"
HORIZON = 1000.0
RATE_TOL = 0.005            # realised per-lane density, relative tolerance
STRAIGHT = ("north2south", "south2north", "east2west", "west2east")

# Manuscript Table I (main.tex lines 101-120), veh/(h*lane).
# level -> (density of EACH turning direction, straight-through density)
TABLE1 = {
    1: (240, 480),
    2: (300, 600),
    3: (384, 768),
    4: (480, 960),
    5: (600, 1200),
}


def expected(level, lanes):
    """-> (n_straight, n_turn, mu_straight, mu_turn, straight_density)."""
    turn_density, straight_density = TABLE1[level]
    mu_s = 3600.0 / (lanes * straight_density)
    mu_t = 3600.0 / (lanes * turn_density)
    return (int(round(HORIZON / mu_s)), int(round(HORIZON / mu_t)),
            mu_s, mu_t, straight_density)


def check_file(path, level, lanes):
    exp_ns, exp_nt, exp_hs, exp_ht, straight_density = expected(level, lanes)
    root = ET.parse(path).getroot()
    flows = root.findall("flow")
    problems = []
    if len(root.findall("route")) != 12 or len(flows) != 12:
        problems.append("expected 12 routes and 12 flows")

    def subset(is_straight):
        return [f for f in flows if (f.get("route") in STRAIGHT) == is_straight]

    def headway(flow):
        match = re.match(r"normal\(([0-9.]+),\s*([0-9.]+)\)",
                         flow.get("departInterval"))
        if not match:
            raise SystemExit("unexpected departInterval in %s" % path)
        return float(match.group(1)), float(match.group(2))

    straight, turning = subset(True), subset(False)
    if len(straight) != 4 or len(turning) != 8:
        problems.append("expected 4 straight and 8 turning flows")

    numbers = {int(f.get("number")) for f in straight}
    numbers_t = {int(f.get("number")) for f in turning}
    headways = {headway(f)[0] for f in straight}
    headways_t = {headway(f)[0] for f in turning}
    sigmas = {headway(f)[1] for f in flows}
    if max(len(numbers), len(numbers_t), len(headways), len(headways_t)) != 1:
        problems.append("straight/turning flows are not uniform")
    if len(sigmas) != 1:
        problems.append("headway spread differs between flows")

    n_s, n_t = list(numbers)[0], list(numbers_t)[0]
    h_s, h_t = list(headways)[0], list(headways_t)[0]
    if abs(h_s - exp_hs) > 1e-5:
        problems.append("straight headway %.9f != %.9f (Eq. 1)" % (h_s, exp_hs))
    if abs(h_t - exp_ht) > 1e-5:
        problems.append("turning headway %.9f != %.9f (Eq. 1)" % (h_t, exp_ht))
    if n_s != exp_ns:
        problems.append("straight number %d != %d" % (n_s, exp_ns))
    if n_t != exp_nt:
        problems.append("turning number %d != %d" % (n_t, exp_nt))
    if abs(h_t / h_s - 2.0) > 1e-9:
        problems.append("rate ratio straight:turn %.9f != 2" % (h_t / h_s))
    if abs(n_s * h_s - HORIZON) > h_s or abs(n_t * h_t - HORIZON) > h_t:
        problems.append("number x headway differs from %.0f s by more than one "
                        "vehicle" % HORIZON)

    realised = n_s * 3600.0 / (lanes * HORIZON)
    if abs(realised - straight_density) / straight_density > RATE_TOL:
        problems.append("realised straight density %.1f != %d veh/(h*lane)"
                        % (realised, straight_density))
    return n_s, n_t, h_s, h_t, realised, problems


def main():
    print("%-26s %6s %6s %9s %9s %12s  %s"
          % ("file", "N_s", "N_t", "h_s", "h_t", "S veh/h/lane", "status"))
    all_ok = True
    for level in sorted(TABLE1):
        for lanes in (2, 3, 4):
            path = OUT_DIR / ("lanes%d_density%d.rou.xml" % (lanes, level))
            if not path.exists():
                print("%-26s MISSING" % path.name)
                all_ok = False
                continue
            n_s, n_t, h_s, h_t, realised, problems = check_file(path, level, lanes)
            all_ok = all_ok and not problems
            print("%-26s %6d %6d %9.6f %9.6f %12.1f  %s"
                  % (path.name, n_s, n_t, h_s, h_t, realised,
                     "OK" if not problems else "FAIL: " + "; ".join(problems)))
    print()
    print("ALL 15 FILES CONSISTENT WITH TABLE I + EQ. (1):", all_ok)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
