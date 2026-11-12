"""
planner.py — The night planner: what to observe or photograph tonight
======================================================================
For one night and one place, the deep-sky objects of a catalogue that meet
the observer's constraints, the planets and the Moon, and the comets bright
enough, after the manner of uptonight (github.com/mawinkler/uptonight):

1. the night: astronomical darkness (Sun 18° below the horizon), or nautical
   then civil darkness where the Sun does not go that low;
2. every target sampled every 10 minutes through the night: altitude and
   azimuth (with the refraction of the temperature and pressure given), the
   horizon mask, the airmass and the distance to the Moon;
3. a deep-sky object is kept when it is observable — between the altitude
   limits, under the airmass limit, far enough from the Moon and above the
   horizon mask — for a large enough share of the night, and when its size,
   type and magnitude pass the filters; the bucket list always shows (when
   the object rises above the horizon), the done list never does;
4. targets ranked by that share of the night, then by their highest altitude.

Catalogues (assets/deep_sky.csv.gz, from OpenNGC, CC BY-SA 4.0;
scripts/make_deep_sky.py): Messier (110), Caldwell (109) and NGC/IC (about
12,800 objects), with the user's own targets added to each.

Independent of the interface (no Qt).
"""
import csv
import functools
import gzip
import json
import math
import os
from datetime import timedelta

import numpy as np

from engine import PLANETS, AstroEngine, _fast_time, _sky, wgs84

_DEEP_SKY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "deep_sky.csv.gz")

CATALOGS = ("messier", "caldwell", "ngc_ic")
DEEP_SKY_TYPES = ("galaxy", "galaxy_group", "globular_cluster", "open_cluster", "nebula",
                  "planetary_nebula", "supernova_remnant", "dark_nebula", "star_cloud", "asterism",
                  "double_star")

# The constraints, with uptonight's names in comments
DEFAULTS = {
    "catalog": "messier",
    "altitude_min": 30.0,               # altitude_constraint_min, degrees
    "altitude_max": 80.0,               # altitude_constraint_max
    "airmass_max": 2.0,                 # airmass_constraint (secant of the zenith distance)
    "size_min": 10.0,                   # size_constraint_min, arcminutes
    "size_max": 300.0,                  # size_constraint_max
    "fraction_min": 0.5,                # fraction_of_time_observable_threshold
    "moon_separation_min": 45.0,        # moon_separation_min, degrees
    "moon_separation_from_illumination": False,   # moon_separation_use_illumination: 1 % = 1°
    "magnitude_max": None,              # (Céleste) faintest magnitude, None for any
    "types": (),                        # type_filter: empty for every type
    "max_targets": 60,                  # max_number_within_threshold
    "comet_magnitude_max": 12.0,        # DEFAULT_MAGNITUDE_LIMIT
}
STEP_MINUTES = 10.0
_SIDEREAL_DEG_PER_HOUR = 15.04107


# ── Catalogues ────────────────────────────────────────────────────────────────

@functools.lru_cache(maxsize=1)
def deep_sky_catalog():
    """Every object of the file: dicts id, type, ra, dec (J2000, degrees), const,
    mag, major, minor (arcminutes; None when unknown), m, c (Messier and Caldwell
    numbers or None), name."""
    def number(text):
        return float(text) if text else None

    with gzip.open(_DEEP_SKY_FILE, "rt", encoding="utf-8") as f:
        return tuple({"id": r["id"], "type": r["type"], "ra": float(r["ra"]), "dec": float(r["dec"]),
                      "const": r["const"], "mag": number(r["mag"]), "major": number(r["major"]),
                      "minor": number(r["minor"]), "m": int(r["M"]) if r["M"] else None,
                      "c": int(r["C"]) if r["C"] else None, "name": r["name"]}
                     for r in csv.DictReader(f, delimiter=";"))


def label(obj):
    """"M31", "C14", "NGC 7000", or the name of a target of the user's."""
    if obj.get("custom"):
        return obj["id"]
    if obj.get("m"):
        return f"M{obj['m']}"
    if obj.get("c"):
        return f"C{obj['c']}"
    return obj["id"]


def catalog(name, custom=()):
    """The objects of catalogue *name* (CATALOGS), with the user's targets after them."""
    every = deep_sky_catalog()
    if name == "messier":
        objects = sorted((o for o in every if o["m"]), key=lambda o: o["m"])
    elif name == "caldwell":
        objects = sorted((o for o in every if o["c"]), key=lambda o: o["c"])
    else:
        objects = [o for o in every if o["id"].startswith(("NGC ", "IC "))]
    return list(objects) + [custom_target(**t) if "custom" not in t else t for t in custom]


