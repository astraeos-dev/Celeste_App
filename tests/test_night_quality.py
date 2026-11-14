"""
tests/test_night_quality.py — The quality of the night (night_quality.py)

The score from the darkness, the Moon, the clouds and the damp air; the best
window; the forecast of Open-Meteo read from a sample answer (the format of
the API: hourly arrays, Unix times), kept on disk for an hour.
"""
import io
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import night_quality as nq  # noqa: E402

CHERBOURG = (49.6333, -1.6167)


def _night(hours, fraction=0.0):
    """A night as AstroEngine.tonight() gives it: [(sun, moon)] from 12:00 UT, hour by hour."""
    start = datetime(2026, 11, 12, 12, 0)
    return {"moon": {"fraction": fraction},
            "hours": [{"time": start + timedelta(hours=i), "sun": sun, "moon": moon}
                      for i, (sun, moon) in enumerate(hours)]}


def _weather(night, clouds, humidity=70.0):
    """A forecast covering the night's hours: {Unix time: hour} with the given cloud cover."""
    out = {}
    for hour, cloud in zip(night["hours"], clouds):
        key = nq._forecast_key(hour["time"])
        out[key] = {"cloud": cloud, "humidity": humidity}
    return out


class TestScore:
    def test_darkness(self):
        assert nq.darkness(-30) == 1.0 and nq.darkness(-18) == 1.0
        assert nq.darkness(-15) == 0.5
        assert nq.darkness(-8) == 0.0 and nq.darkness(10) == 0.0

    def test_moon_glare(self):
        assert nq.moon_glare(1.0, -5) == 0.0                     # set
        assert nq.moon_glare(0.0, 60) == 0.0                     # new
        assert nq.moon_glare(1.0, 90) == pytest.approx(1.0)      # full, at the zenith
        assert nq.moon_glare(1.0, 10) < nq.moon_glare(1.0, 60)   # brighter sky when higher

    def test_hour_score(self):
        assert nq.hour_score(1.0, 0.0) == 100
        assert nq.hour_score(0.5, 0.0) == 50
        assert nq.hour_score(1.0, 1.0) == 30
        assert nq.hour_score(1.0, 0.0, cloud=50) == 50
        assert nq.hour_score(1.0, 0.0, cloud=100) == 0
        assert nq.hour_score(1.0, 0.0, humidity=100) == 70
        assert nq.hour_score(1.0, 0.0, humidity=80) == 100

    @pytest.mark.parametrize("score, key", [(100, "excellent"), (75, "excellent"), (60, "good"),
                                            (40, "fair"), (20, "poor"), (5, "bad"), (0, "bad")])
    def test_rating(self, score, key):
        assert nq.rating(score) == key

    def test_limiting_magnitude(self):
        assert nq.limiting_magnitude(1) == 7.8 and nq.limiting_magnitude(9) == 4.0
        assert nq.limiting_magnitude(0) is None and nq.limiting_magnitude(None) is None


class TestAssess:
    def test_no_night(self):
        q = nq.assess(_night([(10, 0)] * 6 + [(-8, 0)] * 6))
        assert q["rating"] == "no_night" and q["hours"] == [] and q["best"] is None

    def test_moonless_clear_night(self):
        night = _night([(-25, -10)] * 8)
        q = nq.assess(night, _weather(night, [0] * 8))
        assert q["rating"] == "excellent" and q["score"] == 100 and q["weather"]
        assert q["cloud"] == 0 and q["moon_up"] == 0
        assert q["best"]["start"] == night["hours"][0]["time"]
        assert q["best"]["end"] == night["hours"][-1]["time"] + timedelta(hours=1)

    def test_without_forecast_the_moon_alone(self):
        night = _night([(-25, 50)] * 6, fraction=1.0)
        q = nq.assess(night)
        assert not q["weather"] and q["cloud"] is None and q["moon_up"] == 1.0
        assert q["rating"] == "fair"

    def test_overcast_night(self):
        night = _night([(-25, -10)] * 6)
        q = nq.assess(night, _weather(night, [100] * 6))
        assert q["rating"] == "bad" and q["best"] is None

    def test_best_window_is_the_clear_spell(self):
        night = _night([(-25, -10)] * 8)
        q = nq.assess(night, _weather(night, [90, 80, 10, 0, 5, 70, 100, 100]))
        best = q["best"]
        assert best["start"] == night["hours"][2]["time"]
        assert best["end"] == night["hours"][4]["time"] + timedelta(hours=1)
        assert best["score"] >= 90

    def test_twilight_hours_count_half(self):
        q = nq.assess(_night([(-14, -10), (-25, -10)]))
        assert [h["score"] for h in q["hours"]] == [50, 100]

    def test_the_engine_night(self):
        """Cherbourg, 12–13 November 2026: a thin crescent setting early, a long dark night."""
        from engine import AstroEngine
        night = AstroEngine.tonight(datetime(2026, 11, 12, 20, 0), *CHERBOURG, 0, 1)
        assert len(night["hours"]) == 24
        q = nq.assess(night)
        assert q["rating"] in ("excellent", "good")
        times = [h["time"] for h in q["hours"]]
        assert times[0] < night["dawn"] and times[-1] > night["dusk"]
        assert night["dusk"] - timedelta(hours=1) <= q["best"]["start"] < q["best"]["end"]
        assert q["best"]["end"] <= night["dawn"] + timedelta(hours=1)


