"""
Builds assets/comets.npz: heliocentric positions and velocities of the comets
followed by Céleste, from JPL Horizons, over the years of their apparition.

Unlike a minor planet, a comet's orbit changes with each passage near the Sun
(non-gravitational forces): the table only covers the years around the orbit
solution that JPL fits to the observations of this apparition, every 2 days
(cubic Hermite in engine.py). Re-run the script as the orbits improve: a newly
found comet's solution rests on a few months of observations.

Magnitudes: total magnitude parameters M1, K1 of the JPL Small-Body Database,
m = M1 + 5 log10(Δ) + K1 log10(r), as Horizons computes T-mag.

    python scripts/make_comets.py
"""
import json
import os
import sys
import urllib.parse
import urllib.request

import numpy as np

# This list is the only place where a comet is declared: the table carries the
# names, and engine.py and the interface read them from it.
# name in Céleste (one word, a capital then lower case):
#     (Horizons command, SBDB designation, full designation, short designation)
# The full designation shows in the data window and the events, the short one in
# the tables and "Tonight".
COMETS = {
    "Panstarrs": ("DES=C/2026 O1;", "C/2026 O1", "C/2026 O1 (PANSTARRS)", "C/2026 O1"),
    "Honda": ("DES=45P;CAP;NOFRAG;", "45P", "45P/Honda-Mrkos-Pajdušáková", "45P/Honda"),
    "Tsuchinshan": ("DES=C/2026 C1;", "C/2026 C1", "C/2026 C1 (Tsuchinshan)", "C/2026 C1"),
    "Borrelly": ("DES=19P;CAP;NOFRAG;", "19P", "19P/Borrelly", "19P/Borrelly"),
    "Lemmon": ("DES=C/2025 A6;", "C/2025 A6", "C/2025 A6 (Lemmon)", "C/2025 A6"),
}
START, STOP, STEP = "2025-01-01", "2031-12-31", 2
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "comets.npz")


def _get(url, params):
    with urllib.request.urlopen(url + "?" + urllib.parse.urlencode(params), timeout=300) as r:
        return json.load(r)


def states(command):
    result = _get("https://ssd.jpl.nasa.gov/api/horizons.api", dict(
        format="json", COMMAND=f"'{command}'", CENTER="'500@10'", EPHEM_TYPE="VECTORS",
        START_TIME=f"'{START}'", STOP_TIME=f"'{STOP}'", STEP_SIZE=f"'{STEP}d'",
        REF_PLANE="FRAME", REF_SYSTEM="ICRF", OUT_UNITS="AU-D", VEC_TABLE="2",
        VEC_CORR="NONE", CSV_FORMAT="YES", OBJ_DATA="NO"))["result"]
    rows = result.split("$$SOE")[1].split("$$EOE")[0].strip().splitlines()
    data = np.array([[float(v) for v in (r.split(",")[0],) + tuple(r.split(",")[2:8])] for r in rows])
    jd = data[:, 0]
    assert np.allclose(np.diff(jd), STEP), "irregular sampling"
    return jd[0], data[:, 1:4], data[:, 4:7]


def magnitude_parameters(designation):
    sbdb = _get("https://ssd-api.jpl.nasa.gov/sbdb.api", {"sstr": designation, "phys-par": "1"})
    phys = {p["name"]: p["value"] for p in sbdb["phys_par"] if p.get("value")}
    return float(phys["M1"]), float(phys["K1"])


def names():
    """The names of the comets and their designations, as the table stores them."""
    return {"names": np.array(list(COMETS)),
            "designations": np.array([c[2] for c in COMETS.values()]),
            "short": np.array([c[3] for c in COMETS.values()])}


def main():
    table = names()
    for name, (command, designation, _full, _short) in COMETS.items():
        jd0, r, v = states(command)
        m1, k1 = magnitude_parameters(designation)
        table[f"{name}_start"] = np.array([jd0, STEP])
        table[f"{name}_position"] = r
        table[f"{name}_velocity"] = v
        table[f"{name}_m1k1"] = np.array([m1, k1])
        print(f"{name}: {len(r)} states from JD {jd0}, M1={m1} K1={k1}", file=sys.stderr)
    np.savez_compressed(OUT, **table)
    print(f"{OUT}: {os.path.getsize(OUT) / 1e6:.2f} MB", file=sys.stderr)


if __name__ == "__main__":
    main()
