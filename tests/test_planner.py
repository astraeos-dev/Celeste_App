"""
tests/test_planner.py — The night planner (planner.py) and the MPC comets (mpc.py)
"""
import math
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mpc  # noqa: E402
import planner  # noqa: E402
from engine import AstroEngine  # noqa: E402

PARIS = ZoneInfo("Europe/Paris")
CHERBOURG = (49.6333, -1.6167)
NIGHT = datetime(2026, 11, 1, 21, 30)           # Moon 49 % lit, rising at 22:42 UT


@pytest.fixture(scope="module")
def messier():
    return planner.plan(NIGHT, *CHERBOURG, 0.0, PARIS)


class TestCatalogues:
    def test_sizes(self):
        assert len(planner.catalog("messier")) == 110
        assert len(planner.catalog("caldwell")) == 109
        assert len(planner.catalog("ngc_ic")) > 12000
        assert len(planner.deep_sky_catalog()) == 12822

    def test_labels_and_names(self):
        m31 = planner.catalog("messier")[30]
        assert planner.label(m31) == "M31" and m31["id"] == "NGC 224" and m31["name"] == "Andromeda Galaxy"
        assert m31["type"] == "galaxy" and m31["major"] > 150 and m31["mag"] == 3.4
        c14 = next(o for o in planner.catalog("caldwell") if o["c"] == 14)
        assert planner.label(c14) == "C14" and c14["name"] == "Double Cluster"
        m102 = planner.catalog("messier")[101]
        assert m102["id"] == "NGC 5866"

    def test_matching_by_label_designation_or_name(self):
        m31 = planner.catalog("messier")[30]
        assert planner.matches(m31, ["m 31"]) and planner.matches(m31, ["NGC224"])
        assert planner.matches(m31, ["andromeda galaxy"]) and not planner.matches(m31, ["M3"])

    def test_custom_targets_join_every_catalogue(self):
        mine = planner.custom_target("Mon objet", 10.684, 41.269, "galaxy", "And", 30, 9.0)
        for name in planner.CATALOGS:
            assert planner.catalog(name, [mine])[-1]["id"] == "Mon objet"
        assert planner.label(mine) == "Mon objet" and planner.custom_target("x", -10, 0)["ra"] == 350.0


class TestGeometry:
    def test_airmass_is_the_secant(self):
        assert planner.airmass(90.0) == pytest.approx(1.0)
        assert planner.airmass(30.0) == pytest.approx(2.0)
        assert planner.airmass(-1.0) == np.inf

    def test_refraction(self):
        """Sæmundsson (true altitudes): 29′ for a true altitude of 0 (seen at 0.5°), 1′ at 45°,
        none with a pressure of 0."""
        assert planner.refraction(0.0) * 60 == pytest.approx(29.0, abs=0.3)
        assert planner.refraction(45.0) * 60 == pytest.approx(0.98, abs=0.05)
        assert planner.refraction(45.0, 30.0, 1010.0) < planner.refraction(45.0, -10.0, 1010.0)
        assert planner.refraction(10.0, 10.0, 0.0) == 0.0

    def test_horizon_mask(self):
        """Linear between the points, round the circle."""
        points = [(0, 10), (90, 20), (180, 0), (270, 30)]
        assert planner.horizon_altitude([45, 90, 315, 359], points) == pytest.approx([15, 20, 20, 10 + 20 / 90])
        assert planner.horizon_altitude([123.0], []) == pytest.approx([0.0])

    def test_altitudes_match_skyfield(self):
        """The planner's analytic altitudes against the engine's (DE440, Skyfield)."""
        objects = planner.catalog("messier")[:20]
        ctx_time = AstroEngine.julian_century_j2000(datetime(2026, 11, 1, 23, 0))
        alt_ref, az_ref = AstroEngine.stars_horizontal(ctx_time, *CHERBOURG, [o["ra"] / 15 for o in objects],
                                                       [o["dec"] for o in objects])
        from engine import _sky, wgs84
        here = _sky()["earth"] + wgs84.latlon(*CHERBOURG)
        t = AstroEngine._time_ut(ctx_time)
        ctx = {"here": here, "middle": t}
        ra, dec = planner._apparent(objects, ctx)
        alt, az = planner._altaz(ra, dec, np.array([(float(t.gast) * 15 + CHERBOURG[1]) % 360]), CHERBOURG[0])
        assert np.abs(alt[:, 0] - alt_ref).max() < 0.01
        assert np.abs(((az[:, 0] - az_ref + 180) % 360) - 180).max() < 0.02


