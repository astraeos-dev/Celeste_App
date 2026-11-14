"""
transients.py — Recent novae and supernovae
===========================================
New stars come and go in the sky: a nova in our galaxy can be seen with
binoculars for a few weeks, and each year a few supernovae in nearby galaxies
get bright enough for an amateur's telescope. Céleste lists the bright ones of
the moment from two lists kept by hand:

- the active supernovae of David Bishop's "Latest Supernovae"
  (rochesterastronomy.org), a page made to be read by programs and sorted by
  brightness. It gives each object's latest magnitude, its type, its host
  galaxy, its maximum and its discovery. Extragalactic novae (in the
  Magellanic Clouds or in M31) are listed there too;
- the galactic novae confirmed by their spectrum, from Koji Mukai's "List of
  Recent Galactic Novae" (NASA Goddard). It gives their position, discovery
  date and peak magnitude.

The two lists are read again after 12 hours and kept in
~/.celeste/transients.json; a nova on both is shown once, under its variable
star name. The magnitudes change from night to night: a nova fades within
weeks, a supernova within months.

No Qt: the interface calls refresh() in the background, and tonight() for
when each object is high in a dark sky from the place.
"""
import html
import json
import math
import os
import re
import time
import urllib.request
import zlib
from datetime import date, datetime, timedelta, timezone

import numpy as np

import settings

SUPERNOVAE_URL = "https://www.rochesterastronomy.org/snimages/snactive.html"
SUPERNOVAE_PAGE = "https://www.rochesterastronomy.org/supernova.html"
NOVAE_URL = "https://asd.gsfc.nasa.gov/Koji.Mukai/novae/novae.html"
CACHE = os.path.join(settings.USER_DIR, "transients.json")
MAX_AGE_HOURS = 12.0
KEEP_MAG = 17.5               # the supernovae kept: brighter than this
NOVA_DAYS = 730               # the galactic novae kept: found in the last two years
SAME_ARCSEC = 10.0            # a nova on both lists: within this of itself
RECENT_DAYS = 60             # a magnitude older than this is no longer the object's
VISIBLE_ALT, DARK_SUN = 20.0, -12.0
_KM_S = 299792.458            # the speed of light
_HUBBLE = 70.0                # km/s per megaparsec
_LY_PER_PC = 3.26156
_MAX_PAGE = 16 * 1024 * 1024  # the supernova page is about 2 MB
_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
_CELL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S | re.I)
_SUPERNOVA_TYPE = re.compile(r"^(?:SN|SLSN|I[abc]|II)")   # Ia, Iax, Ib/c, Ic-BL, II, IIP, IIn, SLSN-I… (not ILRT)
_NOVA_TYPES = ("Nova", "EGN")                # a nova, here or in another galaxy


class TransientError(RuntimeError):
    """A list could not be read."""


# ── Reading the lists ─────────────────────────────────────────────────────────

def _cells(row, keep_breaks=False):
    """The texts of a table row's cells (line breaks kept as newlines when asked)."""
    out = []
    for cell in _CELL.findall(row):
        if keep_breaks:
            cell = re.sub(r"<br\s*/?>", "\n", cell, flags=re.I)
        text = html.unescape(re.sub(r"<[^>]+>", " ", cell))
        lines = [" ".join(line.split()) for line in text.split("\n")]
        out.append("\n".join(line for line in lines if line) if keep_breaks else " ".join(text.split()))
    return out


def _sexagesimal(text, hours):
    """Degrees (or hours) of "03:41:55.511", "-47 13 39.4"."""
    parts = re.split(r"[:\s]+", text.strip())
    if len(parts) != 3:
        raise ValueError(text)
    sign = -1.0 if parts[0].startswith("-") else 1.0
    a, b, c = abs(float(parts[0])), float(parts[1]), float(parts[2])
    value = sign * (a + b / 60.0 + c / 3600.0)
    if hours and not 0.0 <= value < 24.0 or not hours and not -90.0 <= value <= 90.0:
        raise ValueError(text)
    return value


