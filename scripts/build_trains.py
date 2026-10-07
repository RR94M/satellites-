"""Find satellite "trains" and write trains.json for the Tonight page.

A train is a batch of satellites from one launch that are still bunched together, so they cross the sky as a
line of lights a few minutes long. This happens for the first days or weeks after a Starlink, Kuiper or Qianfan
launch, until the satellites drift apart around their orbit.

Input: active.tle in the directory given as argv[1]. Output: trains.json in the same directory.
A launch group counts as a train when it has 8+ satellites and half of them are within MAX_SPREAD degrees
(measured from the group's medoid, so a few stragglers don't hide a real train).
"""
import json
import math
import sys
from collections import defaultdict
from datetime import datetime, timezone

from sgp4.api import Satrec, jday

MAX_SPREAD = 20.0
MIN_SIZE = 8
# Only constellations whose fresh batches are bright enough to see by eye. Other launch groups that fly together
# (formation-flying science or cubesat clusters) are too faint to show up as a train.
FAMILIES = ("STARLINK", "KUIPER", "QIANFAN", "GUOWANG", "ONEWEB")


def unit_positions(sats, jd, fr):
    out = []
    for name, l1, l2, sat in sats:
        err, r, _ = sat.sgp4(jd, fr)
        if err == 0:
            n = math.sqrt(sum(x * x for x in r))
            out.append(((name, l1, l2), [x / n for x in r]))
    return out


def angle(a, b):
    return math.degrees(math.acos(max(-1.0, min(1.0, sum(a[i] * b[i] for i in range(3))))))


def main(directory):
    lines = open(f"{directory}/active.tle", encoding="utf-8").read().splitlines()
    groups = defaultdict(list)
    for i in range(0, len(lines) - 2, 3):
        name, l1, l2 = lines[i].strip(), lines[i + 1], lines[i + 2]
        if not (l1.startswith("1 ") and l2.startswith("2 ")):
            continue
        designator = l1[9:14].strip()          # launch year + launch number, e.g. "26159"
        if designator[:2].isdigit() and name.upper().startswith(FAMILIES):
            groups[designator].append((name, l1, l2, Satrec.twoline2rv(l1, l2)))

    now = datetime.now(timezone.utc)
    jd, fr = jday(now.year, now.month, now.day, now.hour, now.minute, now.second)
    trains = []
    for designator, sats in groups.items():
        if len(sats) < MIN_SIZE:
            continue
        pos = unit_positions(sats, jd, fr)
        if len(pos) < MIN_SIZE:
            continue
        medoid = min(pos, key=lambda p: sum(angle(p[1], q[1]) for q in pos))
        spread = sorted(angle(medoid[1], q[1]) for q in pos)
        if spread[len(spread) // 2] > MAX_SPREAD:
            continue
        name, l1, l2 = medoid[0]
        family = name.split("-")[0].split(" ")[0].title() if name else "Satellite"
        year = int(designator[:2])
        trains.append({
            "designator": f"{2000 + year if year < 57 else 1900 + year}-{designator[2:]}",
            "family": family,
            "count": len(pos),
            "length": round(spread[-1] * 2),          # degrees of orbit the line of lights covers
            "name": name,
            "tle": [l1, l2],
        })
    trains.sort(key=lambda t: t["designator"], reverse=True)
    result = {"updated": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "trains": trains}
    with open(f"{directory}/trains.json", "w", encoding="utf-8") as f:
        json.dump(result, f, separators=(",", ":"))
    print(f"{len(trains)} train(s): " + ", ".join(f"{t['family']} {t['designator']} ({t['count']})" for t in trains))


if __name__ == "__main__":
    main(sys.argv[1])