class TestNight:
    def test_astronomical_night(self, messier):
        tonight = AstroEngine.tonight(NIGHT, *CHERBOURG, 0.0, PARIS)
        window = messier["window"]
        assert window["kind"] == "astro" == tonight["dark"]
        assert abs((window["start"] - tonight["dusk"]).total_seconds()) < 120
        assert abs((window["end"] - tonight["dawn"]).total_seconds()) < 120
        times = messier["times"]
        assert times[0] == window["start"] and times[-1] == window["end"]
        assert max((b - a).total_seconds() for a, b in zip(times, times[1:])) <= 600

    def test_nautical_night_in_june_at_59_degrees(self):
        window = planner.night_window(datetime(2026, 6, 21, 22), 59.3, 18.07, 0, ZoneInfo("Europe/Stockholm"))
        assert window["kind"] == "civil" or window["kind"] == "naut"

    def test_no_night_in_the_polar_day(self):
        result = planner.plan(datetime(2026, 6, 21, 22), 78.22, 15.65, 0, ZoneInfo("Arctic/Longyearbyen"))
        assert result["window"]["kind"] is None and result["deep_sky"] == [] and result["times"] == []


class TestDeepSky:
    def test_constraints_hold(self, messier):
        c = messier["constraints"]
        assert 0 < len(messier["deep_sky"]) <= c["max_targets"]
        for o in messier["deep_sky"]:
            assert o["fraction"] >= c["fraction_min"]
            assert c["size_min"] <= o["major"] <= c["size_max"]
            assert o["best"] is not None and o["alt_max"] >= c["altitude_min"]

    def test_ranked_by_the_share_of_the_night(self, messier):
        fractions = [o["fraction"] for o in messier["deep_sky"]]
        assert fractions == sorted(fractions, reverse=True)
        assert [o["label"] for o in messier["deep_sky"][:4]] == ["M33", "M34", "M45", "M31"]

    def test_m31_transits_at_22_05(self, messier):
        m31 = next(o for o in messier["deep_sky"] if o["label"] == "M31")
        assert m31["transit"].strftime("%Y-%m-%d %H:%M") == "2026-11-01 22:05"
        assert m31["alt_max"] == pytest.approx(90 - (CHERBOURG[0] - 41.4), abs=0.3)

    def test_moon_separation(self):
        near = planner.plan(NIGHT, *CHERBOURG, 0.0, PARIS, {"moon_separation_min": 0})
        far = planner.plan(NIGHT, *CHERBOURG, 0.0, PARIS, {"moon_separation_min": 100})
        assert len(far["deep_sky"]) < len(near["deep_sky"])
        lit = planner.plan(NIGHT, *CHERBOURG, 0.0, PARIS, {"moon_separation_from_illumination": True})
        assert lit["moon"]["separation_min"] == pytest.approx(lit["moon"]["illumination"])
        assert 45 < lit["moon"]["illumination"] < 52

    def test_type_size_and_magnitude_filters(self):
        result = planner.plan(NIGHT, *CHERBOURG, 0.0, PARIS, {"types": ("open_cluster",), "size_min": 0,
                                                             "magnitude_max": 6.0, "fraction_min": 0.1})
        assert result["deep_sky"] and all(o["type"] == "open_cluster" and o["mag"] <= 6.0 for o in result["deep_sky"])

    def test_horizon_mask_hides_the_south(self):
        """A wall to the south, 75° high, hides M33's culmination (71°): a smaller share of the night."""
        wall = [(0, 0), (110, 0), (120, 75), (240, 75), (250, 0)]
        constraints = {"fraction_min": 0.0}
        free = planner.plan(NIGHT, *CHERBOURG, 0.0, PARIS, constraints)
        masked = planner.plan(NIGHT, *CHERBOURG, 0.0, PARIS, constraints, horizon=wall)
        m33 = lambda r: next(o for o in r["deep_sky"] if o["label"] == "M33")   # noqa: E731
        assert m33(masked)["fraction"] < m33(free)["fraction"] - 0.2

    def test_bucket_and_done_lists(self, messier):
        """M42 never makes the cut before 22:00 (fraction) but the bucket list shows it;
        the done list takes M31 away."""
        assert "M42" not in [o["label"] for o in messier["deep_sky"]]
        lists = planner.plan(NIGHT, *CHERBOURG, 0.0, PARIS, bucket=["Orion Nebula"], done=["M31"])
        labels = [o["label"] for o in lists["deep_sky"]]
        assert "M42" in labels and "M31" not in labels
        assert next(o for o in lists["deep_sky"] if o["label"] == "M42")["bucket"] is True

    def test_custom_target(self):
        mine = planner.custom_target("Mon objet", 10.684, 41.269, "galaxy", "And", 30, 9.0)
        result = planner.plan(NIGHT, *CHERBOURG, 0.0, PARIS, custom=[mine])
        found = next(o for o in result["deep_sky"] if o["label"] == "Mon objet")
        m31 = next(o for o in result["deep_sky"] if o["label"] == "M31")
        assert found["fraction"] == pytest.approx(m31["fraction"], abs=0.02)

    def test_max_targets(self):
        result = planner.plan(NIGHT, *CHERBOURG, 0.0, PARIS, {"catalog": "ngc_ic", "max_targets": 25})
        assert len(result["deep_sky"]) == 25 and result["deep_sky_considered"] > 200     # 10′ to 300′


