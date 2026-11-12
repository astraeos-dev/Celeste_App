"""
mpc.py — The comets of the Minor Planet Center, downloaded and kept
===================================================================
The night planner can look at every comet the Minor Planet Center follows
(about a thousand), not only those of Céleste's table: their orbital elements
(file CometEls.txt, one comet per line) are downloaded from
minorplanetcenter.net and kept in ~/.celeste/CometEls.txt, refreshed after a
week. Positions come from two-body orbits (Skyfield), good to a few
arcminutes near the elements' epoch; magnitudes from the MPC's parameters,
m = H + 5 log10 Δ + 2.5 G log10 r.

No Qt here: the interface calls refresh() in the background (gui.py).
"""
import math
import os
import time
import urllib.request

import settings

URL = "https://www.minorplanetcenter.net/iau/MPCORB/CometEls.txt"
CACHE = os.path.join(settings.USER_DIR, "CometEls.txt")
MAX_AGE_DAYS = 7.0
_GM_SUN_KM3_S2 = 1.32712440041e11


class MpcError(RuntimeError):
    """The comet elements could not be downloaded."""


def parse(text):
    """The comets of a CometEls.txt text: dicts designation, perihelion (year,
    month, day TT), q (AU), e, i, node, peri (degrees), H, G; lines that cannot
    be read are left out."""
    comets = []
    for line in text.splitlines():
        if len(line) < 102:
            continue
        try:
            comets.append({
                "designation": line[102:158].strip() or line[0:12].strip(),
                "perihelion": (int(line[14:18]), int(line[19:21]), float(line[22:29])),
                "q": float(line[30:39]), "e": float(line[41:49]), "peri": float(line[51:59]),
                "node": float(line[61:69]), "i": float(line[71:79]),
                "H": float(line[91:95]) if line[91:95].strip() else None,
                "G": float(line[96:100]) if line[96:100].strip() else None,
            })
        except ValueError:
            continue
    return comets


def target(element):
    """
    Skyfield vector of the comet, from the Solar System barycentre (as the
    planets), for observe(). What skyfield.data.mpc.comet_orbit() does,
    without that module, which imports pandas (left out of the Windows build).
    """
    from engine import _sky
    from skyfield.data.spice import inertial_frames
    from skyfield.keplerlib import _KeplerOrbit
    sky = _sky()
    q, e = element["q"], element["e"]
    p = q * 2.0 if e == 1.0 else q / (1.0 - e) * (1.0 - e * e)
    year, month, day = element["perihelion"]
    orbit = _KeplerOrbit._from_periapsis(p, e, element["i"], element["node"], element["peri"],
                                         sky["ts"].tt(year, month, day), _GM_SUN_KM3_S2, 10, element["designation"])
    orbit._rotation = inertial_frames["ECLIPJ2000"].T
    return sky["sun"] + orbit


