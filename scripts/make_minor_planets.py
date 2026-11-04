"""
Builds assets/minor_planets.npz: heliocentric positions and velocities of the
minor planets of Céleste, from JPL Horizons, for the years of DE440s.

Horizons integrates each orbit with the perturbations of the planets (JPL
small-body solutions); the table keeps a state (ICRF, AU, AU/day, TDB) every
`step` days, between which engine.py interpolates (cubic Hermite: a few km
for the main belt at 10 days). H and G (magnitudes) come from the JPL
Small-Body Database.

    python scripts/make_minor_planets.py
"""
import json
import os
import sys
import urllib.parse
import urllib.request

import numpy as np

# name: (Horizons / SBDB designation, step in days)
BODIES = {
    "Ceres": ("1", 10), "Pallas": ("2", 10), "Juno": ("3", 10), "Vesta": ("4", 10),
    "Eris": ("136199", 60), "Haumea": ("136108", 60), "Makemake": ("136472", 60), "Sedna": ("90377", 60),
}
START, STOP = "1849-11-01", "2150-03-01"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets",
                   "minor_planets.npz")


def _get(url, params):
    with urllib.request.urlopen(url + "?" + urllib.parse.urlencode(params), timeout=300) as r:
        return json.load(r)


def states(designation, step):
    result = _get("https://ssd.jpl.nasa.gov/api/horizons.api", dict(
        format="json", COMMAND=f"'{designation};'", CENTER="'500@10'", EPHEM_TYPE="VECTORS",
        START_TIME=f"'{START}'", STOP_TIME=f"'{STOP}'", STEP_SIZE=f"'{step}d'",
        REF_PLANE="FRAME", REF_SYSTEM="ICRF", OUT_UNITS="AU-D", VEC_TABLE="2",
        VEC_CORR="NONE", CSV_FORMAT="YES", OBJ_DATA="NO"))["result"]
    rows = result.split("$$SOE")[1].split("$$EOE")[0].strip().splitlines()
    data = np.array([[float(v) for v in (r.split(",")[0],) + tuple(r.split(",")[2:8])] for r in rows])
    jd = data[:, 0]
    assert np.allclose(np.diff(jd), step), "irregular sampling"
    return jd[0], data[:, 1:4], data[:, 4:7]


def magnitude_parameters(designation):
    sbdb = _get("https://ssd-api.jpl.nasa.gov/sbdb.api", {"sstr": designation, "phys-par": "1"})
    phys = {p["name"]: p["value"] for p in sbdb["phys_par"] if p.get("value")}
    return float(phys["H"]), float(phys.get("G", 0.15))


def main():
    table = {}
    for name, (designation, step) in BODIES.items():
        jd0, r, v = states(designation, step)
        h, g = magnitude_parameters(designation)
        table[f"{name}_start"] = np.array([jd0, step])
        table[f"{name}_position"] = r
        table[f"{name}_velocity"] = v
        table[f"{name}_hg"] = np.array([h, g])
        print(f"{name}: {len(r)} states from JD {jd0}, H={h} G={g}", file=sys.stderr)
    np.savez_compressed(OUT, **table)
    print(f"{OUT}: {os.path.getsize(OUT) / 1e6:.2f} MB", file=sys.stderr)


if __name__ == "__main__":
    main()
