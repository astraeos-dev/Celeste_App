"""
Builds assets/moons.npz: the main moons of Mars, Saturn, Uranus, Neptune and
Pluto, from JPL Horizons (its satellite ephemerides MAR097, SAT441, URA184,
NEP097, PLU060).

For each moon, its state (position, km, and velocity, km/s; ICRF axes)
relative to the centre of its planet at 00:00 TDB of each day from START to
STOP. engine.py propagates the nearest state by a two-body orbit around the
planet (at most 12 hours: within a fraction of a degree, even for Phobos,
whose orbit the flattening of Mars turns by 0.44° a day). Jupiter's four
Galilean moons have their own theory in engine.py (Meeus).

Magnitudes: V at mean opposition (JPL Solar System Dynamics, planetary
satellite physical parameters), approximate.

    python scripts/make_moons.py
"""
import os
import sys
import urllib.parse
import urllib.request

import numpy as np

# name in Céleste: (Horizons id, planet, its Horizons centre, mean opposition V)
MOONS = {
    "Phobos": ("401", "Mars", "499", 11.4),
    "Deimos": ("402", "Mars", "499", 12.5),
    "Mimas": ("601", "Saturn", "699", 12.9),
    "Enceladus": ("602", "Saturn", "699", 11.7),
    "Tethys": ("603", "Saturn", "699", 10.2),
    "Dione": ("604", "Saturn", "699", 10.4),
    "Rhea": ("605", "Saturn", "699", 9.7),
    "Titan": ("606", "Saturn", "699", 8.4),
    "Hyperion": ("607", "Saturn", "699", 14.4),
    "Iapetus": ("608", "Saturn", "699", 11.0),
    "Miranda": ("705", "Uranus", "799", 15.8),
    "Ariel": ("701", "Uranus", "799", 13.7),
    "Umbriel": ("702", "Uranus", "799", 14.5),
    "Titania": ("703", "Uranus", "799", 13.5),
    "Oberon": ("704", "Uranus", "799", 13.7),
    "Triton": ("801", "Neptune", "899", 13.5),
    "Charon": ("901", "Pluto", "999", 16.8),
}
START, STOP = "2020-01-01", "2040-12-31"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "moons.npz")
API = "https://ssd.jpl.nasa.gov/api/horizons.api"


def states(command, centre):
    """Daily (jd, x, y, z, vx, vy, vz) of a moon relative to its planet's centre."""
    query = {"format": "text", "COMMAND": f"'{command}'", "EPHEM_TYPE": "'VECTORS'",
             "CENTER": f"'500@{centre}'", "START_TIME": f"'{START}'", "STOP_TIME": f"'{STOP}'",
             "STEP_SIZE": "'1d'", "VEC_TABLE": "'2'", "REF_PLANE": "'FRAME'", "OUT_UNITS": "'KM-S'",
             "CSV_FORMAT": "'YES'", "VEC_LABELS": "'NO'", "OBJ_DATA": "'NO'"}
    url = API + "?" + urllib.parse.urlencode(query)
    request = urllib.request.Request(url, headers={"User-Agent": "Celeste (make_moons.py)"})
    with urllib.request.urlopen(request, timeout=300) as resp:
        text = resp.read().decode("utf-8")
    body = text.split("$$SOE", 1)[1].split("$$EOE", 1)[0]
    rows = []
    for line in body.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        rows.append([float(parts[0])] + [float(p) for p in parts[2:8]])
    return np.array(rows)


def main():
    names, planets, mags, data = [], [], [], []
    jd = None
    for name, (command, planet, centre, mag) in MOONS.items():
        rows = states(command, centre)
        if jd is None:
            jd = rows[:, 0]
        elif len(rows) != len(jd) or np.abs(rows[:, 0] - jd).max() > 1e-6:
            sys.exit(f"{name}: dates differ")
        names.append(name)
        planets.append(planet)
        mags.append(mag)
        data.append(rows[:, 1:7].astype(np.float32))
        print(f"{name}: {len(rows)} days, |r| {np.linalg.norm(rows[:, 1:4], axis=1).mean():.0f} km")
    np.savez_compressed(OUT, names=np.array(names), planets=np.array(planets), mags=np.array(mags),
                        jd0=np.float64(jd[0]), states=np.stack(data))
    print("written", OUT, os.path.getsize(OUT) // 1024, "KB")


if __name__ == "__main__":
    main()
