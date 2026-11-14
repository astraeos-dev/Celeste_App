"""
tests/test_constellation_chart.py — The constellation charts (constellation_chart.py, v4.24)

The outlines (d3-celestial's J2000 version of the IAU boundaries) are checked
against the IAU's areas and against Skyfield's own constellation lookup.
"""
import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import constellation_chart as cc  # noqa: E402
import i18n  # noqa: E402

# IAU areas, square degrees (Delporte's boundaries)
IAU_AREAS = {"Hya": 1302.844, "UMa": 1279.660, "Ori": 594.120, "And": 722.278, "UMi": 255.864, "Oct": 291.045,
             "Cru": 68.447, "Ser": 636.928, "Dra": 1082.952, "Cep": 587.787, "Psc": 889.417, "Equ": 71.641}


@pytest.fixture(scope="module")
def sky():
    import charts
    import planner
    from star_catalog import CATALOG
    return CATALOG, charts.constellation_figures(), planner.deep_sky_catalog()


def test_the_outlines():
    rings = cc.outlines()
    assert len(rings) == 88 and len(rings["Ser"]) == 2                 # Serpens' head and tail
    assert all(ring[0] == ring[-1] for parts in rings.values() for ring in parts)


@pytest.mark.parametrize("key", IAU_AREAS)
def test_the_areas(key):
    assert cc.area(key) == pytest.approx(IAU_AREAS[key], rel=0.005)


def test_the_whole_sky():
    assert sum(cc.area(k) for k in cc.outlines()) == pytest.approx(4 * math.pi * (180 / math.pi) ** 2, rel=1e-4)


def _inside(key, ra, dec):
    """Whether the point lies in the outline of *key*: the winding of the outline, seen from the point."""
    for ring in cc.outlines()[key]:
        points = cc.densified(ring, 0.5)
        x, y = cc.project([p[0] for p in points], [p[1] for p in points], ra, dec)
        if np.isnan(x).any():                                            # far away: not around the point
            continue
        angles = np.unwrap(np.arctan2(y, x))
        if abs(angles[-1] - angles[0]) > math.pi:
            return True
    return False


def test_the_outlines_agree_with_skyfield():
    """At 300 points of the sky, the outline holding the point is Skyfield's constellation."""
    from engine import constellation_at
    rng = np.random.default_rng(42)
    agree = 0
    for _ in range(300):
        ra = rng.uniform(0, 24)
        dec = math.degrees(math.asin(rng.uniform(-1, 1)))
        key = constellation_at(ra, dec, 2451545.0)
        agree += _inside(key, ra, dec)
    assert agree >= 297                                                 # a point on a boundary may differ


def test_projection():
    x, y = cc.project(5.6, 6.0, 5.6, 6.0)
    assert float(x) == pytest.approx(0) and float(y) == pytest.approx(0)
    x, _y = cc.project(5.8, 6.0, 5.6, 6.0)
    assert float(x) < 0                                                 # east (more RA) on the left
    _x, y = cc.project(5.6, 10.0, 5.6, 6.0)
    assert float(y) > 0                                                 # north up
    assert np.isnan(cc.project(17.6, -6.0, 5.6, 6.0)[0])                # the far side of the sky


def test_best_month():
    """As the star guides have them (constellations highest at 10 pm in the middle of their month)."""
    months = {k: cc.best_month(cc.center(k)[0]) for k in ("Ori", "Vir", "Her", "Aql", "Per")}
    assert months == {"Ori": 1, "Vir": 5, "Her": 7, "Aql": 8, "Per": 12}


def test_visibility():
    assert cc.visibility("Cru", 49.6) == "none" and cc.visibility("Cru", -33.9) == "all"
    assert cc.visibility("Ori", 49.6) == "all" and cc.visibility("Sco", 49.6) == "part"
    assert cc.visibility("UMi", -33.9) == "none" and cc.visibility("Oct", 49.6) == "none"


def test_the_chart_of_orion(sky):
    stars, figures, deep_sky = sky
    scene = cc.chart("Ori", stars, figures, deep_sky)
    x0, x1, y0, y1 = scene["view"]
    assert x1 - x0 == pytest.approx(y1 - y0) and len(scene["own"]) == 1
    betelgeuse = next(s for s in scene["stars"] if s["designation"] == "α Ori")
    assert betelgeuse["label"] == "α" and betelgeuse["name"] == "Betelgeuse" and betelgeuse["own"]
    assert {"Tau", "Gem", "Mon", "Eri", "Lep"} <= {name for name, _x, _y in scene["names"]}
    assert "M42" in {o["label"] for o in scene["deep_sky"]}
    assert any(kind == "dec" and text == "+10°" for kind, text, _x, _y in scene["grid_labels"])
    for o in scene["deep_sky"] + scene["stars"]:
        assert x0 <= o["x"] <= x1 and y0 <= o["y"] <= y1


def test_facts(sky):
    stars, _figures, deep_sky = sky
    i18n.switch_lang("fr")
    info = cc.facts("Ori", 49.6, stars, deep_sky)
    assert [row[0] for row in info["stars"][:3]] == ["β Ori", "α Ori", "γ Ori"]
    assert info["objects"][0][0] == "M42" and info["month"] == 1 and info["visibility"] == "all"
    assert cc.star_line(info["stars"][0]) == "β Rigel 0,12"
    assert cc.object_line(info["objects"][0]) == "M42 · Nébuleuse · 4,0 · Nébuleuse d'Orion"
    assert cc.fact_line("Ori", info).startswith("Ori · 594 degrés carrés · au plus haut à 22 h en janvier")


