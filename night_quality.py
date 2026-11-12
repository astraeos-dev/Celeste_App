"""
night_quality.py — How good is the night for observing?
=======================================================
A score of the night, hour by hour, for observing the faint sky (deep-sky
objects, the Milky Way): how dark the sky gets (the Sun's depth under the
horizon), how much the Moon brightens it, and — when the user turns the
forecast on — the clouds and the damp air forecast by Open-Meteo
(https://open-meteo.com, CC BY 4.0: free, without key, for non-commercial
use; data credited "Weather data by Open-Meteo.com" next to them).

The light pollution of the place is not in the score (it does not change from
one night to the next): the observer gives the Bortle class of the place in
the settings, and the interface shows the naked-eye limiting magnitude it
means.

No Qt: the interface (ui/tonight.py) fetches the forecast in the background
and draws the hours.
"""
import json
import math
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import settings as prefs

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
FORECAST_DAYS = 7             # the forecast reaches 7 days ahead (Open-Meteo: up to 16)
CACHE_SECONDS = 3600          # a forecast is fetched again after an hour, or for another place
CACHE_DEGREES = 0.05          # "the same place": within 0.05° (about 5 km)
HOURLY = ("cloud_cover", "cloud_cover_low", "cloud_cover_mid", "cloud_cover_high",
          "relative_humidity_2m", "wind_speed_10m", "visibility")
_KEYS = {"cloud_cover": "cloud", "cloud_cover_low": "low", "cloud_cover_mid": "mid",
         "cloud_cover_high": "high", "relative_humidity_2m": "humidity", "wind_speed_10m": "wind",
         "visibility": "visibility"}

ASTRONOMICAL, NAUTICAL = -18.0, -12.0     # Sun's altitude: dark night, nautical twilight
GOOD_HOUR = 60                            # an hour of the best window scores this at least
RATINGS = ((75, "excellent"), (55, "good"), (35, "fair"), (15, "poor"), (0, "bad"))

# Bortle class → naked-eye limiting magnitude at the zenith (middle of the class's range)
BORTLE_NELM = {1: 7.8, 2: 7.3, 3: 6.8, 4: 6.3, 5: 5.8, 6: 5.3, 7: 4.8, 8: 4.3, 9: 4.0}


# ── The score ────────────────────────────────────────────────────────────────

def darkness(sun_alt):
    """1 in the dark night (Sun 18° under the horizon), 0.5 in nautical twilight, else 0."""
    if sun_alt <= ASTRONOMICAL:
        return 1.0
    return 0.5 if sun_alt <= NAUTICAL else 0.0


def moon_glare(fraction, moon_alt):
    """How much the Moon brightens the sky (0 to 1): its lit fraction, more when high."""
    if moon_alt <= 0.0:
        return 0.0
    return fraction * (0.4 + 0.6 * math.sin(math.radians(min(moon_alt, 90.0))))


def hour_score(dark, glare, cloud=None, humidity=None):
    """The score of an hour, 0 to 100: darkness, less the Moon's glare, the clouds and the damp air."""
    score = dark * (1.0 - 0.7 * glare)
    if cloud is not None:
        score *= 1.0 - min(100.0, max(0.0, cloud)) / 100.0
    if humidity is not None:                       # haze and dew above 85 %
        score *= 1.0 - 0.3 * min(1.0, max(0.0, (humidity - 85.0) / 15.0))
    return int(round(100.0 * score))


def rating(score):
    """'excellent', 'good', 'fair', 'poor' or 'bad'."""
    return next(key for limit, key in RATINGS if score >= limit)


def _forecast_key(hour_start):
    """The forecast hour (Unix time) for the hour that starts at *hour_start* (UT)."""
    middle = hour_start.replace(tzinfo=timezone.utc) + timedelta(minutes=30)
    return int(middle.timestamp()) // 3600 * 3600


