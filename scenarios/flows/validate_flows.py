#!/usr/bin/env python3
"""Independent validation of the 15 generated traffic-flow files.

Re-derives every expected number from ``scenarios/original/routes.txt`` and
compares it with what is actually written in ``scenarios/flows/*.rou.xml``.
It does not import the generator, so a bug in the generator cannot hide itself.

Checks per file:
  * 12 <route> and 12 <flow> elements
  * one number / headway for all straight flows and one for all turning flows
  * straight : each turning direction = 2 : 1 (both count and headway)
  * number x headway = 1000 s (self-consistency of the demand)
  * the level / lane values match routes.txt exactly

Exit code 0 = all consistent.

Usage:
    python3 scenarios/flows/validate_flows.py
"""

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROUTES_TXT = ROOT / "scenarios" / "original" / "routes.txt"
OUT_DIR = ROOT / "scenarios" / "flows"
SCALE = 10
STRAIGHT = ("north2south", "south2north", "east2west", "west2east")


def expected():
    cells = {}
    for line in ROUTES_TXT.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        level_text, rest = line.split(":", 1)
        for column, (straight, turn) in enumerate(
                re.findall(r"(\d+)/(\d+)", rest)):
            cells[(int(level_text), column + 2)] = (int(straight), int(turn))
    return cells


def check_file(path, straight_c, turn_c):
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
    if n_s != straight_c * SCALE:
        problems.append("straight number %d != %d" % (n_s, straight_c * SCALE))
    if n_t != turn_c * SCALE:
        problems.append("turning number %d != %d" % (n_t, turn_c * SCALE))
    if abs(h_s - 100.0 / straight_c) > 1e-5:
        problems.append("straight headway %.6f != %.6f"
                        % (h_s, 100.0 / straight_c))
    if abs(h_t - 100.0 / turn_c) > 1e-5:
        problems.append("turning headway %.6f != %.6f" % (h_t, 100.0 / turn_c))
    if abs(n_s / n_t - 2.0) > 1e-9:
        problems.append("count ratio %.6f != 2" % (n_s / n_t))
    if abs(h_t / h_s - 2.0) > 1e-6:
        problems.append("headway ratio %.6f != 2" % (h_t / h_s))
    if abs(n_s * h_s - 1000.0) > 0.5 or abs(n_t * h_t - 1000.0) > 0.5:
        problems.append("number x headway != 1000 s")
    return n_s, n_t, h_s, h_t, problems


def main():
    cells = expected()
    print("%-26s %6s %6s %8s %8s %6s  %s"
          % ("file", "N_s", "N_t", "h_s", "h_t", "sigma", "status"))
    all_ok = True
    for (level, lanes), (straight_c, turn_c) in sorted(cells.items()):
        path = OUT_DIR / ("lanes%d_density%d.rou.xml" % (lanes, level))
        if not path.exists():
            print("%-26s MISSING" % path.name)
            all_ok = False
            continue
        n_s, n_t, h_s, h_t, problems = check_file(path, straight_c, turn_c)
        all_ok = all_ok and not problems
        print("%-26s %6d %6d %8.4f %8.4f %6.1f  %s"
              % (path.name, n_s, n_t, h_s, h_t, 1.0,
                 "OK" if not problems else "FAIL: " + "; ".join(problems)))
    print()
    print("ALL 15 FILES CONSISTENT WITH routes.txt:", all_ok)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
