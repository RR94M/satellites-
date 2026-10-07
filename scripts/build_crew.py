"""Build data/crew.json (who is on each space station right now) from Launch Library 2 downloads.

Inputs, in the directory given as argv[1]: ll-stations.json, ll-astronauts.json, ll-expeditions.json
(raw responses from The Space Devs' Launch Library 2 API, fetched by .github/workflows/update-data.yml).

Two sources are combined because each lags in a different way:
  - the station's active expedition crew list, which can miss a crew that has just arrived;
  - astronauts flagged "in space" whose latest flight is going to that station.
"""
import json
import sys
from datetime import datetime, timedelta, timezone

# Our tracker's satellite for each Launch Library station id, matched by CelesTrak name prefix.
STATIONS = {4: {"short": "ISS", "match": "ISS ("}, 18: {"short": "Tiangong", "match": "CSS ("}}

# Usual stay by spacecraft, used only when no departure date has been published. Shown as an estimate.
TYPICAL_DAYS = [("Ax-", 14), ("Axiom", 14), ("Soyuz", 240), ("Shenzhou", 183), ("Crew-", 180), ("Dragon", 180), ("Starliner", 180)]


def load(directory, name):
    try:
        with open(f"{directory}/{name}", encoding="utf-8") as f:
            return json.load(f).get("results") or []
    except (OSError, ValueError):
        return []


def parse(ts):
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")) if ts else None
    except ValueError:
        return None


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None


def latest(items, key):
    items = [i for i in items or [] if key(i)]
    return max(items, key=key) if items else None


def typical_days(mission):
    for prefix, days in TYPICAL_DAYS:
        if prefix.lower() in (mission or "").lower():
            return days
    return 180


def describe(astronaut, role, now):
    flight = latest(astronaut.get("flights"), lambda f: f.get("net") or "") or {}
    mission = (flight.get("mission") or {}).get("name") or flight.get("name")
    pad = flight.get("pad") or {}
    location = pad.get("location") or {}
    rocket = ((flight.get("rocket") or {}).get("configuration") or {}).get("full_name")
    launched = parse(flight.get("net"))

    # The ride home is the spacecraft flight that went up on this same launch, if it has been recorded.
    ride = next((l for l in astronaut.get("landings") or []
                 if (l.get("launch") or {}).get("id") and (l.get("launch") or {}).get("id") == flight.get("id")), None)
    vehicle = ((ride or {}).get("spacecraft") or {}).get("name")
    leaves = parse((ride or {}).get("mission_end"))
    days = typical_days(mission or vehicle)
    estimated = leaves is None
    if estimated and launched:
        leaves = launched + timedelta(days=days)

    return {
        "name": astronaut.get("name"),
        "role": role,
        "agency": (astronaut.get("agency") or {}).get("abbrev") or (astronaut.get("agency") or {}).get("name"),
        "countries": [{"name": n.get("name"), "code": n.get("alpha_2_code")} for n in astronaut.get("nationality") or []],
        "image": (astronaut.get("image") or {}).get("thumbnail_url") or (astronaut.get("image") or {}).get("image_url"),
        "launched": iso(launched),
        "mission": mission,
        "rocket": rocket,
        "site": location.get("name") or pad.get("name"),
        "leaves": iso(leaves),
        "leavesEstimated": estimated,
        "typicalDays": days,
        "vehicle": vehicle or mission,
    }


def build(directory):
    now = datetime.now(timezone.utc)
    stations = {s.get("id"): s for s in load(directory, "ll-stations.json")}
    expeditions = {e.get("id"): e for e in load(directory, "ll-expeditions.json")}
    in_space = {a.get("id"): a for a in load(directory, "ll-astronauts.json") if a.get("in_space")}

    out = []
    for sid, meta in STATIONS.items():
        station = stations.get(sid)
        if not station:
            continue
        crew, seen = [], set()
        active = (station.get("active_expeditions") or [{}])[0]
        expedition = expeditions.get(active.get("id"), active)

        # 1. the expedition's own crew list (only people still in space)
        for member in expedition.get("crew") or []:
            a = member.get("astronaut") or {}
            full = in_space.get(a.get("id"))
            if full:
                crew.append(describe(full, (member.get("role") or {}).get("role"), now))
                seen.add(a.get("id"))

        # 2. anyone in space whose latest flight's ride is headed to this station (newly arrived crews)
        for aid, a in in_space.items():
            if aid in seen:
                continue
            flight = latest(a.get("flights"), lambda f: f.get("net") or "") or {}
            ride = next((l for l in a.get("landings") or []
                         if (l.get("launch") or {}).get("id") == flight.get("id")), None)
            if ride and (ride.get("destination") or "") == station.get("name"):
                crew.append(describe(a, "Crew", now))
                seen.add(aid)

        crew.sort(key=lambda c: (c["role"] != "Commander", c["launched"] or "", c["name"] or ""))
        out.append({
            "id": sid,
            "name": station.get("name"),
            "short": meta["short"],
            "match": meta["match"],
            "expedition": expedition.get("name"),
            "expeditionStart": expedition.get("start"),
            "crew": crew,
        })
    return {"updated": iso(now), "source": "The Space Devs - Launch Library 2", "stations": out}


if __name__ == "__main__":
    result = build(sys.argv[1])
    with open(f"{sys.argv[1]}/crew.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, separators=(",", ":"))
    for s in result["stations"]:
        print(f"{s['short']}: {len(s['crew'])} aboard")
