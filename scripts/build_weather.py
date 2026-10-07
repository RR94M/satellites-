"""Global weather layers and alerts: cloud cover and wind from NOAA's GFS model, tropical storms and other disasters
from GDACS, earthquakes from USGS, space weather alerts from NOAA SWPC.

Writes into the directory given as argv[1]:
  weather.json       1-degree grids of total cloud cover (%) and 10 m wind (m/s), packed as base64 bytes
  storms.json        active tropical storms/hurricanes/typhoons worldwide: position, strength, past and forecast track
  hazards.json       other current GDACS disasters (floods, wildfires, volcanoes, droughts) with alert levels
  quakes.json        earthquakes of magnitude 4.5+ worldwide in the past week (USGS)
  space-alerts.json  NOAA space weather alerts, watches and warnings from the past 3 days

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
# The same kind of storm has a different name by ocean
def kind(lon, lat):
    if lon is None: return "hurricane"
    if 100 <= lon <= 180 and lat > 0: return "typhoon"
    if (lon < -20 or lon > 180) and lat > 0: return "hurricane"  # Atlantic and east/central Pacific
    return "cyclone"


def strength(kmh, word):
    """Saffir-Simpson style class from maximum sustained wind (km/h)."""
    if kmh is None: return None
    for limit, cat in ((252, 5), (209, 4), (178, 3), (154, 2), (119, 1)):
        if kmh >= limit: return f"Category {cat} {word}"
    return "tropical storm" if kmh >= 63 else "tropical depression"


CLASS = {"TD": "tropical depression", "TS": "tropical storm", "STS": "severe tropical storm", "HU": None, "TY": None, "STY": None,
         "SS": "subtropical storm", "SD": "subtropical depression", "EX": "post-tropical storm", "LO": "remnant low", "DB": "disturbance"}


def thin(ring, keep=80):
    step = max(1, len(ring) // keep)
    out = [[round(x, 2), round(y, 2)] for x, y in ring[::step]]
    return out if out[-1] == out[0] else out + [out[0]]


def parse_storm(feat, geom):
    p = feat.get("properties", {})
    here = (feat.get("geometry") or {}).get("coordinates")
    sev = p.get("severitydata") or {}
    kmh = sev.get("severity") if (sev.get("severityunit") or "").startswith("km") else None
    segs, cone, winds, times = [], None, {}, []
    for f in (geom or {}).get("features", []):
        g, q = f.get("geometry") or {}, f.get("properties") or {}
        label = q.get("polygonlabel") or ""
        if g.get("type") == "LineString" and len(g.get("coordinates", [])) >= 2:
            segs.append((label, [tuple(c[:2]) for c in g["coordinates"]]))
        elif g.get("type") == "Polygon" and label == "Uncertainty Cones":
            cone = thin(g["coordinates"][0], 120)
        elif g.get("type") == "Polygon" and label.endswith("km/h"):
            winds[label] = thin(g["coordinates"][0], 60)
        elif g.get("type") == "Polygon" and label.endswith("UTC"):  # a forecast position (circle) with its time
            ring = g["coordinates"][0]
            cx, cy = sum(c[0] for c in ring) / len(ring), sum(c[1] for c in ring) / len(ring)
            year = (q.get("polygondate") or "2000")[:4]
            try:
                t = datetime.strptime(year + " " + label.replace(" UTC", ""), "%Y %d/%m %H:%M").replace(tzinfo=timezone.utc)
                times.append((t, (cx, cy)))
            except ValueError:
                pass
    # join the short track pieces into one line, start to finish
    starts = {seg[1][0]: seg for seg in segs}
    ends = {seg[1][-1] for seg in segs}
    first = next((seg for seg in segs if seg[1][0] not in ends), segs[0] if segs else None)
    track, seen = [], set()
    seg = first
    while seg and id(seg) not in seen:
        seen.add(id(seg))
        cls, pts = seg
        if not track: track.append([pts[0][0], pts[0][1], cls])
        for pt in pts[1:]: track.append([pt[0], pt[1], cls])
        seg = starts.get(pts[-1])
    # split at the storm's current position: what's behind it happened, what's ahead is forecast
    now_i = 0
    if here and track:
        now_i = min(range(len(track)), key=lambda i: (track[i][0] - here[0]) ** 2 + (track[i][1] - here[1]) ** 2)
    for t, (cx, cy) in times:  # put forecast times on the nearest forecast points
        if track[now_i:]:
            k = min(range(now_i, len(track)), key=lambda i: (track[i][0] - cx) ** 2 + (track[i][1] - cy) ** 2)
            if len(track[k]) == 3: track[k].append(t.strftime("%Y-%m-%dT%H:%MZ"))
    name = (p.get("eventname") or p.get("name") or "Storm").rsplit("-", 1)[0].replace("Tropical Cyclone ", "").title()
    word = kind(*(here or [None, None]))
    cls = track[now_i][2] if track else None   # GDACS's wind figure is the forecast peak, so "now" comes from the track class
    now_name = CLASS.get(cls, None) if cls in CLASS else None
    if now_name is None: now_name = word if cls in ("HU", "TY", "STY") else (strength(kmh, word) or "tropical storm")
    countries = [c.get("countryname") for c in p.get("affectedcountries") or [] if c.get("countryname")]
    return {
        "id": p.get("eventid"), "name": name, "kind": word, "now": now_name, "alert": p.get("alertlevel"),
        "peakKmh": round(kmh) if kmh else None, "peak": strength(kmh, word), "at": here, "updated": p.get("todate"),
        "countries": countries or ([p.get("country")] if p.get("country") else []),
        "past": [t[:3] for t in track[:now_i + 1]], "forecast": [t if len(t) == 4 else t[:3] for t in track[now_i:]],
        "cone": cone, "wind60": winds.get("60 km/h"), "wind120": winds.get("120 km/h"),
        "report": (p.get("url") or {}).get("report"),
    }


def storms(directory, events=None, geometry=None):
    events = events if events is not None else get("https://www.gdacs.org/gdacsapi/api/events/geteventlist/EVENTS4APP")
    if not events:
        print("::warning::no GDACS event list")
        return None
    out = []
    for feat in events.get("features", []):
        p = feat.get("properties", {})
        if p.get("eventtype") != "TC" or str(p.get("iscurrent")).lower() != "true":
            continue
        url = (p.get("url") or {}).get("geometry")
        geom = geometry(p) if geometry else (get(url) if url else None)
        try:
            out.append(parse_storm(feat, geom))
        except Exception as e:  # noqa: BLE001 - one odd storm shouldn't lose the others
            print(f"::warning::could not read storm {p.get('eventname')}: {e}")
    out.sort(key=lambda s: -(s["peakKmh"] or 0))
    with open(f"{directory}/storms.json", "w") as f:
        json.dump({"updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "source": "GDACS (European Commission JRC and UN)", "storms": out},
                  f, separators=(",", ":"))
    hazards(directory, events)
    print(f"storms.json: {len(out)} storm(s): " + ", ".join(f"{s['name']} ({s['now']} now, peak {s['peak']} {s['peakKmh']} km/h, {len(s['past'])}+{len(s['forecast'])} pts)" for s in out))


HAZARD = {"FL": "flood", "WF": "wildfire", "VO": "volcano", "DR": "drought", "EQ": "earthquake"}


def hazards(directory, events):
    """Current GDACS disasters other than storms (covered by storms.json) and earthquakes (USGS is quicker and fuller)."""
    out = []
    for feat in events.get("features", []):
        p = feat.get("properties", {})
        t = p.get("eventtype")
        if t not in ("FL", "WF", "VO", "DR") or str(p.get("iscurrent")).lower() != "true":
            continue
        c = (feat.get("geometry") or {}).get("coordinates") or [None, None]
        sev = (p.get("severitydata") or {}).get("severitytext") or ""
        out.append({"type": HAZARD[t], "id": p.get("eventid"), "name": p.get("name") or p.get("description"), "alert": p.get("alertlevel"),
                    "detail": sev.strip() if t != "FL" else "", "country": p.get("country"), "from": p.get("fromdate"), "to": p.get("todate"),
                    "lon": c[0], "lat": c[1], "report": (p.get("url") or {}).get("report")})
    rank = {"Red": 0, "Orange": 1, "Green": 2}
    out.sort(key=lambda h: (rank.get(h["alert"], 3), h["to"] or ""), reverse=False)
    with open(f"{directory}/hazards.json", "w") as f:
        json.dump({"updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "source": "GDACS", "hazards": out}, f, separators=(",", ":"))
    print(f"hazards.json: {len(out)} event(s)")


def quakes(directory):
    d = get("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson")
    if not d:
        print("::warning::no USGS feed")
        return
    out = []
    for f in d.get("features", []):
        p, c = f.get("properties", {}), (f.get("geometry") or {}).get("coordinates") or [None, None, None]
        out.append({"id": f.get("id"), "mag": p.get("mag"), "place": p.get("place"), "time": p.get("time"), "lon": c[0], "lat": c[1],
                    "depth": c[2], "alert": p.get("alert"), "tsunami": p.get("tsunami"), "felt": p.get("felt"), "url": p.get("url")})
    out.sort(key=lambda q: -(q["time"] or 0))
    with open(f"{directory}/quakes.json", "w") as f:
        json.dump({"updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "source": "USGS", "quakes": out}, f, separators=(",", ":"))
    print(f"quakes.json: {len(out)} earthquake(s), biggest M{max((q['mag'] or 0) for q in out) if out else 0}")


def space_alerts(directory):
    d = get("https://services.swpc.noaa.gov/products/alerts.json")
    if d is None:
        print("::warning::no SWPC alerts")
        return
    cutoff = datetime.now(timezone.utc) - timedelta(days=3)
    out = []
    for a in d:
        try:
            issued = datetime.strptime(a["issue_datetime"][:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except (KeyError, ValueError):
            continue
        if issued < cutoff:
            continue
        lines = [l.strip() for l in (a.get("message") or "").replace("\r", "").split("\n")]
        head = next((l for l in lines if l.split(":")[0] in ("ALERT", "WARNING", "WATCH", "SUMMARY", "EXTENDED WARNING", "CANCEL WARNING", "CANCEL WATCH")), None)
        field = lambda name: next((l.split(":", 1)[1].strip() for l in lines if l.lower().startswith(name.lower() + ":")), None)
        if not head:
            continue
        impacts = []
        if "Potential Impacts:" in (a.get("message") or ""):
            k = next(i for i, l in enumerate(lines) if l.startswith("Potential Impacts:"))
            impacts = [l for l in [lines[k].split(":", 1)[1].strip()] + lines[k + 1:k + 6] if l and not l.startswith("www.")][:5]
        days = []  # watches list the expected level for each day, e.g. "Oct 08: G2 (Moderate)"
        k = next((i for i, l in enumerate(lines) if l.lower().startswith("highest storm level predicted by day")), None)
        if k is not None:
            for l in lines[k + 1:k + 4]:
                if not l: break
                days.append(" ".join(l.split()))
        out.append({"id": a.get("product_id"), "issued": issued.strftime("%Y-%m-%dT%H:%MZ"), "kind": head.split(":")[0].title(), "days": days,
                    "headline": head.split(":", 1)[1].strip(), "scale": field("NOAA Scale"), "validFrom": field("Valid From"),
                    "validTo": field("Valid To"), "impacts": impacts})
    out.sort(key=lambda x: x["issued"], reverse=True)
    with open(f"{directory}/space-alerts.json", "w") as f:
        json.dump({"updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "source": "NOAA SWPC", "alerts": out}, f, separators=(",", ":"))
    print(f"space-alerts.json: {len(out)} alert(s) in 3 days: " + "; ".join(x["headline"][:60] for x in out[:5]))


if __name__ == "__main__":
    d = sys.argv[1]
    os.makedirs(d, exist_ok=True)
    try:
        gfs(d)
    except Exception as e:  # noqa: BLE001
        print("::warning::GFS step failed:", e)
    for step in (storms, quakes, space_alerts):
        try:
            step(d)
        except Exception as e:  # noqa: BLE001 - one source failing shouldn't stop the others
            print(f"::warning::{step.__name__} step failed:", e)