def custom_target(name, ra, dec, type="nebula", const="", size=None, mag=None, description=""):
    """A target of the user's: *ra*, *dec* J2000 in degrees, *size* in arcminutes."""
    return {"id": str(name), "type": type if type in DEEP_SKY_TYPES else "nebula", "ra": float(ra) % 360.0,
            "dec": float(dec), "const": const, "mag": None if mag in (None, "") else float(mag),
            "major": None if size in (None, "") else float(size), "minor": None, "m": None, "c": None,
            "name": description or "", "custom": True}


def _key(text):
    return "".join(str(text).lower().split())


def matches(obj, names):
    """Is *obj* one of *names* (its label, its designation or its common name)?"""
    keys = {_key(n) for n in names}
    return bool(keys & {_key(label(obj)), _key(obj["id"]), _key(obj["name"])} - {""})


# ── The night ─────────────────────────────────────────────────────────────────

def night_window(dte, lat, lon, elevation_m=0.0, tz=0, depths=((-18.0, "astro"), (-12.0, "naut"), (-6.0, "civil"))):
    """
    The night of *dte* (UT; in the morning, the night under way): from the
    Sun going *depth* below the horizon to its coming back, for the darkest
    depth it reaches.

    Returns:
        dict: kind ("astro", "naut", "civil" or None in a polar day), start,
        end (UT datetimes, None in a polar day; the window's edges, noon to
        noon, in a polar night).
    """
    local = dte.replace(tzinfo=None) - timedelta(hours=12)
    noon = AstroEngine._local_day(local, tz)[0] + timedelta(hours=12)
    noon = noon.replace(tzinfo=None)
    jd0 = AstroEngine.julian_day(noon)
    jds = jd0 + np.arange(721) / 720.0                    # every 2 minutes
    here = _sky()["earth"] + wgs84.latlon(lat, lon, elevation_m=elevation_m)
    sun = here.at(_fast_time(jds)).observe(_sky()["sun"]).apparent().altaz()[0].degrees
    for depth, kind in depths:
        below = sun < depth
        if not below.any():
            continue
        idx = np.flatnonzero(below)
        # the longest stretch of darkness (one stretch, unless the window holds two nights' edges)
        breaks = np.flatnonzero(np.diff(idx) > 1)
        runs = np.split(idx, breaks + 1)
        run = max(runs, key=len)
        i0, i1 = int(run[0]), int(run[-1])

        def edge(i, j):
            if i < 0 or j >= len(jds):
                return float(jds[max(0, min(i, len(jds) - 1))])
            f = (depth - sun[i]) / (sun[j] - sun[i])
            return float(jds[i] + f * (jds[j] - jds[i]))

        start = edge(i0 - 1, i0) if i0 > 0 else float(jds[0])
        end = edge(i1, i1 + 1) if i1 < len(jds) - 1 else float(jds[-1])
        return {"kind": kind, "start": AstroEngine._jd_to_datetime(start, noon),
                "end": AstroEngine._jd_to_datetime(end, noon)}
    return {"kind": None, "start": None, "end": None}


def _grid(window, step_minutes=STEP_MINUTES):
    """Julian days of the samples of the night, both ends included."""
    jd0, jd1 = AstroEngine.julian_day(window["start"]), AstroEngine.julian_day(window["end"])
    n = max(2, int(math.ceil((jd1 - jd0) * 1440.0 / step_minutes)) + 1)
    return np.linspace(jd0, jd1, n)


# ── Geometry ──────────────────────────────────────────────────────────────────

def refraction(alt, temperature_c=10.0, pressure_hpa=1010.0):
    """Atmospheric refraction in degrees at the geometric altitude *alt* (Bennett,
    Meeus chap. 16, Sæmundsson's form); none with a pressure of 0."""
    alt = np.asarray(alt, dtype=float)
    if not pressure_hpa:
        return np.zeros_like(alt)
    h = np.clip(alt, -1.0, 90.0)
    r = 1.02 / np.tan(np.radians(h + 10.3 / (h + 5.11))) / 60.0
    return np.where(alt > -1.0, r * (pressure_hpa / 1010.0) * (283.0 / (273.0 + temperature_c)), 0.0)


def horizon_altitude(az, points):
    """Altitude of the horizon mask at the azimuths *az*: *points* (azimuth,
    altitude) pairs, linearly interpolated round the circle; 0 without points."""
    az = np.asarray(az, dtype=float)
    if not points:
        return np.zeros_like(az)
    pts = sorted((float(a) % 360.0, float(h)) for a, h in points)
    a = np.array([p[0] for p in pts])
    h = np.array([p[1] for p in pts])
    a = np.concatenate([a - 360.0, a, a + 360.0])
    h = np.concatenate([h, h, h])
    return np.interp(az % 360.0, a, h)


