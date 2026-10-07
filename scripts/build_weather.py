"""Global weather layers for the globe: cloud cover and wind from NOAA's GFS model, tropical storms from GDACS.

Writes into the directory given as argv[1]:
  weather.json  1-degree grids of total cloud cover (%) and 10 m wind (m/s), packed as base64 bytes
  storms.json   active tropical storms/hurricanes/typhoons worldwide: position, strength, past and forecast track
Raw GDACS responses are kept alongside (gdacs-*.json) so problems can be checked.

GFS is a US government product (public domain). GDACS is run by the European Commission's JRC with the UN.
"""
import base64
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

UA = {"User-Agent": "Overhead satellite tracker (github.com/RR94M/satellites-)"}


def get(url, binary=False, tries=3):
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                data = r.read()
                return data if binary else json.loads(data.decode("utf-8"))
        except Exception as e:  # noqa: BLE001 - log and retry anything
            print(f"  attempt {attempt + 1} failed for {url[:120]}: {e}")
            time.sleep(10)
    return None


# ---------------------------------------------------------------- GFS: clouds and wind
def gfs(directory):
    import numpy as np
    import pygrib

    now = datetime.now(timezone.utc)
    for back in range(0, 4):  # the newest run appears ~4-5 hours after its start time
        run = (now - timedelta(hours=4 + 6 * back)).replace(minute=0, second=0, microsecond=0)
        run = run.replace(hour=run.hour - run.hour % 6)
        fh = int(round((now - run).total_seconds() / 3600 / 3)) * 3  # forecast hour nearest to now
        day, hh = run.strftime("%Y%m%d"), run.strftime("%H")
        url = ("https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_1p00.pl?"
               f"dir=%2Fgfs.{day}%2F{hh}%2Fatmos&file=gfs.t{hh}z.pgrb2.1p00.f{fh:03d}"
               "&var_UGRD=on&var_VGRD=on&lev_10_m_above_ground=on&var_TCDC=on&lev_entire_atmosphere=on")
        print(f"GFS run {day} {hh}z +{fh}h")
        data = get(url, binary=True, tries=2)
        if data and data[:4] == b"GRIB":
            break
    else:
        print("::warning::no GFS data")
        return False
    path = f"{directory}/gfs.grb2"
    with open(path, "wb") as f:
        f.write(data)
    fields = {}
    for g in pygrib.open(path):
        print(f"  field: {g.shortName} {g.typeOfLevel} {g.level} {g.values.shape}")
        fields[g.shortName] = g.values  # rows: 90N..90S, columns: 0..359E
    os.remove(path)
    u, v, c = fields.get("10u"), fields.get("10v"), fields.get("tcc")
    if u is None or v is None or c is None:
        print("::warning::GFS file missing a field:", list(fields))
        return False

    def pack(a, scale, lo, hi, signed):
        q = np.clip(np.round(np.asarray(a, dtype=float) * scale), lo, hi).astype(np.int8 if signed else np.uint8)
        return base64.b64encode(q.tobytes()).decode("ascii")

    valid = run + timedelta(hours=fh)
    out = {
        "run": run.strftime("%Y-%m-%dT%H:%MZ"), "valid": valid.strftime("%Y-%m-%dT%H:%MZ"),
        "w": int(c.shape[1]), "h": int(c.shape[0]), "lat0": 90, "lon0": 0, "step": 1,
        "cloud": pack(c, 1, 0, 100, False),            # % cover, 1 byte each
        "u": pack(u, 2, -127, 127, True),              # m/s x 2, signed byte (eastward)
        "v": pack(v, 2, -127, 127, True),              # m/s x 2, signed byte (northward)
        "source": "NOAA GFS 1-degree",
    }
    with open(f"{directory}/weather.json", "w") as f:
        json.dump(out, f, separators=(",", ":"))
    print(f"weather.json: valid {out['valid']}, cloud mean {float(np.mean(c)):.0f}%, max wind {float(np.max(np.hypot(u, v))):.0f} m/s")
    return True


# ---------------------------------------------------------------- GDACS: tropical cyclones
def storms(directory):
    events = get("https://www.gdacs.org/gdacsapi/api/events/geteventlist/EVENTS4APP")
    with open(f"{directory}/gdacs-events.json", "w") as f:
        json.dump(events, f)
    if not events:
        print("::warning::no GDACS event list")
        return
    out = []
    for feat in events.get("features", []):
        p = feat.get("properties", {})
        if p.get("eventtype") != "TC":
            continue
        geo_url = (p.get("url") or {}).get("geometry")
        geom = get(geo_url) if geo_url else None
        with open(f"{directory}/gdacs-{p.get('eventid')}.json", "w") as f:
            json.dump(geom, f)
        out.append({"id": p.get("eventid"), "episode": p.get("episodeid"), "name": p.get("name") or p.get("eventname"),
                    "alert": p.get("alertlevel"), "severity": p.get("severitydata"), "from": p.get("fromdate"), "to": p.get("todate"),
                    "current": p.get("iscurrent"), "country": p.get("country"), "point": (feat.get("geometry") or {}).get("coordinates"),
                    "geometryUrl": geo_url, "report": (p.get("url") or {}).get("report")})
    with open(f"{directory}/storms-raw.json", "w") as f:
        json.dump({"updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "storms": out}, f)
    print(f"GDACS: {len(out)} tropical cyclone event(s): " + ", ".join(str(s['name']) for s in out))


if __name__ == "__main__":
    d = sys.argv[1]
    os.makedirs(d, exist_ok=True)
    try:
        gfs(d)
    except Exception as e:  # noqa: BLE001
        print("::warning::GFS step failed:", e)
    try:
        storms(d)
    except Exception as e:  # noqa: BLE001
        print("::warning::storms step failed:", e)