class TestBodiesAndComets:
    def test_bodies_of_the_night(self, messier):
        names = [b["name"] for b in messier["bodies"]]
        assert names == ["moon", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune"]
        saturn = messier["bodies"][3]
        engine_transit = AstroEngine.find_events(NIGHT, *CHERBOURG, "Saturn", PARIS)["transit"]
        assert abs((saturn["transit"] - engine_transit.replace(tzinfo=None)).total_seconds()) < 90
        assert 0 < saturn["mag"] < 1.5

    def test_comet_of_the_table(self):
        """C/2025 A6 (Lemmon), magnitude 7.6 on 25 October 2025 (JPL)."""
        result = planner.plan(datetime(2025, 10, 25, 18), *CHERBOURG, 0.0, PARIS)
        lemmon = next(c for c in result["comets"] if c["name"] == "Lemmon")
        assert lemmon["mag"] == pytest.approx(7.6, abs=0.1) and lemmon["table"] == "Lemmon"
        assert 0.5 < lemmon["earth_au"] < 0.7 and lemmon["alt_max"] > 10

    def test_comets_of_the_minor_planet_center(self):
        text = open(os.path.join(os.path.dirname(__file__), "data", "CometEls_sample.txt"), encoding="ascii").read()
        elements = mpc.parse(text)
        assert len(elements) == 6 and elements[0]["designation"] == "C/2025 A6 (Lemmon)"
        result = planner.plan(datetime(2025, 10, 25, 18), *CHERBOURG, 0.0, PARIS, mpc_comets=elements)
        names = [c["name"] for c in result["comets"]]
        assert names.count("Lemmon") == 1 and "C/2025 A6 (Lemmon)" not in names     # not twice

    def test_vectorised_magnitudes_agree(self):
        text = open(os.path.join(os.path.dirname(__file__), "data", "CometEls_sample.txt"), encoding="ascii").read()
        elements = mpc.parse(text)
        from engine import _sky
        t = _sky()["ts"].ut1_jd(AstroEngine.julian_day(datetime(2026, 11, 1)))
        rough = mpc.magnitudes(elements, t)
        for element, approx in zip(elements, rough):
            exact = mpc.magnitude(element, t)
            assert exact is not None and abs(exact - approx) < 0.1, element["designation"]


class TestWithoutPandas:
    def test_comets_without_pandas(self):
        """The Windows build leaves pandas out, which skyfield.data.mpc imports."""
        import subprocess
        code = ("import sys\n"
                "class Block:\n"
                "    def find_spec(self, name, path, target=None):\n"
                "        if name.split('.')[0] == 'pandas': raise ImportError('no pandas')\n"
                "sys.meta_path.insert(0, Block())\n"
                "import mpc\nfrom engine import _sky\n"
                "e = mpc.parse(open('tests/data/CometEls_sample.txt', encoding='ascii').read())[0]\n"
                "print(round(mpc.magnitude(e, _sky()['ts'].ut1_jd(2461346.0)), 2))\n")
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        out = subprocess.run([sys.executable, "-c", code], cwd=root, capture_output=True, text=True)
        assert out.returncode == 0, out.stderr
        assert float(out.stdout) > 10


class TestMpcFile:
    def test_refresh_keeps_a_recent_file(self, tmp_path, monkeypatch):
        sample = open(os.path.join(os.path.dirname(__file__), "data", "CometEls_sample.txt"), encoding="ascii").read()
        monkeypatch.setattr(mpc, "CACHE", str(tmp_path / "CometEls.txt"))
        (tmp_path / "CometEls.txt").write_text(sample, encoding="ascii")
        monkeypatch.setattr(mpc.urllib.request, "urlopen", lambda *a, **k: pytest.fail("no download"))
        comets, error = mpc.refresh()
        assert len(comets) == 6 and error is None

    def test_refresh_offline_keeps_what_it_has(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mpc, "CACHE", str(tmp_path / "CometEls.txt"))

        def offline(*_a, **_k):
            raise OSError("offline")
        monkeypatch.setattr(mpc.urllib.request, "urlopen", offline)
        comets, error = mpc.refresh()
        assert comets == [] and "offline" in error


class TestReport:
    def test_json(self, messier):
        import json
        data = json.loads(planner.report_json(messier, "Cherbourg"))
        assert data["place"] == "Cherbourg" and data["night"]["kind"] == "astro"
        assert data["night"]["start"] == "2026-11-01T18:33:00Z"
        assert data["deep_sky"][0]["label"] == "M33" and 0 < data["deep_sky"][0]["fraction"] <= 1
        assert data["constraints"]["airmass_max"] == 2.0 and data["bodies"][0]["name"] == "moon"
