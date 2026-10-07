"""Shrink NOAA's aurora nowcast into aurora.json for the globe.

Inputs, in the directory given as argv[1]:
  ovation.json  NOAA SWPC OVATION model: chance of aurora overhead (0-100) on a 1-degree grid, for ~30 minutes ahead
  kp-1m.json    NOAA's estimated planetary Kp, one value per minute
Output: aurora.json with only the grid cells that have some aurora (a few thousand instead of 65,000), plus the latest Kp.
"""
import json
import sys


def main(directory):
    with open(f"{directory}/ovation.json", encoding="utf-8") as f:
        ov = json.load(f)
    points = [[int(lon), int(lat), int(round(p))] for lon, lat, p in ov["coordinates"] if p >= 2]
    kp = kp_time = None
    try:
        with open(f"{directory}/kp-1m.json", encoding="utf-8") as f:
            rows = [r for r in json.load(f) if isinstance(r, dict)]
        last = rows[-1]
        kp = float(last.get("estimated_kp", last.get("kp_index")))
        kp_time = last.get("time_tag")
    except (OSError, ValueError, IndexError, TypeError, KeyError):
        pass
    out = {"observed": ov.get("Observation Time"), "forecast": ov.get("Forecast Time"), "kp": kp, "kpTime": kp_time, "points": points}
    with open(f"{directory}/aurora.json", "w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))
    print(f"aurora.json: {len(points)} cells, max {max((p[2] for p in points), default=0)}%, Kp {kp}")


if __name__ == "__main__":
    main(sys.argv[1])