def airmass(alt):
    """Secant of the zenith distance, as uptonight (infinite below the horizon)."""
    alt = np.asarray(alt, dtype=float)
    with np.errstate(divide="ignore"):
        return np.where(alt > 0.0, 1.0 / np.sin(np.radians(np.maximum(alt, 1e-9))), np.inf)


def _separation(ra1, dec1, ra2, dec2):
    """Angular distances in degrees between arrays of positions (degrees)."""
    ra1, dec1, ra2, dec2 = map(np.radians, (ra1, dec1, ra2, dec2))
    c = np.sin(dec1) * np.sin(dec2) + np.cos(dec1) * np.cos(dec2) * np.cos(ra1 - ra2)
    return np.degrees(np.arccos(np.clip(c, -1.0, 1.0)))


def _altaz(ra_deg, dec_deg, last_deg, lat):
    """Geometric altitude and azimuth (north, eastward) of positions of date
    (N,) at local sidereal times (T,): arrays (N, T)."""
    h = np.radians(last_deg[None, :] - np.asarray(ra_deg)[:, None])
    d = np.radians(np.asarray(dec_deg))[:, None]
    phi = math.radians(lat)
    sin_alt = math.sin(phi) * np.sin(d) + math.cos(phi) * np.cos(d) * np.cos(h)
    alt = np.degrees(np.arcsin(np.clip(sin_alt, -1.0, 1.0)))
    az = np.degrees(np.arctan2(-np.cos(d) * np.sin(h),
                               np.sin(d) * math.cos(phi) - np.cos(d) * math.sin(phi) * np.cos(h))) % 360.0
    return alt, az


# ── The plan ──────────────────────────────────────────────────────────────────