def _day(text):
    """The date of "2026/11/10" or "2026-11-10"; None when unreadable."""
    match = re.search(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", text or "")
    if not match:
        return None
    try:
        return date(*(int(g) for g in match.groups()))
    except ValueError:
        return None


def _tidy(name):
    """The usual form of a transient's name: "AT 2026lck", "SN 2026sqf"."""
    match = re.fullmatch(r"(AT|SN)\s?(\d{4}[a-z]+)", name.strip())
    return f"{match.group(1)} {match.group(2)}" if match else name.strip()


def _float(text):
    match = re.search(r"-?\d+(?:\.\d+)?", text or "")
    return float(match.group()) if match else None


def _kind(kind_text):
    if kind_text.startswith(_NOVA_TYPES):
        return "nova"
    if _SUPERNOVA_TYPE.match(kind_text):
        return "supernova"
    return None                                  # unclassified, cataclysmic variables: left out


def parse_supernovae(text, keep_mag=KEEP_MAG):
    """
    The supernovae and extragalactic novae of the active objects' page,
    brighter than *keep_mag*.

    Returns:
        list[dict]: name ("SN 2026sqf", "AT 2026aina"), kind ("supernova" or
        "nova"), type ("Ia", "IIP", "Nova"…), host (galaxy, None for ours),
        ra (h), dec (°), mag (the latest), mag_date, stale (latest observation
        more than a month old), peak, peak_date, discovered, discoverer, aka
        (other names), z (redshift or None).
    """
    found = []
    for row in _ROW.findall(text):
        cells = _cells(row)
        if len(cells) < 14 or cells[0] == "SN":
            continue
        kind = _kind(cells[7])
        mag = _float(cells[5])
        if kind is None or mag is None or mag > keep_mag:
            continue
        try:
            ra, dec = _sexagesimal(cells[2], hours=True), _sexagesimal(cells[3], hours=False)
        except ValueError:
            continue
        code = cells[0].strip()
        name = f"SN {code}" if re.fullmatch(r"\d{4}[a-z]+", code) else _tidy(code)   # "2026sqf": a supernova
        host = cells[1].strip()
        found.append({
            "name": name, "kind": kind, "type": cells[7].strip(),
            "host": None if host.lower() in ("none", "", "n/a") else host,
            "ra": ra, "dec": dec, "mag": mag, "mag_date": _day(cells[6]), "stale": "*" in cells[5],
            "peak": _float(cells[9]), "peak_date": _day(cells[10]), "discovered": _day(cells[11]),
            "discoverer": cells[12].strip(), "aka": [a.strip() for a in cells[13].split(",") if a.strip()],
            "z": _float(cells[8]) if _float(cells[8]) and _float(cells[8]) > 0 else None,
        })
    found.sort(key=lambda o: o["mag"])
    return found


def parse_novae(text, since=None):
    """
    The galactic novae of Koji Mukai's list, found from *since* (a date) on.

    Returns:
        list[dict]: name (its variable star name, "V8056 Sgr", else its first
        name), kind "nova", type "Nova", host None, ra, dec, mag None (the
        list gives the peak), peak, peak_date None, discovered, aka.
    """
    found = []
    for row in _ROW.findall(text):
        cells = _cells(row, keep_breaks=True)
        if len(cells) < 4:
            continue
        names = [n for n in cells[0].split("\n") if n]
        position = cells[1].split("\n")
        discovered = _day(cells[2])
        if not names or len(position) != 2 or discovered is None:
            continue
        if since is not None and discovered < since:
            continue
        try:
            ra, dec = _sexagesimal(position[0], hours=True), _sexagesimal(position[1], hours=False)
        except ValueError:
            continue
        names = [_tidy(n) for n in names]
        variable = next((n for n in names if re.fullmatch(r"V\d+ [A-Z][a-z]{2}", n)), None)
        name = variable or names[0]
        found.append({"name": name, "kind": "nova", "type": "Nova", "host": None, "ra": ra, "dec": dec,
                      "mag": None, "mag_date": None, "stale": False, "peak": _float(cells[3].split("\n")[0]),
                      "peak_date": None, "discovered": discovered, "discoverer": "",
                      "aka": [n for n in names if n != name], "z": None})
    return found


def separation_arcsec(a, b):
    """Angle between two objects (ra h, dec °), arcseconds."""
    ra1, dec1 = math.radians(a["ra"] * 15.0), math.radians(a["dec"])
    ra2, dec2 = math.radians(b["ra"] * 15.0), math.radians(b["dec"])
    cosine = (math.sin(dec1) * math.sin(dec2) + math.cos(dec1) * math.cos(dec2) * math.cos(ra1 - ra2))
    return math.degrees(math.acos(max(-1.0, min(1.0, cosine)))) * 3600.0


def merge(supernovae, novae):
    """
    One list: a galactic nova on both lists is shown once, under its variable
    star name, with the latest magnitude of the supernova page.
    """
    merged = [dict(n) for n in novae]
    for obj in supernovae:
        twin = next((n for n in merged if obj["kind"] == "nova" and separation_arcsec(obj, n) <= SAME_ARCSEC), None)
        if twin is None:
            merged.append(dict(obj))
            continue
        twin.update(mag=obj["mag"], mag_date=obj["mag_date"], stale=obj["stale"], peak_date=obj["peak_date"],
                    discoverer=obj["discoverer"] or twin["discoverer"])
        twin["peak"] = min(p for p in (twin["peak"], obj["peak"]) if p is not None) \
            if twin["peak"] is not None or obj["peak"] is not None else None
        twin["aka"] = [a for a in dict.fromkeys(twin["aka"] + [obj["name"]] + obj["aka"]) if a != twin["name"]]
    return merged


# ── Download and cache ────────────────────────────────────────────────────────

def _get(url, timeout):
    request = urllib.request.Request(url, headers={"User-Agent": "Celeste (transients.py)",
                                                   "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(request, timeout=timeout) as resp:
        data = resp.read(_MAX_PAGE + 1)
        encoding = resp.headers.get("Content-Encoding", "")
    if len(data) > _MAX_PAGE:
        raise TransientError("page too large")
    if "gzip" in encoding:
        decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)
        data = decompressor.decompress(data, _MAX_PAGE * 4)
    return data.decode("utf-8", "replace")


def _jsonable(objects):
    return [{k: (v.isoformat() if isinstance(v, date) else v) for k, v in o.items()} for o in objects]


def _from_json(objects):
    out = []
    for o in objects:
        o = dict(o)
        for key in ("mag_date", "peak_date", "discovered"):
            o[key] = date.fromisoformat(o[key]) if o.get(key) else None
        out.append(o)
    return out


def cache_age_hours():
    try:
        return (time.time() - os.path.getmtime(CACHE)) / 3600.0
    except OSError:
        return None


def cache_stamp():
    """When the kept lists last changed (None without them)."""
    try:
        return os.path.getmtime(CACHE)
    except OSError:
        return None


_LOADED = {}


def load():
    """The objects kept on disk (shared: not to be changed); [] without them."""
    try:
        stamp = os.path.getmtime(CACHE)
        kept = _LOADED.get(CACHE)
        if kept is not None and kept[0] == stamp:
            return kept[1]
        with open(CACHE, encoding="utf-8") as f:
            objects = _from_json(json.load(f)["objects"])
    except (OSError, ValueError, KeyError, TypeError):
        return []
    _LOADED[CACHE] = (stamp, objects)
    return objects


def refresh(today=None, timeout=30, max_age_hours=MAX_AGE_HOURS):
    """
    The novae and supernovae, the two lists read again when the kept ones are
    older than *max_age_hours*.

    Returns:
        tuple: (objects, error or None) — the kept ones when a download fails.
    """
    age = cache_age_hours()
    if age is not None and age < max_age_hours:
        kept = load()
        if kept:
            return kept, None
    today = today or datetime.now(timezone.utc).date()
    try:
        supernovae = parse_supernovae(_get(SUPERNOVAE_URL, timeout))
        novae = parse_novae(_get(NOVAE_URL, timeout), since=today - timedelta(days=NOVA_DAYS))
        if not supernovae and not novae:
            raise TransientError("no object in the lists")
        objects = merge(supernovae, novae)
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        with open(CACHE + ".part", "w", encoding="utf-8") as f:
            json.dump({"objects": _jsonable(objects)}, f, ensure_ascii=False)
        os.replace(CACHE + ".part", CACHE)
        return load(), None
    except Exception as exc:                  # network, a page that changed: the kept lists
        return load(), str(exc)


# ── What the place sees ───────────────────────────────────────────────────────

def chosen(objects, today, mag_limit=15.0, nova_days=365, recent_days=RECENT_DAYS):
    """
    The objects to show, the brightest first:

    - the supernovae and the novae of other galaxies brighter than *mag_limit*
      at a measure of the last *recent_days* days (older ones have faded, or
      nobody follows them any more);
    - the galactic novae found in the last *nova_days* days whose peak (or
      latest measure) was brighter than *mag_limit*.
    """
    since = today - timedelta(days=nova_days)
    recent = today - timedelta(days=recent_days)
    out = []
    for o in objects:
        if o["host"] is not None or o["kind"] == "supernova":
            keep = o["mag"] is not None and o["mag"] <= mag_limit and (o["mag_date"] or date.min) >= recent
        else:
            brightest = min((m for m in (o["peak"], o["mag"]) if m is not None), default=None)
            keep = (o["discovered"] is not None and o["discovered"] >= since
                    and brightest is not None and brightest <= mag_limit)
        if keep:
            out.append(o)

    def brightness(o):
        if o["mag"] is not None and (o["mag_date"] or date.min) >= recent:
            return o["mag"]
        return (o["peak"] if o["peak"] is not None else 30.0) + 5.0       # faded since its peak
    return sorted(out, key=brightness)


def distance_mly(z):
    """The distance of a galaxy of redshift *z* (Hubble's law, 70 km/s/Mpc), millions of light-years;
    rough for the nearest ones, which their own motion moves."""
    if not z or z <= 0:
        return None
    return _KM_S * z / _HUBBLE * _LY_PER_PC


def tonight(objects, start, end, lat, lon, elevation_m=0.0, min_alt=VISIBLE_ALT, step_minutes=15):
    """
    When each object is highest in the dark between *start* and *end* (UT
    datetimes: the night of the planner, the Sun below −12°) from the place.

    Returns:
        list: for each object, None when it never gets *min_alt* high in the
        dark, else a dict best (UT datetime), alt, az.
    """
    if not objects or start is None or end is None or end <= start:
        return [None] * len(objects)
    from engine import AstroEngine
    count = max(2, int((end - start).total_seconds() // (step_minutes * 60)) + 1)
    times = [start + (end - start) * i / (count - 1) for i in range(count)]
    ra = [o["ra"] for o in objects]
    dec = [o["dec"] for o in objects]
    alts, azs = [], []
    for when in times:
        alt, az = AstroEngine.stars_horizontal(AstroEngine.julian_century_j2000(when), lat, lon, ra, dec,
                                               elevation_m)
        alts.append(np.asarray(alt, dtype=float))
        azs.append(np.asarray(az, dtype=float))
    alts, azs = np.array(alts), np.array(azs)                  # (times, objects)
    best = np.argmax(alts, axis=0)
    out = []
    for i in range(len(objects)):
        j = int(best[i])
        out.append(None if alts[j, i] < min_alt else
                   {"best": times[j], "alt": float(alts[j, i]), "az": float(azs[j, i])})
    return out