def magnitudes(elements, time_):
    """
    Approximate magnitudes of many comets at once (numpy two-body orbits,
    within about 0.1 magnitude of magnitude()): to keep the few bright enough
    before computing them exactly. NaN without magnitude parameters.
    """
    import numpy as np
    from engine import _sky
    if not elements:
        return np.zeros(0)
    sky = _sky()
    k = 0.01720209895                                   # Gaussian gravitational constant
    q = np.array([e["q"] for e in elements])
    ecc = np.array([e["e"] for e in elements])
    inc, node, peri = (np.radians([e[key] for e in elements]) for key in ("i", "node", "peri"))
    h = np.array([np.nan if e["H"] is None else e["H"] for e in elements])
    g = np.array([np.nan if e["G"] is None else e["G"] for e in elements])
    t_peri = np.array([sky["ts"].tt(*e["perihelion"]).tt for e in elements])
    dt = float(time_.tt) - t_peri
    nu, r = np.zeros_like(q), np.zeros_like(q)
    ell, hyp = ecc < 0.9999, ecc > 1.0001
    par = ~(ell | hyp)
    if ell.any():
        a = q[ell] / (1.0 - ecc[ell])
        m = np.remainder(k / a ** 1.5 * dt[ell] + np.pi, 2 * np.pi) - np.pi
        e_ = ecc[ell]
        big = np.where(e_ > 0.8, np.pi * np.sign(m), m)
        for _ in range(60):
            big = big - (big - e_ * np.sin(big) - m) / (1.0 - e_ * np.cos(big))
        r[ell] = a * (1.0 - e_ * np.cos(big))
        nu[ell] = 2.0 * np.arctan2(np.sqrt(1 + e_) * np.sin(big / 2), np.sqrt(1 - e_) * np.cos(big / 2))
    if hyp.any():
        a = q[hyp] / (ecc[hyp] - 1.0)
        m = k / a ** 1.5 * dt[hyp]
        e_ = ecc[hyp]
        big = np.arcsinh(m / e_)
        for _ in range(60):
            big = big - (e_ * np.sinh(big) - big - m) / (e_ * np.cosh(big) - 1.0)
        r[hyp] = a * (e_ * np.cosh(big) - 1.0)
        nu[hyp] = 2.0 * np.arctan(np.sqrt((e_ + 1) / (e_ - 1)) * np.tanh(big / 2))
    if par.any():
        w = 3.0 * k / np.sqrt(2.0 * q[par] ** 3) * dt[par]
        y = np.cbrt(w / 2 + np.sqrt(w * w / 4 + 1))
        s_ = y - 1 / y
        nu[par] = 2.0 * np.arctan(s_)
        r[par] = q[par] * (1 + s_ * s_)
    u = peri + nu
    xyz = r * np.array([np.cos(node) * np.cos(u) - np.sin(node) * np.sin(u) * np.cos(inc),
                        np.sin(node) * np.cos(u) + np.cos(node) * np.sin(u) * np.cos(inc),
                        np.sin(u) * np.sin(inc)])
    eps = np.radians(23.4392911)
    earth = (sky["earth"].at(time_) - sky["sun"].at(time_)).position.au           # ICRS ≈ equatorial J2000
    earth = np.array([earth[0], earth[1] * np.cos(eps) + earth[2] * np.sin(eps),
                      -earth[1] * np.sin(eps) + earth[2] * np.cos(eps)])            # to the ecliptic
    delta = np.linalg.norm(xyz - earth[:, None], axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        return h + 5.0 * np.log10(delta) + 2.5 * g * np.log10(r)


def magnitude(element, time_):
    """Total magnitude seen from the Earth's centre at the Skyfield time *time_*; None
    without magnitude parameters or for an orbit the two-body model cannot place."""
    if element["H"] is None or element["G"] is None:
        return None
    from engine import _sky
    sky = _sky()
    try:
        comet = target(element)
        r = (comet.at(time_) - sky["sun"].at(time_)).distance().au
        delta = sky["earth"].at(time_).observe(comet).distance().au
    except (ValueError, ZeroDivisionError, OverflowError):
        return None
    if not (r > 0 and delta > 0) or math.isnan(r) or math.isnan(delta):
        return None
    return element["H"] + 5.0 * math.log10(delta) + 2.5 * element["G"] * math.log10(r)


def cache_age_days():
    """Age of the kept file in days; None without one."""
    try:
        return (time.time() - os.path.getmtime(CACHE)) / 86400.0
    except OSError:
        return None


def load():
    """The comets of the kept file; [] without one."""
    try:
        with open(CACHE, encoding="ascii", errors="replace") as f:
            return parse(f.read())
    except OSError:
        return []


def refresh(timeout=30):
    """
    The comets, downloaded again when the kept file is older than a week.

    Returns:
        tuple: (comets, error) — error is None, or the reason the download
        failed (the kept comets are returned all the same).
    """
    age = cache_age_days()
    if age is not None and age < MAX_AGE_DAYS:
        comets = load()
        if comets:
            return comets, None
    try:
        request = urllib.request.Request(URL, headers={"User-Agent": "Celeste (mpc.py)"})
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            text = resp.read().decode("ascii", "replace")
        comets = parse(text)
        if len(comets) < 100:
            raise MpcError("unreadable comet elements")
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        with open(CACHE, "w", encoding="ascii", errors="replace") as f:
            f.write(text)
        return comets, None
    except Exception as exc:  # network, file: the kept elements, if any
        return load(), str(exc)