@pytest.mark.parametrize("lang, phrase", [("fr", "en janvier"), ("en", "in January"), ("es", "en enero"),
                                          ("de", "im Januar")])
def test_the_month_in_a_sentence(sky, lang, phrase):
    stars, _figures, deep_sky = sky
    i18n.switch_lang(lang)
    try:
        assert phrase in cc.fact_line("Ori", cc.facts("Ori", 49.6, stars, deep_sky))
    finally:
        i18n.switch_lang("fr")


def test_the_names_by_the_edges(sky):
    """A neighbour's name near a side of the chart runs towards the middle, inside the chart."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    stars, figures, deep_sky = sky
    scene = cc.chart("Hyi", stars, figures, deep_sky)
    fig = plt.figure(figsize=(4, 4), dpi=100)
    ax = fig.add_axes((0, 0, 1, 1))
    names = {k: i18n.t(f"constellations.{k}") for k in cc.outlines()}
    cc.draw(ax, scene, names)
    fig.canvas.draw()
    box = ax.get_window_extent()
    texts = [a for a in ax.texts if a.get_text() in {n.upper() for n in names.values()}]
    assert len(texts) >= 6
    for text in texts:
        extent = text.get_window_extent()
        assert box.x0 - 1 <= extent.x0 and extent.x1 <= box.x1 + 1, text.get_text()
    plt.close(fig)


def _visible_labels(ax):
    return [(text.get_text(), text.get_window_extent()) for text in ax._celeste_labels if text.get_visible()]


@pytest.mark.parametrize("key, inches", [("Vir", 3.4), ("Sgr", 3.4), ("Sgr", 7.0), ("Ori", 5.0)])
def test_no_label_on_another(sky, key, inches):
    """In the crowded parts of the sky (the Virgo cluster, the heart of the Milky Way), a label that would
    sit on a more important one is hidden: the stars first, then the Messier and Caldwell objects."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    stars, figures, deep_sky = sky
    fig = plt.figure(figsize=(inches, inches), dpi=100)
    ax = fig.add_axes((0, 0, 1, 1))
    cc.draw(ax, cc.chart(key, stars, figures, deep_sky), {k: i18n.t(f"constellations.{k}") for k in cc.outlines()})
    shown = _visible_labels(ax)
    for i, (text, box) in enumerate(shown):
        for other, other_box in shown[i + 1:]:
            assert not box.overlaps(other_box), (text, other)
    texts = [text for text, _box in shown]
    brightest = min((s for s in cc.chart(key, stars, figures, deep_sky)["stars"] if s["label"]), key=lambda s: s["mag"])
    assert any(text.startswith(brightest["label"]) for text in texts)
    if key == "Sgr" and inches < 4:
        assert len(shown) < len(ax._celeste_labels)                     # some were hidden
    if key == "Ori":
        assert "M42" in texts
    plt.close(fig)


def test_labels_measured_again(sky):
    """A chart made smaller: its labels are measured again and still do not sit on one another."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    stars, figures, deep_sky = sky
    fig = plt.figure(figsize=(7, 7), dpi=100)
    ax = fig.add_axes((0, 0, 1, 1))
    cc.draw(ax, cc.chart("Vir", stars, figures, deep_sky), {k: i18n.t(f"constellations.{k}") for k in cc.outlines()})
    wide = len(_visible_labels(ax))
    fig.set_size_inches(3, 3)
    cc.declutter(ax)
    shown = _visible_labels(ax)
    assert len(shown) < wide
    assert not any(a.overlaps(b) for i, (_t, a) in enumerate(shown) for _u, b in shown[i + 1:])
    plt.close(fig)


@pytest.mark.parametrize("lang", ["fr", "en", "es", "de"])
@pytest.mark.parametrize("key", ["Sgr", "Ori", "Hyi", "Com", "Dor"])
def test_the_sheet_holds_on_its_page(sky, lang, key):
    """The sheet's texts on the page, and none on another: the longest names, the most objects."""
    stars, figures, deep_sky = sky
    i18n.switch_lang(lang)
    try:
        fig = cc.sheet_figure(key, 49.6 if key != "Dor" else -33.9, "Cherbourg-en-Cotentin · 49°38′ N, 1°37′ O",
                              stars, figures, deep_sky)
        page = fig.bbox
        boxes = [text.get_window_extent() for text in fig.texts]
        for box in boxes:
            assert page.x0 + 10 <= box.x0 and box.x1 <= page.x1 - 10 and page.y0 <= box.y0, box
        assert not any(a.overlaps(b) for i, a in enumerate(boxes) for b in boxes[i + 1:])
        chart_box = fig.axes[0].get_window_extent()
        assert all(not box.overlaps(chart_box) for box in boxes)
    finally:
        i18n.switch_lang("fr")


@pytest.mark.parametrize("lang", ["fr", "en", "es", "de"])
def test_the_sheet(tmp_path, sky, lang):
    stars, figures, deep_sky = sky
    i18n.switch_lang(lang)
    try:
        path = cc.sheet(str(tmp_path / "cru.pdf"), "Cru", -33.9, "Sydney", stars, figures, deep_sky)
        assert open(path, "rb").read(5) == b"%PDF-"
    finally:
        i18n.switch_lang("fr")
