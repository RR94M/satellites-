"""Space weather for the Space weather page, from NOAA's Space Weather Prediction Center and NASA's DONKI (all public
domain). Writes space.json into the directory given as argv[1]; the page also tries NOAA directly for the newest values.

  scales     NOAA R/S/G scales: yesterday, now, and chances for the next 3 days
  kp         observed 3-hourly Kp for the past week, plus NOAA's 3-day forecast
  wind       solar wind at L1 for the past day (speed, density, Bz, Bt), 10-minute averages
  xray       GOES X-ray flux for the past day (long channel), 5-minute samples, and flares from the past week
  protons    GOES >=10 MeV proton flux for the past day
  cmes       CMEs modelled by NASA to reach Earth, with predicted arrival
  cycle      monthly sunspot numbers since 1996 plus NOAA's prediction
"""
import json
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

UA = {"User-Agent": "Overhead satellite tracker (github.com/RR94M/satellites-)"}
SWPC = "https://services.swpc.noaa.gov/"


def get(url, tries=3):
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            print(f"  attempt {attempt + 1} failed for {url[:110]}: {e}")
            time.sleep(8)
    return None


def table(rows):
    """NOAA 'products' files are a header row followed by rows of strings."""
    if not rows or not isinstance(rows, list) or not isinstance(rows[0], list):
        return []
    head = rows[0]
    return [dict(zip(head, r)) for r in rows[1:]]


def num(x):
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def main(d):
    out = {"updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")}

    out["scales"] = get(SWPC + "products/noaa-scales.json")

    kp = table(get(SWPC + "products/noaa-planetary-k-index.json"))
    out["kp"] = [[r.get("time_tag"), num(r.get("Kp"))] for r in kp if num(r.get("Kp")) is not None]
    fc = get(SWPC + "products/noaa-planetary-k-index-forecast.json")
    rows = fc if fc and isinstance(fc[0], dict) else table(fc)
    out["kpForecast"] = [[r.get("time_tag"), num(r.get("kp")), r.get("observed")] for r in rows or [] if num(r.get("kp")) is not None]

    plasma = {r["time_tag"][:16]: r for r in table(get(SWPC + "products/solar-wind/plasma-1-day.json"))}
    mag = {r["time_tag"][:16]: r for r in table(get(SWPC + "products/solar-wind/mag-1-day.json"))}
    wind = []
    for t in sorted(set(plasma) | set(mag)):
        if t[-1] != "0":  # one sample every 10 minutes keeps the file small
            continue
        p, m = plasma.get(t, {}), mag.get(t, {})
        wind.append([t, num(p.get("speed")), num(p.get("density")), num(m.get("bz_gsm")), num(m.get("bt"))])
    out["wind"] = wind

    xr = get(SWPC + "json/goes/primary/xrays-1-day.json") or []
    out["xray"] = [[r.get("time_tag"), num(r.get("flux"))] for r in xr
                   if r.get("energy") == "0.1-0.8nm" and num(r.get("flux")) and r.get("time_tag", "")[15] in "05"]
    flares = get(SWPC + "json/goes/primary/xray-flares-7-day.json") or []
    out["flares"] = [{k: f.get(k) for k in ("begin_time", "max_time", "end_time", "max_class", "begin_class")} for f in flares if f.get("max_class")]

    pr = get(SWPC + "json/goes/primary/integral-protons-1-day.json") or []
    out["protons"] = [[r.get("time_tag"), num(r.get("flux"))] for r in pr if r.get("energy") == ">=10 MeV" and r.get("time_tag", "")[15] in "05"]

    now = datetime.now(timezone.utc)
    sims = get("https://kauai.ccmc.gsfc.nasa.gov/DONKI/WS/get/WSAEnlilSimulations?startDate="
               + (now - timedelta(days=7)).strftime("%Y-%m-%d") + "&endDate=" + now.strftime("%Y-%m-%d")) or []
    cmes = {}
    for s in sims:
        arrival = s.get("estimatedShockArrivalTime")
        if not arrival:
            continue
        cme = (s.get("cmeInputs") or [{}])[0]
        key = ",".join(s.get("cmeIDs") or []) or arrival
        cmes[key] = {"arrival": arrival, "glancing": bool(s.get("isEarthGB")), "launched": cme.get("cmeStartTime"),
                     "speed": cme.get("speed"), "kp": max([k for k in (s.get("kp_18"), s.get("kp_90"), s.get("kp_135"), s.get("kp_180")) if k] or [None]),
                     "modelled": s.get("modelCompletionTime"), "link": s.get("link")}
    out["cmes"] = sorted(cmes.values(), key=lambda c: c["arrival"])

    cyc = get(SWPC + "json/solar-cycle/observed-solar-cycle-indices.json") or []
    out["cycle"] = [[c.get("time-tag"), num(c.get("ssn")), num(c.get("smoothed_ssn"))] for c in cyc if (c.get("time-tag") or "") >= "1996"]
    pred = get(SWPC + "json/solar-cycle/predicted-solar-cycle.json") or []
    out["cyclePrediction"] = [[c.get("time-tag"), num(c.get("predicted_ssn"))] for c in pred if num(c.get("predicted_ssn")) is not None][:60]

    with open(f"{d}/space.json", "w") as f:
        json.dump(out, f, separators=(",", ":"))
    print("space.json:", {k: (len(v) if isinstance(v, list) else ("ok" if v else "missing")) for k, v in out.items() if k != "updated"})
    if out["scales"]:
        print("  scales now:", json.dumps(out["scales"].get("0"))[:300])
    print("  latest wind:", wind[-1:] if wind else None, "| latest flare:", out["flares"][:1], "| cmes:", out["cmes"][:2])


if __name__ == "__main__":
    main(sys.argv[1])