def plan(dte, lat, lon, elevation_m=0.0, tz=0, constraints=None, horizon=(), environment=None,
         custom=(), bucket=(), done=(), mpc_comets=None, step_minutes=STEP_MINUTES):
    """
    The night planner.

    Args:
        dte: UT datetime of the night (in the morning: the night under way).
        constraints (dict): keys of DEFAULTS (the others keep their default).
        horizon: (azimuth, altitude) points of the horizon mask, degrees.
        environment (dict): temperature (°C), pressure (hPa; 0: no refraction).
        custom: targets of the user's (custom_target() keyword dicts).
        bucket, done: names of targets always shown, never shown.
        mpc_comets: comet elements from mpc.parse(), for every comet the Minor
            Planet Center follows (None: the comets of Céleste's table only).

    Returns:
        dict: window, times (UT datetimes of the samples), moon (illumination
        %, separation used), constraints, deep_sky, bodies, comets: lists of
        dicts (see _deep_sky, _bodies, _comets); deep_sky_considered.
    """
    c = dict(DEFAULTS, **(constraints or {}))
    env = {"temperature": 10.0, "pressure": 1010.0, **(environment or {})}
    window = night_window(dte, lat, lon, elevation_m, tz)
    out = {"window": window, "constraints": c, "environment": env, "horizon": list(horizon),
           "times": [], "moon": None, "deep_sky": [], "bodies": [], "comets": [], "deep_sky_considered": 0}
    if window["kind"] is None:
        return out
    jds = _grid(window, step_minutes)
    times = _fast_time(jds)
    out["times"] = [AstroEngine._jd_to_datetime(float(j), window["start"]) for j in jds]
    sky = _sky()
    here = sky["earth"] + wgs84.latlon(lat, lon, elevation_m=elevation_m)
    observer = here.at(times)
    moon_ra, moon_dec, _ = observer.observe(sky["moon"]).apparent().radec(epoch="date")
    middle = _fast_time(float(jds[len(jds) // 2]))
    from skyfield import almanac
    illumination = 100.0 * float(almanac.fraction_illuminated(sky["eph"], "moon", middle))
    separation = illumination if c["moon_separation_from_illumination"] else float(c["moon_separation_min"])
    out["moon"] = {"illumination": illumination, "separation_min": separation}
    context = {"lat": lat, "lon": lon, "jds": jds, "times": out["times"], "here": here, "observer": observer,
               "last": (np.asarray(times.gast) * 15.0 + lon) % 360.0, "moon": (moon_ra._degrees, moon_dec.degrees),
               "env": env, "horizon": horizon, "c": c, "separation": separation, "middle": middle}
    out["deep_sky"], out["deep_sky_considered"] = _deep_sky(context, custom, bucket, done)
    out["bodies"] = _bodies(context)
    out["comets"] = _comets(context, dte, lat, lon, elevation_m, tz, mpc_comets)
    return out


def _observable(alt, az, ctx, moon_sep=None):
    """Samples (N, T) where the targets meet the constraints."""
    c = ctx["c"]
    ok = (alt >= c["altitude_min"]) & (alt <= c["altitude_max"]) & (airmass(alt) <= c["airmass_max"])
    ok &= alt > horizon_altitude(az, ctx["horizon"])
    if moon_sep is not None:
        ok &= moon_sep >= ctx["separation"]
    return ok


def _apparent(objects, ctx):
    """Apparent right ascension and declination of date (degrees) at the middle of the night."""
    from skyfield.api import Star
    stars = Star(ra_hours=np.array([o["ra"] for o in objects]) / 15.0,
                 dec_degrees=np.array([o["dec"] for o in objects]))
    ra, dec, _ = ctx["here"].at(ctx["middle"]).observe(stars).apparent().radec(epoch="date")
    return np.atleast_1d(ra._degrees), np.atleast_1d(dec.degrees)


def _summary(alt, az, ok, ctx, i):
    """What the tables show of target *i*: start position, highest point, best stretch."""
    times = ctx["times"]
    k = int(np.argmax(alt[i]))
    best = None
    flags = ok[i]
    if flags.any():
        idx = np.flatnonzero(flags)
        runs = np.split(idx, np.flatnonzero(np.diff(idx) > 1) + 1)
        run = max(runs, key=len)
        best = (times[int(run[0])], times[int(run[-1])])
    return {"alt_start": float(alt[i, 0]), "az_start": float(az[i, 0]), "alt_max": float(alt[i, k]),
            "az_max": float(az[i, k]), "time_max": times[k], "fraction": float(flags.mean()),
            "best": best, "altitudes": alt[i].copy(), "azimuths": az[i].copy()}


def _transit(ra_deg, ctx):
    """Meridian transit nearest the middle of the night (UT datetime)."""
    jd_mid = float(ctx["jds"][len(ctx["jds"]) // 2])
    last_mid = float(ctx["last"][len(ctx["jds"]) // 2])
    hours = ((ra_deg - last_mid + 180.0) % 360.0 - 180.0) / _SIDEREAL_DEG_PER_HOUR
    return AstroEngine._jd_to_datetime(jd_mid + hours / 24.0, ctx["times"][0])


def _deep_sky(ctx, custom, bucket, done):
    c = ctx["c"]
    objects = [o for o in catalog(c["catalog"], custom) if not matches(o, done)] if done else \
        catalog(c["catalog"], custom)
    if not objects:
        return [], 0
    wanted = [matches(o, bucket) for o in objects] if bucket else [False] * len(objects)
    types = set(c["types"] or ())

    def passes(o):
        size = o["major"]
        if size is not None and not (c["size_min"] <= size <= c["size_max"]):
            return False
        if size is None and c["size_min"] > 0 and not o.get("custom"):
            return False
        if types and o["type"] not in types:
            return False
        if c["magnitude_max"] is not None and (o["mag"] is None or o["mag"] > c["magnitude_max"]):
            return False
        return True

    keep = [w or passes(o) for o, w in zip(objects, wanted)]
    objects = [o for o, k in zip(objects, keep) if k]
    wanted = [w for w, k in zip(wanted, keep) if k]
    if not objects:
        return [], 0
    ra, dec = _apparent(objects, ctx)
    alt, az = _altaz(ra, dec, ctx["last"], ctx["lat"])
    alt = alt + refraction(alt, ctx["env"]["temperature"], ctx["env"]["pressure"])
    moon_ra, moon_dec = ctx["moon"]
    sep = _separation(ra[:, None], dec[:, None], moon_ra[None, :], moon_dec[None, :])
    ok = _observable(alt, az, ctx, sep)
    fraction = ok.mean(axis=1)
    rises = (alt > horizon_altitude(az, ctx["horizon"])) & (alt > 0)
    chosen = [i for i in range(len(objects))
              if (fraction[i] >= c["fraction_min"] and fraction[i] > 0) or (wanted[i] and rises[i].any())]
    chosen.sort(key=lambda i: (-fraction[i], -float(alt[i].max())))
    in_bucket = [i for i in chosen if wanted[i]]
    others = [i for i in chosen if not wanted[i]][:max(0, int(c["max_targets"]))]
    rank = {i: n for n, i in enumerate(chosen)}
    result = []
    for i in sorted(in_bucket + others, key=rank.get):
        o = objects[i]
        result.append({**o, "label": label(o), "bucket": wanted[i], "transit": _transit(float(ra[i]), ctx),
                       "moon_separation": float(sep[i].min()), **_summary(alt, az, ok, ctx, i)})
    return result, len(objects)


def _bodies(ctx):
    """The Moon and the planets that rise above the horizon mask during the night."""
    sky, result = _sky(), []
    tc = (float(ctx["jds"][len(ctx["jds"]) // 2]) - 2451545.0) / 36525.0
    mags = AstroEngine.observations(tc, list(PLANETS))
    for name in ("moon",) + PLANETS:
        alt, az, _ = ctx["observer"].observe(AstroEngine._target(name)).apparent().altaz()
        alt, az = alt.degrees[None, :], az.degrees[None, :]
        up = (alt > horizon_altitude(az, ctx["horizon"])) & (alt > 0)
        if not up.any():
            continue
        ra, _dec, _ = ctx["observer"].observe(AstroEngine._target(name)).apparent().radec(epoch="date")
        item = {"name": name, "mag": None if name == "moon" else mags[name]["mag"],
                "transit": _transit(float(ra._degrees[len(ctx["jds"]) // 2]), ctx),
                **_summary(alt, az, up, ctx, 0)}
        result.append(item)
    return result


def _comets(ctx, dte, lat, lon, elevation_m, tz, mpc_comets):
    """
    Comets brighter than comet_magnitude_max that rise above the horizon mask
    while the Sun is 6° below the horizon: those of Céleste's table and, with
    *mpc_comets*, every comet the Minor Planet Center follows.
    """
    limit = ctx["c"]["comet_magnitude_max"]
    window = night_window(dte, lat, lon, elevation_m, tz, depths=((-6.0, "civil"),))
    if window["kind"] is None:
        return []
    jds = _grid(window, 15.0)
    times = _fast_time(jds)
    sky = _sky()
    observer = ctx["here"].at(times)
    middle = times[len(jds) // 2]
    tc = (float(jds[len(jds) // 2]) - 2451545.0) / 36525.0
    candidates = []
    table = AstroEngine.comets_at(tc)
    seen = AstroEngine.observations(tc, table) if table else {}
    for name in table:
        if seen[name]["mag"] <= limit:
            candidates.append((name, AstroEngine._target(name), seen[name]["mag"], name))
    if mpc_comets:
        import mpc
        from engine import COMET_DESIGNATIONS
        ours = {d.split(" (")[0] for d in COMET_DESIGNATIONS.values()}
        others = [e for e in mpc_comets if e["designation"].split(" (")[0] not in ours]
        rough = mpc.magnitudes(others, middle)
        for element, approx in zip(others, rough):
            if not approx <= limit + 1.0:                 # NaN and the faint ones out, then exactly
                continue
            mag = mpc.magnitude(element, middle)
            if mag is not None and mag <= limit:
                candidates.append((element["designation"], mpc.target(element), mag, None))
    result = []
    times_dt = [AstroEngine._jd_to_datetime(float(j), window["start"]) for j in jds]
    for name, target, mag, table_name in candidates:
        apparent = observer.observe(target).apparent()
        alt, az, dist = apparent.altaz()
        alt, az = alt.degrees, az.degrees
        up = (alt > horizon_altitude(az, ctx["horizon"])) & (alt > 0)
        if not up.any():
            continue
        helio = (target.at(middle) - sky["sun"].at(middle)).distance().au
        rise = next((times_dt[i] for i in range(1, len(alt)) if up[i] and not up[i - 1]), None)
        setting = next((times_dt[i] for i in range(1, len(alt)) if up[i - 1] and not up[i]), None)
        k = int(np.argmax(alt))
        result.append({"name": name, "table": table_name, "mag": float(mag),
                       "earth_au": float(dist.au[len(jds) // 2]), "sun_au": float(helio),
                       "alt_start": float(alt[0]), "az_start": float(az[0]), "alt_max": float(alt[k]),
                       "az_max": float(az[k]), "time_max": times_dt[k], "rise": rise, "set": setting,
                       "fraction": float(up.mean()), "altitudes": alt.copy(), "azimuths": az.copy()})
    result.sort(key=lambda r: r["mag"])
    return result


# ── Report ────────────────────────────────────────────────────────────────────

def report_json(result, place=""):
    """The plan as JSON (UTF-8 text): what uptonight's json report holds, times in UT."""
    def iso(dt):
        return None if dt is None else dt.replace(microsecond=0).isoformat() + "Z"

    def clean(item, keys):
        out = {}
        for k in keys:
            v = item.get(k)
            if hasattr(v, "isoformat"):
                v = iso(v)
            elif isinstance(v, tuple):
                v = [iso(x) for x in v]
            elif isinstance(v, float):
                v = round(v, 4)
            out[k] = v
        return out

    window = result["window"]
    data = {"place": place, "night": {"kind": window["kind"], "start": iso(window["start"]), "end": iso(window["end"])},
            "moon": result["moon"], "constraints": {k: list(v) if isinstance(v, tuple) else v
                                                    for k, v in result["constraints"].items()},
            "environment": result["environment"], "horizon": result["horizon"],
            "deep_sky": [clean(o, ("label", "id", "name", "type", "const", "mag", "major", "minor", "ra", "dec",
                                   "alt_start", "az_start", "alt_max", "time_max", "transit", "fraction",
                                   "best", "moon_separation", "bucket")) for o in result["deep_sky"]],
            "bodies": [clean(b, ("name", "mag", "alt_max", "az_max", "time_max", "transit", "fraction"))
                       for b in result["bodies"]],
            "comets": [clean(c, ("name", "mag", "earth_au", "sun_au", "alt_start", "az_start", "alt_max",
                                 "rise", "set", "fraction")) for c in result["comets"]]}
    return json.dumps(data, ensure_ascii=False, indent=2)


def report_html(data):
    """
    The night's tracks as an interactive page (HTML, no network needed), after
    uptonight's sky plots: a map of the sky (zenith at the centre, north up, east on
    the left) with the path of each target through the night and its hours, the
    altitude–time chart beside it, a slider to move through the night, a legend to
    show or hide each target, and the details of a point under the mouse.

    Args:
        data (dict): title, subtitle, times (local "HH:MM" of the samples), tracks
            ([{name, kind, alt, az, on}], kind: deep_sky, body, comet, moon),
            horizon ([[az, alt], ...]), limits ([altitude min, max]), labels
            (north, east, south, west, altitude, azimuth, time, hide_all, show_all,
            moon, made_with).
    """
    def r(v):
        return None if v is None or v != v else round(float(v), 2)

    clean = dict(data)
    clean["tracks"] = [dict(t, alt=[r(v) for v in t["alt"]], az=[r(v) for v in t["az"]]) for t in data["tracks"]]
    payload = json.dumps(clean, ensure_ascii=False).replace("</", "<\\/")
    return _HTML_TEMPLATE.replace("__TITLE__", _escape(data.get("title", ""))).replace("__DATA__", payload)


def _escape(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


_HTML_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--bg:#0b0f17;--card:#121826;--line:#26324a;--ink:#e8ecf2;--soft:#9aa6b8;--gold:#f2b84b;--sky:#0e1524}
@media (prefers-color-scheme: light){:root{--bg:#f4f6fa;--card:#ffffff;--line:#d5dbe6;--ink:#141a26;--soft:#5b6578;--gold:#b7791f;--sky:#eef2f8}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
header{padding:20px 24px 8px}h1{margin:0;font-size:20px;font-weight:600}header p{margin:4px 0 0;color:var(--soft)}
main{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr) 260px;gap:16px;padding:12px 24px 24px}
@media (max-width:1100px){main{grid-template-columns:1fr}}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px}
svg{width:100%;height:auto;display:block}
.controls{display:flex;align-items:center;gap:12px;padding:0 24px}
input[type=range]{flex:1;accent-color:var(--gold)}#now{font-variant-numeric:tabular-nums;min-width:56px;font-weight:600}
.legend label{display:flex;align-items:center;gap:8px;padding:3px 0;cursor:pointer}
.legend .sw{width:14px;height:4px;border-radius:2px;display:inline-block}
.legend h3{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--soft);margin:12px 0 4px}
.legend button{background:none;border:1px solid var(--line);color:var(--ink);border-radius:6px;padding:3px 8px;margin-right:6px;cursor:pointer}
#tip{position:fixed;pointer-events:none;background:var(--card);border:1px solid var(--line);border-radius:6px;padding:6px 8px;font-size:12px;display:none;white-space:nowrap}
footer{color:var(--soft);font-size:12px;padding:0 24px 20px}
</style></head><body>
<header><h1 id="title"></h1><p id="subtitle"></p></header>
<div class="controls"><span id="now"></span><input id="slider" type="range" min="0" value="0" step="1"></div>
<main><div class="card"><svg id="map" viewBox="-1.18 -1.18 2.36 2.36"></svg></div>
<div class="card"><svg id="chart" viewBox="0 0 640 420"></svg></div>
<div class="card legend" id="legend"></div></main>
<div id="tip"></div><footer id="made"></footer>
<script>
const D = __DATA__;
const L = D.labels, NS = "http://www.w3.org/2000/svg";
const COLORS = ["#f2b84b","#7cc4ff","#ff8a80","#9be7a4","#d7a8ff","#ffd180","#80deea","#f48fb1","#c5e1a5","#b0bec5","#ffab91","#90caf9"];
D.tracks.forEach((t,i)=>{t.color = t.kind==="moon" ? "#cfd8e3" : COLORS[i % COLORS.length];});
const $ = id => document.getElementById(id);
const HOUR = D.times.map((s,i)=> i>0 && s.slice(0,2)!==D.times[i-1].slice(0,2));   // the first sample of each hour
$("title").textContent = D.title; $("subtitle").textContent = D.subtitle; $("made").textContent = L.made_with;
function el(tag, attrs, parent){const e=document.createElementNS(NS,tag);for(const k in attrs)e.setAttribute(k,attrs[k]);if(parent)parent.appendChild(e);return e;}
function xy(alt, az){const r=(90-alt)/90, a=az*Math.PI/180;return [-Math.sin(a)*r, -Math.cos(a)*r];}
const tip = $("tip");
function showTip(ev, t, i){tip.style.display="block";tip.style.left=(ev.clientX+14)+"px";tip.style.top=(ev.clientY+10)+"px";
  tip.textContent = t.name+" — "+D.times[i]+" · "+L.altitude+" "+t.alt[i].toFixed(0)+"° · "+L.azimuth+" "+t.az[i].toFixed(0)+"°";}
function hideTip(){tip.style.display="none";}
// the map
const map = $("map");
el("circle",{cx:0,cy:0,r:1,fill:"var(--sky)",stroke:"var(--line)","stroke-width":0.006},map);
for(const a of [30,60]) el("circle",{cx:0,cy:0,r:(90-a)/90,fill:"none",stroke:"var(--line)","stroke-width":0.004},map);
el("circle",{cx:0,cy:0,r:(90-D.limits[0])/90,fill:"none",stroke:"var(--soft)","stroke-width":0.004,"stroke-dasharray":"0.02 0.015"},map);
if(D.horizon.length){let d="";const pts=[...D.horizon].sort((p,q)=>p[0]-q[0]);
  for(let az=0;az<=360;az+=2){let h=0;for(let k=0;k<pts.length-1;k++){if(az>=pts[k][0]&&az<=pts[k+1][0]){const f=(az-pts[k][0])/((pts[k+1][0]-pts[k][0])||1);h=pts[k][1]+f*(pts[k+1][1]-pts[k][1]);}}
    const [x,y]=xy(Math.max(h,0),az);d+=(az?"L":"M")+x.toFixed(4)+" "+y.toFixed(4);}
  for(let az=360;az>=0;az-=2){const [x,y]=xy(0,az);d+="L"+x.toFixed(4)+" "+y.toFixed(4);}
  el("path",{d:d+"Z",fill:"var(--line)",opacity:0.6},map);}
for(const [lab,az] of [[L.north,0],[L.east,90],[L.south,180],[L.west,270]]){const [x,y]=xy(-9,az);
  const t=el("text",{x:x,y:y,"font-size":0.07,"text-anchor":"middle","dominant-baseline":"middle",fill:"var(--soft)"},map);t.textContent=lab;}
const layers = {}, dots = {}, lines = {};
D.tracks.forEach((t,ti)=>{const g=el("g",{},map);layers[ti]=g;let d="",pen=false;
  t.alt.forEach((a,i)=>{if(a===null||a<0){pen=false;return;}const [x,y]=xy(a,t.az[i]);d+=(pen?"L":"M")+x.toFixed(4)+" "+y.toFixed(4);pen=true;});
  el("path",{d:d,fill:"none",stroke:t.color,"stroke-width":t.kind==="moon"?0.008:0.01,"stroke-dasharray":t.kind==="moon"?"0.015 0.012":"none"},g);
  t.alt.forEach((a,i)=>{if(a===null||a<0)return;const [x,y]=xy(a,t.az[i]);const hour=HOUR[i];
    const c=el("circle",{cx:x,cy:y,r:hour?0.014:0.02,fill:hour?t.color:"transparent"},g);
    c.addEventListener("mousemove",ev=>showTip(ev,t,i));c.addEventListener("mouseleave",hideTip);
    if(hour){const lab=el("text",{x:x+0.02,y:y-0.015,"font-size":0.035,fill:"var(--soft)"},g);lab.textContent=D.times[i].slice(0,2);}});
  let k=0;t.alt.forEach((a,i)=>{if(a!==null&&a>t.alt[k])k=i;});
  if(t.alt[k]>0){const [x,y]=xy(t.alt[k],t.az[k]);const n=el("text",{x:x,y:y-0.035,"font-size":0.045,"text-anchor":"middle",fill:t.color,"font-weight":600},g);n.textContent=t.name;}
  dots[ti]=el("circle",{r:0.028,fill:t.color,stroke:"var(--bg)","stroke-width":0.006},g);});
// the chart
const chart=$("chart"),X0=48,X1=624,Y0=388,Y1=16,n=D.times.length;
const cx=i=>X0+(X1-X0)*i/Math.max(n-1,1), cy=a=>Y0-(Y0-Y1)*Math.max(a,0)/90;
el("rect",{x:X0,y:Y1,width:X1-X0,height:Y0-Y1,fill:"var(--sky)"},chart);
el("rect",{x:X0,y:cy(D.limits[0]),width:X1-X0,height:Y0-cy(D.limits[0]),fill:"var(--line)",opacity:0.45},chart);
el("rect",{x:X0,y:Y1,width:X1-X0,height:cy(D.limits[1])-Y1,fill:"var(--line)",opacity:0.45},chart);
for(let a=0;a<=90;a+=15){el("line",{x1:X0,x2:X1,y1:cy(a),y2:cy(a),stroke:"var(--line)","stroke-width":0.6},chart);
  const t=el("text",{x:X0-6,y:cy(a)+4,"font-size":11,"text-anchor":"end",fill:"var(--soft)"},chart);t.textContent=a+"°";}
D.times.forEach((s,i)=>{if(!HOUR[i])return;el("line",{x1:cx(i),x2:cx(i),y1:Y1,y2:Y0,stroke:"var(--line)","stroke-width":0.6},chart);
  const t=el("text",{x:cx(i),y:Y0+16,"font-size":11,"text-anchor":"middle",fill:"var(--soft)"},chart);t.textContent=s.slice(0,2);});
D.tracks.forEach((t,ti)=>{let d="",pen=false;t.alt.forEach((a,i)=>{if(a===null||a<0){pen=false;return;}d+=(pen?"L":"M")+cx(i).toFixed(1)+" "+cy(a).toFixed(1);pen=true;});
  lines[ti]=el("path",{d:d,fill:"none",stroke:t.color,"stroke-width":t.kind==="moon"?1.5:2,"stroke-dasharray":t.kind==="moon"?"3 3":"none"},chart);
  lines[ti].addEventListener("mousemove",ev=>{const b=chart.getBoundingClientRect();const i=Math.round((ev.clientX-b.left)/b.width*640-X0)/(X1-X0)*(n-1);showTip(ev,t,Math.max(0,Math.min(n-1,Math.round(i))));});
  lines[ti].addEventListener("mouseleave",hideTip);});
const cursor=el("line",{y1:Y1,y2:Y0,stroke:"var(--gold)","stroke-width":1.2},chart);
// the legend
const legend=$("legend");const groups={};
const tools=document.createElement("div");legend.appendChild(tools);
for(const [lab,on] of [[L.show_all,true],[L.hide_all,false]]){const b=document.createElement("button");b.textContent=lab;b.onclick=()=>{D.tracks.forEach((t,i)=>{t.on=on;boxes[i].checked=on;});apply();};tools.appendChild(b);}
const boxes={};
D.tracks.forEach((t,ti)=>{if(!groups[t.kind]){const h=document.createElement("h3");h.textContent=L["group_"+t.kind]||t.kind;legend.appendChild(h);groups[t.kind]=true;}
  const lab=document.createElement("label");const box=document.createElement("input");box.type="checkbox";box.checked=t.on;boxes[ti]=box;
  box.onchange=()=>{t.on=box.checked;apply();};const sw=document.createElement("span");sw.className="sw";sw.style.background=t.color;
  lab.append(box,sw,document.createTextNode(t.name));legend.appendChild(lab);});
function apply(){D.tracks.forEach((t,ti)=>{layers[ti].style.display=t.on?"":"none";lines[ti].style.display=t.on?"":"none";});}
// the time
const slider=$("slider");slider.max=n-1;
function at(i){$("now").textContent=D.times[i];cursor.setAttribute("x1",cx(i));cursor.setAttribute("x2",cx(i));
  D.tracks.forEach((t,ti)=>{const a=t.alt[i];if(a===null||a<0){dots[ti].style.display="none";return;}
    const [x,y]=xy(a,t.az[i]);dots[ti].style.display="";dots[ti].setAttribute("cx",x);dots[ti].setAttribute("cy",y);});}
slider.oninput=()=>at(+slider.value);slider.value=Math.floor((n-1)/2);at(+slider.value);apply();
</script></body></html>
"""