# A sample answer of Open-Meteo (the API's format: hourly arrays, Unix times, a null value)
def _answer(start=datetime(2026, 11, 12, tzinfo=timezone.utc), hours=48, cloud=20.0):
    stamps = [int(start.timestamp()) + 3600 * i for i in range(hours)]
    hourly = {"time": stamps, "cloud_cover": [cloud] * hours, "cloud_cover_low": [5.0] * hours,
              "cloud_cover_mid": [10.0] * hours, "cloud_cover_high": [15.0] * hours,
              "relative_humidity_2m": [80.0] * hours, "wind_speed_10m": [13.5] * hours,
              "visibility": [17120.0] * hours}
    hourly["visibility"][1] = None
    units = {key: "%" for key in hourly}
    units.update(time="unixtime", wind_speed_10m="km/h", visibility="m")
    return {"latitude": 49.618374, "longitude": -1.6172347, "generationtime_ms": 0.1,
            "utc_offset_seconds": 0, "timezone": "GMT", "timezone_abbreviation": "GMT",
            "elevation": 35.0, "hourly_units": units, "hourly": hourly}


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class TestForecast:
    def test_url(self):
        url = nq.forecast_url(*CHERBOURG)
        assert url.startswith("https://api.open-meteo.com/v1/forecast?")
        for part in ("latitude=49.6333", "longitude=-1.6167", "timeformat=unixtime", "forecast_days=7",
                     "cloud_cover%2Ccloud_cover_low"):
            assert part in url

    def test_parse(self):
        data = nq.parse_forecast(_answer())
        first = int(datetime(2026, 11, 12, tzinfo=timezone.utc).timestamp())
        assert len(data) == 48
        assert data[first] == {"cloud": 20.0, "low": 5.0, "mid": 10.0, "high": 15.0, "humidity": 80.0,
                               "wind": 13.5, "visibility": 17120.0}
        assert data[first + 3600]["visibility"] is None
        assert nq.parse_forecast({}) == {}

    def test_downloaded_then_kept_for_an_hour(self, tmp_path):
        cache = str(tmp_path / "weather.json")
        calls = []

        def opener(request, timeout):
            calls.append(request.full_url)
            assert "Celeste" in request.get_header("User-agent")
            return _Response(json.dumps(_answer()).encode("utf-8"))

        now = datetime(2026, 11, 12, 18, 0, tzinfo=timezone.utc)
        data = nq.load_forecast(*CHERBOURG, now=now, opener=opener, cache_file=cache)
        assert len(data) == 48 and len(calls) == 1 and os.path.isfile(cache)
        nq.load_forecast(49.65, -1.63, now=now + timedelta(minutes=30), opener=opener, cache_file=cache)
        assert len(calls) == 1                                          # same place, within the hour
        nq.load_forecast(*CHERBOURG, now=now + timedelta(minutes=61), opener=opener, cache_file=cache)
        assert len(calls) == 2                                          # an hour later
        nq.load_forecast(48.85, 2.35, now=now + timedelta(minutes=62), opener=opener, cache_file=cache)
        assert len(calls) == 3                                          # another place

    def test_answer_without_forecast(self, tmp_path):
        def opener(request, timeout):
            return _Response(json.dumps({"error": True, "reason": "Latitude must be in range"}).encode())

        with pytest.raises(ValueError, match="Latitude"):
            nq.load_forecast(*CHERBOURG, opener=opener, cache_file=str(tmp_path / "w.json"))

    def test_forecast_hours_meet_the_night(self):
        """The forecast of 19:00 UT is the one of the hour that starts at 19:00 UT."""
        night = _night([(-25, -10)] * 30)
        data = nq.parse_forecast(_answer(cloud=40.0))
        q = nq.assess(night, data)
        assert q["weather"] and q["cloud"] == pytest.approx(40.0)
        assert all(h["score"] == 60 for h in q["hours"])