def assess(night, weather=None):
    """
    The quality of the night computed by AstroEngine.tonight().

    Args:
        night (dict): tonight()'s result (hours, moon, dark).
        weather (dict | None): parse_forecast()'s result, {Unix time: hour}.

    Returns:
        dict: rating ('excellent' … 'bad', or 'no_night' without a night
        darker than nautical twilight), score (0–100, the mean of the dark
        hours), hours (the hours of the night: time UT, dark, glare, cloud,
        humidity, score), best (the best window: start, end UT, score, or
        None), weather (True when the forecast covered the night), cloud (mean
        cover of the night's hours, %, or None), moon_up (share of those hours
        with the Moon up).
    """
    fraction = night["moon"]["fraction"]
    hours = []
    for hour in night.get("hours", []):
        dark = darkness(hour["sun"])
        if dark == 0.0:
            continue
        glare = moon_glare(fraction, hour["moon"])
        forecast = (weather or {}).get(_forecast_key(hour["time"]))
        cloud = forecast.get("cloud") if forecast else None
        humidity = forecast.get("humidity") if forecast else None
        hours.append({"time": hour["time"], "dark": dark, "glare": glare, "cloud": cloud,
                      "humidity": humidity, "score": hour_score(dark, glare, cloud, humidity)})
    if not hours:
        return {"rating": "no_night", "score": 0, "hours": [], "best": None, "weather": False,
                "cloud": None, "moon_up": 0.0}
    score = int(round(sum(h["score"] for h in hours) / len(hours)))
    clouds = [h["cloud"] for h in hours if h["cloud"] is not None]
    return {"rating": rating(score), "score": score, "hours": hours, "best": best_window(hours),
            "weather": bool(clouds), "cloud": sum(clouds) / len(clouds) if clouds else None,
            "moon_up": sum(1 for h in hours if h["glare"] > 0) / len(hours)}


def best_window(hours):
    """The longest run of good hours (GOOD_HOUR), else the best hour: start, end (UT), score."""
    runs, run = [], []
    for hour in hours:
        if hour["score"] >= GOOD_HOUR and (not run or hour["time"] - run[-1]["time"] <= timedelta(hours=1)):
            run.append(hour)
        else:
            if run:
                runs.append(run)
            run = [hour] if hour["score"] >= GOOD_HOUR else []
    if run:
        runs.append(run)
    if not runs:
        top = max(hours, key=lambda h: h["score"])
        if top["score"] == 0:
            return None
        runs = [[top]]
    best = max(runs, key=lambda r: (len(r), sum(h["score"] for h in r)))
    return {"start": best[0]["time"], "end": best[-1]["time"] + timedelta(hours=1),
            "score": int(round(sum(h["score"] for h in best) / len(best)))}


def limiting_magnitude(bortle):
    """The naked-eye limiting magnitude of a Bortle class (1 to 9), or None."""
    return BORTLE_NELM.get(int(bortle or 0))


# ── The forecast (Open-Meteo) ───────────────────────────────────────────────

def forecast_url(lat, lon, days=FORECAST_DAYS):
    query = {"latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}", "hourly": ",".join(HOURLY),
             "timezone": "GMT", "timeformat": "unixtime", "forecast_days": days}
    return FORECAST_URL + "?" + urllib.parse.urlencode(query)


def parse_forecast(data):
    """Open-Meteo's answer → {Unix time of the hour: {cloud, low, mid, high, humidity, wind, visibility}}."""
    hourly = data.get("hourly") or {}
    times = hourly.get("time") or []
    out = {}
    for i, stamp in enumerate(times):
        hour = {}
        for name, key in _KEYS.items():
            values = hourly.get(name) or []
            value = values[i] if i < len(values) else None
            hour[key] = None if value is None else float(value)
        out[int(stamp)] = hour
    return out


def _cache_file():
    return os.path.join(prefs.USER_DIR, "weather.json")


def load_forecast(lat, lon, now=None, opener=None, cache_file=None, user_agent="Celeste"):
    """
    The forecast for the place: from the copy on disk when it is less than an
    hour old and for the same place, else downloaded from Open-Meteo (and kept).

    Raises:
        OSError, ValueError: no network, or an answer that is not a forecast.
    """
    now = now or datetime.now(timezone.utc)
    path = cache_file or _cache_file()
    try:
        with open(path, encoding="utf-8") as f:
            cached = json.load(f)
        if (abs(cached["lat"] - lat) <= CACHE_DEGREES and abs(cached["lon"] - lon) <= CACHE_DEGREES
                and 0 <= now.timestamp() - cached["fetched"] < CACHE_SECONDS):
            return parse_forecast(cached["data"])
    except (OSError, ValueError, KeyError, TypeError):
        pass
    request = urllib.request.Request(forecast_url(lat, lon), headers={"User-Agent": user_agent})
    with (opener or urllib.request.urlopen)(request, timeout=10) as response:
        data = json.loads(response.read().decode("utf-8"))
    if not (data.get("hourly") or {}).get("time"):
        raise ValueError(data.get("reason") or "no hourly forecast in the answer")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"lat": lat, "lon": lon, "fetched": now.timestamp(), "data": data}, f)
    except OSError:
        pass                                       # read-only folder: kept in memory only
    return parse_forecast(data)
