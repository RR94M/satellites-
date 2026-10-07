"""Slim Launch Library 2 downloads into launches.json for the Launches page.

Inputs, in the directory given as argv[1]: ll-upcoming.json and ll-previous.json (raw API responses, ~1.7 MB).
Output: launches.json with just what the page shows (~10% of the size). Photos are left out on purpose:
many are licensed for non-commercial use only, so the page draws its own graphics instead.
"""
import json
import re
import sys
from datetime import datetime, timezone


def load(directory, name):
    try:
        with open(f"{directory}/{name}", encoding="utf-8") as f:
            return json.load(f).get("results") or []
    except (OSError, ValueError):
        return []


def g(o, *path):
    """Safe nested get: g(launch, 'pad', 'location', 'name')."""
    for p in path:
        if isinstance(o, list):
            o = o[0] if o else None
        if not isinstance(o, dict):
            return None
        o = o.get(p)
    return o


def seconds(iso):
    """ISO 8601 duration like -PT38M, PT2M14S, P0D -> seconds."""
    m = re.fullmatch(r"(-)?P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:([\d.]+)S)?)?", iso or "")
    if not m:
        return None
    s = int(m[2] or 0) * 86400 + int(m[3] or 0) * 3600 + int(m[4] or 0) * 60 + float(m[5] or 0)
    return -s if m[1] else s


def country(c):
    return {"name": g(c, "name"), "code": g(c, "alpha_2_code")} if c else None


def person(entry):
    a = entry.get("astronaut") or {}
    return {
        "name": a.get("name"),
        "role": g(entry, "role", "role"),
        "agency": g(a, "agency", "abbrev") or g(a, "agency", "name"),
        "countries": [country(n) for n in a.get("nationality") or []],
    }


def slim(l):
    ss = g(l, "rocket", "spacecraft_stage")
    ss = (ss[0] if ss else None) if isinstance(ss, list) else ss
    crew = [person(c) for c in (ss or {}).get("launch_crew") or []]
    vids = sorted(l.get("vid_urls") or [], key=lambda v: (g(v, "type", "name") != "Official Webcast", g(v, "language", "code") not in (None, "en"), -(v.get("priority") or 0)))
    stages = []
    for st in g(l, "rocket", "launcher_stage") or []:
        stages.append({
            "type": st.get("type"),
            "serial": g(st, "launcher", "serial_number"),
            "flight": st.get("launcher_flight_number"),
            "landing": {
                "attempt": g(st, "landing", "attempt"),
                "success": g(st, "landing", "success"),
                "type": g(st, "landing", "type", "name"),
                "where": g(st, "landing", "landing_location", "name"),
            } if st.get("landing") else None,
        })
    update = (l.get("updates") or [None])[0]
    return {
        "id": l.get("id"),
        "slug": l.get("slug"),
        "name": g(l, "mission", "name") or (l.get("name") or "").split(" | ")[-1],
        "rocket": g(l, "rocket", "configuration", "full_name") or g(l, "rocket", "configuration", "name"),
        "provider": g(l, "launch_service_provider", "name"),
        "providerCountry": country(g(l, "launch_service_provider", "country")),
        "status": {k: g(l, "status", k) for k in ("abbrev", "name", "description")},
        "net": l.get("net"),
        "precision": g(l, "net_precision", "name"),
        "windowStart": l.get("window_start"),
        "windowEnd": l.get("window_end"),
        "probability": l.get("probability"),
        "weather": l.get("weather_concerns"),
        "hold": l.get("holdreason") or None,
        "fail": l.get("failreason") or None,
        "mission": {
            "description": g(l, "mission", "description"),
            "type": g(l, "mission", "type"),
            "orbit": g(l, "mission", "orbit", "name"),
            "orbitCode": g(l, "mission", "orbit", "abbrev"),
            "agencies": [a.get("name") for a in g(l, "mission", "agencies") or [] if isinstance(a, dict)],
        },
        "programs": [p.get("name") for p in l.get("program") or []],
        "pad": {
            "name": g(l, "pad", "name"),
            "location": g(l, "pad", "location", "name"),
            "country": country(g(l, "pad", "country")),
            "lat": float(g(l, "pad", "latitude")) if g(l, "pad", "latitude") is not None else None,
            "lon": float(g(l, "pad", "longitude")) if g(l, "pad", "longitude") is not None else None,
            "map": g(l, "pad", "map_url"),
            "tz": g(l, "pad", "location", "timezone_name"),
        },
        "webcastLive": bool(l.get("webcast_live")),
        "videos": [{"title": v.get("title"), "url": v.get("url"), "publisher": v.get("publisher"), "type": g(v, "type", "name"),
                    "live": bool(v.get("live")), "start": v.get("start_time")} for v in vids[:4] if v.get("url")],
        "links": [{"title": i.get("title"), "url": i.get("url"), "type": g(i, "type", "name")} for i in (l.get("info_urls") or [])[:3] if i.get("url")],
        "flightclub": l.get("flightclub_url"),
        "timeline": [[g(t, "type", "abbrev"), seconds(t.get("relative_time"))] for t in l.get("timeline") or [] if seconds(t.get("relative_time")) is not None],
        "stages": stages,
        "spacecraft": {
            "name": g(ss, "spacecraft", "name"),
            "type": g(ss, "spacecraft", "spacecraft_config", "name"),
            "destination": (ss or {}).get("destination"),
            "crew": crew,
        } if ss else None,
        "update": {"text": update.get("comment"), "at": update.get("created_on")} if isinstance(update, dict) and update.get("comment") else None,
    }


def main(directory):
    up = [slim(l) for l in load(directory, "ll-upcoming.json")]
    prev = [slim(l) for l in load(directory, "ll-previous.json")]
    out = {"updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "source": "The Space Devs - Launch Library 2", "upcoming": up, "recent": prev}
    with open(f"{directory}/launches.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    crewed = [l["name"] for l in up if l["spacecraft"] and l["spacecraft"]["crew"]]
    print(f"launches.json: {len(up)} upcoming, {len(prev)} recent, crewed: {crewed or 'none'}")


if __name__ == "__main__":
    main(sys.argv[1])
