"""
engine.py — Astronomical Calculation Engine for Céleste
=========================================================
Implements the algorithms of Jean Meeus (Astronomical Algorithms, 2nd ed.)
for calculating Sun, Moon and planetary positions, as well as detecting
daily events (sunrise, sunset, twilights).

v3.1 additions:
  • sun_position_hp(t)       — VSOP87 truncated (~1" arc)
  • moon_position_elp2000(t) — ELP2000-82B truncated (~10" arc)
  • find_eclipses()          — total/annular/hybrid type, diameter ratio,
                                magnitude, central phase duration

This module is completely independent from the graphical interface (MVC model).
"""

import math
from datetime import timedelta

# ==========================================================
# CONSTANTS
# ==========================================================

# Atmospheric refraction correction (Meeus, chap. 16)
_HORIZON_CORRECTION_SUN = 0.833  # degrees

# Refraction coefficients for Bennett's formula (Meeus, chap. 16)
_REFRACTION_A = 10.3
_REFRACTION_B = 5.11

# Mean orbital elements at J2000.0 (Meeus, App. II)
# Format: [L0 (°), L1 (°/century), a (AU), e0, e1, i (°), Ω (°), ω̃ (°)]
_ORBITAL_ELEMENTS = {
    "Venus":   [181.979801,  58517.8156760, 0.72333199,  0.00677323, -0.00004938,  3.39471,  76.68069, 131.53298],
    "Mars":    [355.433275,  19140.2993313, 1.52366231,  0.09341233,  0.00011902,  1.85061,  49.57854, 336.04084],
    "Jupiter": [ 34.351519,   3034.9056606, 5.20336301,  0.04839266, -0.00012880,  1.30530, 100.55615,  14.75385],
    "Saturn":  [ 50.077444,   1222.1137943, 9.53707032,  0.05415060, -0.00036762,  2.48446, 113.71504,  92.43194],
}

# ==========================================================
# MOON PERIODIC TABLES — Meeus chapter 47 (base series)
# ==========================================================

_MOON_LONGITUDE_TERMS = (
    ( 0,  0,  1,  0,  6288774),
    ( 2,  0, -1,  0, -1274027),
    ( 2,  0,  0,  0,   658314),
    ( 0,  0,  2,  0,   213618),
    ( 0,  1,  0,  0,  -185116),
    ( 0,  0,  0,  2,  -114332),
    ( 2,  0, -2,  0,    58793),
    ( 2, -1, -1,  0,    57066),
    ( 2,  0,  1,  0,    53322),
    ( 2, -1,  0,  0,    45758),
    ( 0,  1, -1,  0,   -40923),
    ( 1,  0,  0,  0,   -34720),
    ( 0,  1,  1,  0,   -30383),
    ( 2,  0,  0, -2,    15327),
    ( 0,  0,  1,  2,   -12528),
    ( 0,  0,  1, -2,    10980),
    ( 4,  0, -1,  0,    10675),
    ( 0,  0,  3,  0,    10034),
    ( 4,  0, -2,  0,     8548),
    ( 2,  1, -1,  0,    -7888),
    ( 2,  1,  0,  0,    -6766),
    ( 1,  0, -1,  0,    -5163),
    ( 1,  1,  0,  0,     4987),
    ( 2, -1,  1,  0,     4036),
    ( 2,  0,  2,  0,     3994),
    ( 4,  0,  0,  0,     3861),
    ( 2,  0, -3,  0,     3665),
    ( 0,  1, -2,  0,    -2689),
    ( 2,  0, -1,  2,    -2602),
    ( 2, -1, -2,  0,     2390),
    ( 1,  0,  1,  0,    -2348),
    ( 2, -2,  0,  0,     2236),
    ( 0,  1,  2,  0,    -2120),
    ( 0,  2,  0,  0,    -2069),
    ( 2, -2, -1,  0,     2048),
    ( 2,  0,  1, -2,    -1773),
    ( 2,  0,  0,  2,    -1595),
    ( 4, -1, -1,  0,     1215),
    ( 0,  0,  2,  2,    -1110),
    ( 3,  0, -1,  0,     -892),
    ( 2,  1,  1,  0,     -810),
    ( 4, -1, -2,  0,      759),
    ( 0,  2, -1,  0,     -713),
    ( 2,  2, -1,  0,     -700),
    ( 2,  1, -2,  0,      691),
    ( 2, -1,  0, -2,      596),
    ( 4,  0,  1,  0,      549),
    ( 0,  0,  4,  0,      537),
    ( 4, -1,  0,  0,      520),
    ( 1,  0, -2,  0,     -487),
    ( 2,  1,  0, -2,     -399),
    ( 0,  0,  2, -2,     -381),
    ( 1,  1,  1,  0,      351),
    ( 3,  0, -2,  0,     -340),
    ( 4,  0, -3,  0,      330),
    ( 2, -1,  2,  0,      327),
    ( 0,  2,  1,  0,     -323),
    ( 1,  1, -1,  0,      299),
    ( 2,  0,  3,  0,      294),
    ( 2,  0, -1, -2,        0),
)

_MOON_DISTANCE_TERMS = (
    ( 0,  0,  1,  0, -20905355),
    ( 2,  0, -1,  0,  -3699111),
    ( 2,  0,  0,  0,  -2955968),
    ( 0,  0,  2,  0,   -569925),
    ( 0,  1,  0,  0,     48888),
    ( 0,  0,  0,  2,     -3149),
    ( 2,  0, -2,  0,    246158),
    ( 2, -1, -1,  0,   -152138),
    ( 2,  0,  1,  0,   -170733),
    ( 2, -1,  0,  0,   -204586),
    ( 0,  1, -1,  0,   -129620),
    ( 1,  0,  0,  0,    108743),
    ( 0,  1,  1,  0,    104755),
    ( 2,  0,  0, -2,     10321),
    ( 0,  0,  1,  2,         0),
    ( 0,  0,  1, -2,     79661),
    ( 4,  0, -1,  0,    -34782),
    ( 0,  0,  3,  0,    -23210),
    ( 4,  0, -2,  0,    -21636),
    ( 2,  1, -1,  0,     24208),
    ( 2,  1,  0,  0,     30824),
    ( 1,  0, -1,  0,     -8379),
    ( 1,  1,  0,  0,    -16675),
    ( 2, -1,  1,  0,    -12831),
    ( 2,  0,  2,  0,    -10445),
    ( 4,  0,  0,  0,    -11650),
    ( 2,  0, -3,  0,     14403),
    ( 0,  1, -2,  0,     -7003),
    ( 2,  0, -1,  2,         0),
    ( 2, -1, -2,  0,     10056),
    ( 1,  0,  1,  0,      6322),
    ( 2, -2,  0,  0,     -9884),
    ( 0,  1,  2,  0,      5751),
    ( 0,  2,  0,  0,         0),
    ( 2, -2, -1,  0,     -4950),
    ( 2,  0,  1, -2,         0),
    ( 2,  0,  0,  2,      4130),
    ( 4, -1, -1,  0,         0),
    ( 0,  0,  2,  2,     -3958),
    ( 3,  0, -1,  0,         0),
    ( 2,  1,  1,  0,      3258),
    ( 4, -1, -2,  0,      2616),
    ( 0,  2, -1,  0,     -1897),
    ( 2,  2, -1,  0,     -2117),
    ( 2,  1, -2,  0,      2354),
    ( 2, -1,  0, -2,         0),
    ( 4,  0,  1,  0,         0),
    ( 0,  0,  4,  0,     -1423),
    ( 4, -1,  0,  0,     -1117),
    ( 1,  0, -2,  0,     -1571),
    ( 2,  1,  0, -2,     -1739),
    ( 0,  0,  2, -2,         0),
    ( 1,  1,  1,  0,         0),
    ( 3,  0, -2,  0,     -4421),
    ( 4,  0, -3,  0,         0),
    ( 2, -1,  2,  0,         0),
    ( 0,  2,  1,  0,      1165),
    ( 1,  1, -1,  0,         0),
    ( 2,  0,  3,  0,         0),
    ( 2,  0, -1, -2,      8752),
)

_MOON_LATITUDE_TERMS = (
    ( 0,  0,  0,  1,  5128122),
    ( 0,  0,  1,  1,   280602),
    ( 0,  0,  1, -1,   277693),
    ( 2,  0,  0, -1,   173237),
    ( 2,  0, -1,  1,    55413),
    ( 2,  0, -1, -1,    46271),
    ( 2,  0,  0,  1,    32573),
    ( 0,  0,  2,  1,    17198),
    ( 2,  0,  1, -1,     9266),
    ( 0,  0,  2, -1,     8822),
    ( 2, -1,  0, -1,     8216),
    ( 2,  0, -2, -1,     4324),
    ( 2,  0,  1,  1,     4200),
    ( 2,  1,  0, -1,    -3359),
    ( 2, -1, -1,  1,     2463),
    ( 2, -1,  0,  1,     2211),
    ( 2, -1, -1, -1,     2065),
    ( 0,  1, -1, -1,    -1870),
    ( 4,  0, -1, -1,     1828),
    ( 0,  1,  0,  1,    -1794),
    ( 0,  0,  0,  3,    -1749),
    ( 0,  1, -1,  1,    -1565),
    ( 1,  0,  0,  1,    -1491),
    ( 0,  1,  1,  1,    -1475),
    ( 0,  1,  1, -1,    -1410),
    ( 0,  1,  0, -1,    -1344),
    ( 1,  0,  0, -1,    -1335),
    ( 0,  0,  3,  1,     1107),
    ( 4,  0,  0, -1,     1021),
    ( 4,  0, -1,  1,      833),
    ( 0,  0,  1, -3,      777),
    ( 4,  0, -2,  1,      671),
    ( 2,  0,  0, -3,      607),
    ( 2,  0,  2, -1,      596),
    ( 2, -1,  1, -1,      491),
    ( 2,  0, -2,  1,     -451),
    ( 0,  0,  3, -1,      439),
    ( 2,  0,  2,  1,      422),
    ( 2,  0, -3, -1,      421),
    ( 2,  1, -1,  1,     -366),
    ( 2,  1,  0,  1,     -351),
    ( 4,  0,  0,  1,      331),
    ( 2, -1,  1,  1,      315),
    ( 2, -2,  0, -1,      302),
    ( 0,  0,  1,  3,     -283),
    ( 2,  1,  1, -1,     -229),
    ( 1,  1,  0, -1,      223),
    ( 1,  1,  0,  1,      223),
    ( 0,  1, -2, -1,     -220),
    ( 2,  1, -1, -1,     -220),
    ( 1,  0,  1,  1,     -185),
    ( 2, -1, -2, -1,      181),
    ( 0,  1,  2,  1,     -177),
    ( 4,  0, -2, -1,      176),
    ( 4, -1, -1, -1,      166),
    ( 1,  0,  1, -1,     -164),
    ( 4,  0,  1, -1,      132),
    ( 1,  0, -1, -1,     -119),
    ( 4, -1,  0, -1,      115),
    ( 2, -2,  0,  1,      107),
)

# ==========================================================
# VSOP87 — Sun high precision (Meeus, chap. 32)
# Terms (A, B, C): contribution = A × cos(B + C×τ), τ = t/10 (millennia)
# Precision after truncation: ~1" arc over ±2000 years
# ==========================================================

_VSOP87_L0 = (
    (175347046.0, 0.0,         0.0         ),
    (  3341656.0, 4.6692568,   6283.0758500),
    (    34894.0, 4.62610,    12566.15170  ),
    (     3497.0, 2.7441,      5753.3849   ),
    (     3418.0, 2.8289,         3.5231   ),
    (     3136.0, 3.6277,     77713.7715   ),
    (     2676.0, 4.4181,      7860.4194   ),
    (     2343.0, 6.1352,      3930.2097   ),
    (     1324.0, 0.7425,     11506.7698   ),
    (     1273.0, 2.0371,       529.6910   ),
    (     1199.0, 1.1096,      1577.3435   ),
    (      990.0, 5.233,       5884.927    ),
    (      902.0, 2.045,         26.298    ),
    (      857.0, 3.508,        398.149    ),
    (      780.0, 1.179,       5223.694    ),
    (      753.0, 2.533,       5507.553    ),
    (      505.0, 4.583,      18849.228    ),
    (      492.0, 4.205,        775.523    ),
    (      357.0, 2.920,          0.067    ),
    (      317.0, 5.849,      11790.629    ),
    (      284.0, 1.899,        796.298    ),
    (      271.0, 0.315,      10977.079    ),
    (      243.0, 0.345,       5486.778    ),
    (      206.0, 4.806,       2544.314    ),
    (      205.0, 1.869,       5573.143    ),
    (      202.0, 2.458,       6069.777    ),
    (      156.0, 0.833,        213.299    ),
    (      132.0, 3.411,       2942.463    ),
    (      126.0, 1.083,         20.775    ),
    (      115.0, 0.645,          0.980    ),
    (      103.0, 0.636,       4694.003    ),
    (       99.0, 6.210,      15720.839    ),
    (       98.0, 0.68,        7084.897    ),
    (       86.0, 5.98,       11243.685    ),
    (       86.0, 1.27,      161000.685    ),
    (       65.0, 1.43,       17260.155    ),
    (       63.0, 1.05,        5088.629    ),
    (       57.0, 5.30,       14712.317    ),
    (       56.0, 5.97,       12036.461    ),
    (       49.0, 5.86,        1349.867    ),
    (       45.0, 1.72,         -220.413   ),
    (       43.0, 0.50,        1059.382    ),
    (       39.0, 3.36,       10447.388    ),
    (       38.0, 1.78,        2352.866    ),
    (       37.0, 1.52,        9437.763    ),
    (       37.0, 4.37,        5765.847    ),
    (       36.0, 6.04,        3154.690    ),
    (       32.0, 1.78,        4690.480    ),
    (       29.0, 3.45,         522.577    ),
    (       28.0, 1.90,        6286.599    ),
    (       27.0, 0.27,        6279.553    ),
    (       27.0, 0.09,       12139.554    ),
)
_VSOP87_L1 = (
    (628331966747.0, 0.0,        0.0        ),
    (    206059.0,   2.678235,   6283.075850),
    (      4303.0,   2.6351,    12566.1517  ),
    (       425.0,   1.590,         3.523   ),
    (       119.0,   5.796,        26.298   ),
    (       109.0,   2.966,      1577.344   ),
    (        93.0,   2.59,      18849.23    ),
    (        72.0,   1.14,        529.69    ),
    (        68.0,   1.87,        398.15    ),
    (        67.0,   4.41,       5507.55    ),
    (        59.0,   2.89,       5223.69    ),
    (        56.0,   2.17,        155.42    ),
    (        45.0,   0.40,        796.30    ),
    (        36.0,   0.47,        775.52    ),
    (        29.0,   2.65,          7.11    ),
    (        21.0,   5.34,          0.98    ),
    (        19.0,   1.85,       5486.78    ),
    (        19.0,   4.97,        213.30    ),
    (        17.0,   2.99,       6275.96    ),
    (        16.0,   0.03,       2544.31    ),
    (        16.0,   1.43,       2146.17    ),
    (        15.0,   1.21,      10977.08    ),
    (        12.0,   2.83,       1748.02    ),
    (        12.0,   3.26,       5088.63    ),
    (        12.0,   5.27,       1194.45    ),
    (        12.0,   2.08,       4694.00    ),
    (        11.0,   0.77,        553.57    ),
    (        10.0,   1.30,       6286.60    ),
    (        10.0,   4.24,       1349.87    ),
    (         9.0,   2.70,        242.73    ),
    (         9.0,   5.64,        951.72    ),
    (         8.0,   5.30,       2352.87    ),
    (         6.0,   2.65,       9437.76    ),
    (         6.0,   4.67,       4690.48    ),
)
_VSOP87_L2 = (
    ( 52919.0, 0.0,       0.0      ),
    (  8720.0, 1.0721,    6283.0758),
    (   309.0, 0.867,    12566.152 ),
    (    27.0, 0.05,         3.52  ),
    (    16.0, 5.19,        26.30  ),
    (    16.0, 3.68,       155.42  ),
    (    10.0, 0.76,     18849.23  ),
    (     9.0, 2.06,     77713.77  ),
    (     7.0, 0.83,       775.52  ),
    (     5.0, 4.66,      1577.34  ),
    (     4.0, 1.03,         7.11  ),
    (     4.0, 3.44,      5573.14  ),
    (     3.0, 5.14,       796.30  ),
    (     3.0, 6.05,      5507.55  ),
    (     3.0, 1.19,       242.73  ),
    (     3.0, 6.12,       529.69  ),
    (     3.0, 0.31,       398.15  ),
    (     3.0, 2.28,       553.57  ),
    (     2.0, 4.38,      5223.69  ),
    (     2.0, 3.75,         0.98  ),
)
_VSOP87_L3 = (
    (289.0, 5.844, 6283.076),
    ( 35.0, 0.0,      0.0  ),
    ( 17.0, 5.49,  12566.15),
    (  3.0, 5.20,    155.42),
    (  1.0, 4.72,      3.52),
    (  1.0, 5.30,  18849.23),
    (  1.0, 5.97,    242.73),
)
_VSOP87_L4 = (
    (114.0, 3.1417, 6283.0758),
    (  8.0, 4.13,      0.0   ),
    (  1.0, 3.84,  12566.15  ),
)
_VSOP87_L5 = ((1.0, 3.14, 0.0),)

_VSOP87_B0 = (
    (280.0, 3.199, 84334.662),
    (102.0, 5.422,  5507.553),
    ( 80.0, 3.88,   5223.69 ),
    ( 44.0, 3.70,   2352.87 ),
    ( 32.0, 4.00,   1577.34 ),
)
_VSOP87_B1 = (
    (9.0, 3.90, 5507.55),
    (6.0, 1.73, 5223.69),
)

_VSOP87_R0 = (
    (100013989.0, 0.0,        0.0        ),
    (  1670700.0, 3.0984635,  6283.07585 ),
    (    13956.0, 3.05525,   12566.1517  ),
    (     3084.0, 5.1985,    77713.7715  ),
    (     1628.0, 1.1739,     5753.3849  ),
    (     1576.0, 2.8469,     7860.4194  ),
    (      925.0, 5.453,     11506.770   ),
    (      542.0, 4.564,      3930.210   ),
    (      472.0, 3.661,      5884.927   ),
    (      346.0, 0.964,      5507.553   ),
    (      329.0, 5.900,      5223.694   ),
    (      307.0, 0.299,      5573.143   ),
    (      243.0, 4.273,     11790.629   ),
    (      212.0, 5.847,      1577.344   ),
    (      186.0, 5.022,     10977.079   ),
    (      175.0, 3.012,     18849.228   ),
    (      110.0, 5.055,      5486.778   ),
    (       98.0, 0.89,       6069.78    ),
    (       86.0, 5.69,      15720.84    ),
    (       72.0, 1.14,     161000.69    ),
    (       68.0, 1.87,      17260.15    ),
    (       52.0, 0.27,      12036.46    ),
    (       38.0, 3.44,       5088.63    ),
    (       37.0, 4.37,      10447.39    ),
    (       32.0, 1.78,       9437.76    ),
    (       29.0, 3.45,        522.58    ),
    (       28.0, 1.90,       6286.60    ),
    (       27.0, 4.31,       6279.55    ),
    (       27.0, 0.27,      12139.55    ),
)
_VSOP87_R1 = (
    (103019.0, 1.107490, 6283.075850),
    (  1721.0, 1.0644,  12566.1517  ),
    (   702.0, 3.142,       0.0     ),
    (    32.0, 1.02,    18849.23    ),
    (    31.0, 2.84,     5507.55    ),
    (    25.0, 1.32,     5223.69    ),
    (    18.0, 1.42,     1577.34    ),
    (    10.0, 5.91,    10977.08    ),
    (     9.0, 1.42,     6275.96    ),
    (     9.0, 0.27,     5486.78    ),
)
_VSOP87_R2 = (
    (4359.0, 5.7846, 6283.0758),
    ( 124.0, 5.579, 12566.152 ),
    (  12.0, 3.14,      0.0   ),
    (   9.0, 3.63,  77713.77  ),
    (   6.0, 1.87,   5573.14  ),
    (   3.0, 5.47,  18849.23  ),
)
_VSOP87_R3 = (
    (145.0, 4.273, 6283.076),
    (  7.0, 3.92, 12566.15 ),
)
_VSOP87_R4 = ((4.0, 2.56, 6283.08),)

# ==========================================================
# ELP2000-82B — Moon additional terms
# ==========================================================

_ELP2000_LON_ADD = (
    ( 2, -2,  1,  0,   2390), ( 2,  0, -1, -2,  -2602),
    ( 2, -1, -2,  0,   2236), ( 4, -1, -1,  0,   1215),
    ( 0,  0,  2,  2,  -1110), ( 3,  0, -1,  0,   -892),
    ( 2,  1,  1,  0,   -810), ( 4, -1, -2,  0,    759),
    ( 0,  2, -1,  0,   -713), ( 2,  2, -1,  0,   -700),
    ( 2,  1, -2,  0,    691), ( 2, -1,  0, -2,    596),
    ( 4,  0,  1,  0,    549), ( 0,  0,  4,  0,    537),
    ( 4, -1,  0,  0,    520), ( 1,  0, -2,  0,   -487),
    ( 2,  1,  0, -2,   -399), ( 0,  0,  2, -2,   -381),
    ( 1,  1,  1,  0,    351), ( 3,  0, -2,  0,   -340),
    ( 4,  0, -3,  0,    330), ( 2, -1,  2,  0,    327),
    ( 0,  2,  1,  0,   -323), ( 1,  1, -1,  0,    299),
    ( 2,  0,  3,  0,    294),
)
_ELP2000_LAT_ADD = (
    ( 0,  1, -2, -1,   -1870), ( 4,  0, -1, -1,   1828),
    ( 0,  1,  0,  1,   -1794), ( 0,  0,  0,  3,  -1749),
    ( 0,  1, -1,  1,   -1565), ( 1,  0,  0,  1,  -1491),
    ( 0,  1,  1,  1,   -1475), ( 0,  1,  1, -1,  -1410),
    ( 0,  1,  0, -1,   -1344), ( 1,  0,  0, -1,  -1335),
    ( 0,  0,  3,  1,    1107), ( 4,  0,  0, -1,   1021),
    ( 4,  0, -1,  1,     833), ( 0,  0,  1, -3,    777),
    ( 4,  0, -2,  1,     671), ( 2,  0,  0, -3,    607),
    ( 2,  0,  2, -1,     596), ( 2, -1,  1, -1,    491),
    ( 2,  0, -2,  1,    -451), ( 0,  0,  3, -1,    439),
    ( 2,  0,  2,  1,     422), ( 2,  0, -3, -1,    421),
    ( 2,  1, -1,  1,    -366), ( 2,  1,  0,  1,   -351),
    ( 4,  0,  0,  1,     331), ( 2, -1,  1,  1,    315),
    ( 2, -2,  0, -1,     302), ( 0,  0,  1,  3,   -283),
    ( 2,  1,  1, -1,    -229), ( 1,  1,  0, -1,    223),
    ( 1,  1,  0,  1,     223), ( 0,  1, -2, -1,   -220),
    ( 2,  1, -1, -1,    -220), ( 1,  0,  1,  1,   -185),
    ( 2, -1, -2, -1,     181), ( 0,  1,  2,  1,   -177),
    ( 4,  0, -2, -1,     176), ( 4, -1, -1, -1,    166),
    ( 1,  0,  1, -1,    -164), ( 4,  0,  1, -1,    132),
    ( 1,  0, -1, -1,    -119), ( 4, -1,  0, -1,    115),
    ( 2, -2,  0,  1,     107),
)
_ELP2000_DIST_ADD = (
    ( 2, -1, -2,  0,   10056), ( 1,  0,  1,  0,    6322),
    ( 2, -2,  0,  0,   -9884), ( 0,  1,  2,  0,    5751),
    ( 2, -2, -1,  0,   -4950), ( 2,  0,  0,  2,    4130),
    ( 0,  0,  2,  2,   -3958), ( 2,  1,  1,  0,    3258),
    ( 4, -1, -2,  0,    2616), ( 0,  2, -1,  0,   -1897),
    ( 2,  2, -1,  0,   -2117), ( 2,  1, -2,  0,    2354),
    ( 0,  0,  4,  0,   -1423), ( 4, -1,  0,  0,   -1117),
    ( 1,  0, -2,  0,   -1571), ( 2,  1,  0, -2,   -1739),
    ( 3,  0, -2,  0,   -4421), ( 0,  2,  1,  0,    1165),
    ( 2,  0, -1, -2,    8752),
)


# ==========================================================
# MAIN ENGINE
# ==========================================================

class MeeusEngine:
    """
    Encapsulates all pure astronomical calculations, independent of the interface.

    All methods are class methods or static methods: no internal state is preserved.

    Reference: Jean Meeus, *Astronomical Algorithms*, 2nd ed., Willmann-Bell, 1998.
    """

    @staticmethod
    def mod360(a):
        """Returns angle normalised to [0, 360[."""
        return a % 360

    @classmethod
    def julian_day(cls, dte):
        """Calculates Julian Day (JD) for a given datetime (Meeus, chap. 7)."""
        y, m, d = dte.year, dte.month, dte.day
        h, mn, s = dte.hour, dte.minute, dte.second
        if m <= 2:
            y -= 1; m += 12
        a = math.floor(y / 100)
        b = 2 - a + math.floor(a / 4)
        frac = d + h/24.0 + mn/1440.0 + s/86400.0
        return math.floor(365.25*(y+4716)) + math.floor(30.6001*(m+1)) + frac + b - 1524.5

    @classmethod
    def julian_century_j2000(cls, dte):
        """Calculates T in Julian centuries since J2000.0."""
        return (cls.julian_day(dte) - 2451545.0) / 36525.0

    # ──────────────────────────────────────────────────────────────────
    # SUN — short series (Meeus, chap. 25) — kept for compatibility
    # ──────────────────────────────────────────────────────────────────

    @classmethod
    def sun_position(cls, t):
        """
        Sun ecliptic longitude and distance — short series (~0.01°).
        Kept for trajectory and event calculations.

        Reference: Meeus, chap. 25.
        """
        l0 = cls.mod360(280.46646 + 36000.76983 * t)
        m  = cls.mod360(357.52911 + 35999.05029 * t)
        e  = 0.016708634 - 0.000042037 * t
        c  = ((1.914602 - 0.004817*t)*math.sin(math.radians(m))
              + (0.019993 - 0.000101*t)*math.sin(math.radians(2*m)))
        l  = cls.mod360(l0 + c)
        r  = 1.00014*(1 - e**2)/(1 + e*math.cos(math.radians(m + c)))
        return l, r

    @classmethod
    def equation_of_time(cls, t):
        """Equation of Time in minutes (Meeus, chap. 28)."""
        l0     = cls.mod360(280.46646 + 36000.76983 * t)
        s_l, _ = cls.sun_position(t)
        ra, _  = cls.ecliptic_to_equatorial(s_l, 0, t)
        eot_deg = l0 - 0.0057183 - ra * 15.0
        eot_deg = ((eot_deg + 180) % 360) - 180
        return eot_deg * 4.0

    # ──────────────────────────────────────────────────────────────────
    # SUN — VSOP87 high precision (Meeus, chap. 32)
    # ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _vsop87_series(table, tau):
        """Evaluates a VSOP87 series: Σ A·cos(B + C·τ)."""
        return sum(A * math.cos(B + C * tau) for A, B, C in table)

    @classmethod
    def sun_position_hp(cls, t):
        """
        Sun ecliptic longitude and distance — VSOP87 truncated (~1" arc).

        Args:
            t (float): Julian centuries since J2000.0.

        Returns:
            tuple[float, float]: (longitude degrees [0,360[, distance AU)

        Reference: Meeus, chap. 32.
        """
        tau = t / 10.0
        v   = cls._vsop87_series

        L = (v(_VSOP87_L0, tau) + v(_VSOP87_L1, tau)*tau + v(_VSOP87_L2, tau)*tau**2
             + v(_VSOP87_L3, tau)*tau**3 + v(_VSOP87_L4, tau)*tau**4
             + v(_VSOP87_L5, tau)*tau**5) / 1e8
        L = math.degrees(L)

        r = (v(_VSOP87_R0, tau) + v(_VSOP87_R1, tau)*tau + v(_VSOP87_R2, tau)*tau**2
             + v(_VSOP87_R3, tau)*tau**3 + v(_VSOP87_R4, tau)*tau**4) / 1e8

        theta      = L + 180.0
        theta     -= 0.005693 / r                           # aberration
        omega      = 125.04 - 1934.136 * t
        delta_psi  = -0.00478 * math.sin(math.radians(omega))  # nutation
        theta     += delta_psi

        return cls.mod360(theta), r

    # ──────────────────────────────────────────────────────────────────
    # MOON — base series (Meeus, chap. 47)
    # ──────────────────────────────────────────────────────────────────

    @classmethod
    def _moon_base_series(cls, t):
        """
        Compute fundamental lunar arguments and base Meeus ch.47 series sums.
        Shared by moon_position() and moon_position_elp2000().

        Returns:
            tuple: (lp, f, mp, a1, a2, a3, d_r, m_r, mp_r, f_r, e, sl, sr, sb)
                lp, f, mp, a1, a2, a3 : fundamental arguments in degrees
                d_r, m_r, mp_r, f_r   : d, m, mp, f converted to radians
                e                     : eccentricity correction factor
                sl, sr, sb            : partial sums (before additive corrections)
        """
        t2, t3 = t*t, t*t*t

        lp = cls.mod360(218.3164477 + 481267.88123421*t - 0.0015786*t2 + t3/538841.0    - t2**2/65194000.0)
        d  = cls.mod360(297.8501921 + 445267.1114034 *t - 0.0018819*t2 + t3/545868.0    - t2**2/113065000.0)
        m  = cls.mod360(357.5291092 + 35999.0502909  *t - 0.0001536*t2 + t3/24490000.0)
        mp = cls.mod360(134.9633964 + 477198.8675055 *t + 0.0087414*t2 + t3/69699.0     - t2**2/14712000.0)
        f  = cls.mod360(93.2720950  + 483202.0175233 *t - 0.0036539*t2 - t3/3526000.0   + t2**2/863310000.0)

        a1 = cls.mod360(119.75 + 131.849*t)
        a2 = cls.mod360(53.09  + 479264.290*t)
        a3 = cls.mod360(313.45 + 481266.484*t)
        e  = 1.0 - 0.002516*t - 0.0000074*t2

        dr = math.radians
        d_r, m_r, mp_r, f_r = dr(d), dr(m), dr(mp), dr(f)
        sl = sr = sb = 0.0

        for cD, cM, cMp, cF, amp in _MOON_LONGITUDE_TERMS:
            if amp == 0: continue
            ec = e**abs(cM) if cM else 1.0
            sl += amp * ec * math.sin(cD*d_r + cM*m_r + cMp*mp_r + cF*f_r)

        for cD, cM, cMp, cF, amp in _MOON_DISTANCE_TERMS:
            if amp == 0: continue
            ec = e**abs(cM) if cM else 1.0
            sr += amp * ec * math.cos(cD*d_r + cM*m_r + cMp*mp_r + cF*f_r)

        for cD, cM, cMp, cF, amp in _MOON_LATITUDE_TERMS:
            if amp == 0: continue
            ec = e**abs(cM) if cM else 1.0
            sb += amp * ec * math.sin(cD*d_r + cM*m_r + cMp*mp_r + cF*f_r)

        return lp, f, mp, a1, a2, a3, d_r, m_r, mp_r, f_r, e, sl, sr, sb

    @classmethod
    def moon_position(cls, t):
        """
        Moon position — base series chap. 47 (~0.01°).
        Kept for trajectory and event calculations.

        Returns:
            tuple[float, float, float]: (longitude°, latitude°, parallax°)
        """
        lp, f, mp, a1, a2, a3, d_r, m_r, mp_r, f_r, e, sl, sr, sb = cls._moon_base_series(t)
        dr = math.radians

        sl += 3958*math.sin(dr(a1)) + 1962*math.sin(dr(lp-f)) + 318*math.sin(dr(a2))
        sb += (-2235*math.sin(dr(lp)) + 382*math.sin(dr(a3))
               + 175*math.sin(dr(a1-f)) + 175*math.sin(dr(a1+f))
               + 127*math.sin(dr(lp-mp)) - 115*math.sin(dr(lp+mp)))

        lon      = cls.mod360(lp + sl/1_000_000.0)
        lat      = sb / 1_000_000.0
        dist_km  = 385000.56 + sr/1000.0
        parallax = math.degrees(math.asin(6378.14/dist_km))
        return lon, lat, parallax

    # ──────────────────────────────────────────────────────────────────
    # MOON — ELP2000-82B high precision (~10" arc)
    # ──────────────────────────────────────────────────────────────────

    @classmethod
    def moon_position_elp2000(cls, t):
        """
        Moon position — ELP2000-82B truncated (~10" arc).

        Returns:
            tuple[float, float, float, float]:
                (longitude°, latitude°, distance_km, parallax°)

        Reference: Meeus, chap. 47 + ELP2000-82B.
        """
        lp, f, mp, a1, a2, a3, d_r, m_r, mp_r, f_r, e, sl, sr, sb = cls._moon_base_series(t)
        dr = math.radians

        # ELP2000 additional terms
        for cD, cM, cMp, cF, amp in _ELP2000_LON_ADD:
            ec = e**abs(cM) if cM else 1.0
            sl += amp * ec * math.sin(cD*d_r + cM*m_r + cMp*mp_r + cF*f_r)
        for cD, cM, cMp, cF, amp in _ELP2000_LAT_ADD:
            ec = e**abs(cM) if cM else 1.0
            sb += amp * ec * math.sin(cD*d_r + cM*m_r + cMp*mp_r + cF*f_r)
        for cD, cM, cMp, cF, amp in _ELP2000_DIST_ADD:
            if amp == 0: continue
            ec = e**abs(cM) if cM else 1.0
            sr += amp * ec * math.cos(cD*d_r + cM*m_r + cMp*mp_r + cF*f_r)

        sl += 3958*math.sin(dr(a1)) + 1962*math.sin(dr(lp-f)) + 318*math.sin(dr(a2))
        sb += (-2235*math.sin(dr(lp)) + 382*math.sin(dr(a3))
               + 175*math.sin(dr(a1-f)) + 175*math.sin(dr(a1+f))
               + 127*math.sin(dr(lp-mp)) - 115*math.sin(dr(lp+mp)))

        lon      = cls.mod360(lp + sl/1_000_000.0)
        lat      = sb / 1_000_000.0
        dist_km  = 385000.56 + sr/1000.0
        parallax = math.degrees(math.asin(6378.14/dist_km))
        return lon, lat, dist_km, parallax

    # ──────────────────────────────────────────────────────────────────
    # APPARENT DIAMETERS AND ECLIPSE HELPERS
    # ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _sun_semi_diameter(r_au):
        """Sun apparent semi-diameter in degrees given distance in AU."""
        return 0.26667 / r_au

    @staticmethod
    def _moon_semi_diameter(dist_km):
        """Moon apparent semi-diameter in degrees given geocentric distance in km."""
        return math.degrees(math.asin(1737.4 / dist_km))

    @staticmethod
    def _eclipse_magnitude(u, gamma):
        """
        Solar eclipse magnitude (Meeus, chap. 54).

        Args:
            u (float): Central shadow radius (Earth equatorial radii).
            gamma (float): Minimum centre-to-centre distance (same unit).

        Returns:
            float: Magnitude (≥1 = total/annular, <1 = partial).
        """
        return (1.0128 - u - abs(gamma)) / 0.5450 + 0.0400 * math.cos(math.radians(u * 60))

    @staticmethod
    def _totality_duration(u, gamma):
        """
        Estimated duration of the central phase of a solar eclipse (Meeus, chap. 54).

        Returns:
            float | None: Duration in minutes, None if no central phase.
        """
        discriminant = 1.0128 - u - (gamma * gamma)
        if discriminant <= 0:
            return None
        return round(2.0 * 60.0 * math.sqrt(discriminant) / 0.5660, 1)

    # ──────────────────────────────────────────────────────────────────
    # COORDINATE CONVERSIONS
    # ──────────────────────────────────────────────────────────────────

    @classmethod
    def ecliptic_to_equatorial(cls, l_deg, b_deg, t):
        """Ecliptic → equatorial conversion (Meeus, chap. 13)."""
        eps = math.radians(23.4392911 - (46.815*t)/3600.0)
        l, b = math.radians(l_deg), math.radians(b_deg)
        ra  = math.atan2(math.sin(l)*math.cos(eps) - math.tan(b)*math.sin(eps), math.cos(l))
        dec = math.asin(math.sin(b)*math.cos(eps) + math.cos(b)*math.sin(eps)*math.sin(l))
        return cls.mod360(math.degrees(ra))/15.0, math.degrees(dec)

    @classmethod
    def equatorial_to_horizontal(cls, jd, lat, lon, ra_h, dec_deg):
        """Equatorial → local horizontal conversion (Meeus, chap. 13)."""
        theta0 = 280.46061837 + 360.98564736629*(jd - 2451545.0)
        lst    = cls.mod360(theta0 + lon)
        tau    = math.radians(lst - ra_h*15.0)
        phi, delta = math.radians(lat), math.radians(dec_deg)
        h  = math.asin(math.sin(phi)*math.sin(delta) + math.cos(phi)*math.cos(delta)*math.cos(tau))
        az = cls.mod360(math.degrees(math.atan2(
            -math.sin(tau),
            math.cos(phi)*math.tan(delta) - math.sin(phi)*math.cos(tau))))
        return math.degrees(h), az

    @staticmethod
    def elevation_correction(h_true, parallax_deg):
        """Atmospheric refraction + parallax correction (Meeus, chap. 16)."""
        if h_true < -5.0:
            return h_true - parallax_deg
        r = (1.02 / math.tan(math.radians(
            h_true + _REFRACTION_A / (h_true + _REFRACTION_B)))) / 60.0
        return h_true + r - parallax_deg

    # ──────────────────────────────────────────────────────────────────
    # DAILY EVENTS
    # ──────────────────────────────────────────────────────────────────

    @classmethod
    def find_events(cls, dte_ref, lat, lon, body="sun"):
        """
        Detects daily events by minute-by-minute scanning.
        Resolution: 1 minute.

        Returns:
            dict with keys: rise, set, transit,
                            dawn_civ, dusk_civ, dawn_naut, dusk_naut,
                            dawn_astro, dusk_astro  (sun only)
        """
        events = {
            'rise': None, 'set': None, 'transit': None,
            'dawn_civ': None,  'dusk_civ': None,
            'dawn_naut': None, 'dusk_naut': None,
            'dawn_astro': None,'dusk_astro': None,
        }
        max_alt  = -90
        prev_alt = None
        start    = dte_ref.replace(hour=0, minute=0, second=0, microsecond=0)

        for mn in range(1440):
            dt  = start + timedelta(minutes=mn)
            jd  = cls.julian_day(dt)
            t   = cls.julian_century_j2000(dt)

            if body == "sun":
                s_l, _ = cls.sun_position(t)
                ra, dec = cls.ecliptic_to_equatorial(s_l, 0, t)
                alt, _  = cls.equatorial_to_horizontal(jd, lat, lon, ra, dec)
                alt_test = alt + _HORIZON_CORRECTION_SUN
            else:
                m_l, m_b, m_p = cls.moon_position(t)
                ra, dec = cls.ecliptic_to_equatorial(m_l, m_b, t)
                alt, _  = cls.equatorial_to_horizontal(jd, lat, lon, ra, dec)
                alt_test = cls.elevation_correction(alt, m_p)

            if alt_test > max_alt:
                max_alt = alt_test; events['transit'] = dt

            if prev_alt is not None:
                if prev_alt < 0 and alt_test >= 0:   events['rise'] = dt
                elif prev_alt > 0 and alt_test <= 0: events['set']  = dt
                if body == "sun":
                    if prev_alt < -6  and alt_test >= -6:  events['dawn_civ']  = dt
                    elif prev_alt > -6  and alt_test <= -6:  events['dusk_civ']  = dt
                    if prev_alt < -12 and alt_test >= -12: events['dawn_naut'] = dt
                    elif prev_alt > -12 and alt_test <= -12: events['dusk_naut'] = dt
                    if prev_alt < -18 and alt_test >= -18: events['dawn_astro'] = dt
                    elif prev_alt > -18 and alt_test <= -18: events['dusk_astro'] = dt
            prev_alt = alt_test

        return events

    # ──────────────────────────────────────────────────────────────────
    # PLANETS
    # ──────────────────────────────────────────────────────────────────

    @classmethod
    def planet_heliocentric(cls, t, name):
        """
        Heliocentric ecliptic position of a planet from its mean orbital
        elements (Meeus, App. II), solving Kepler's equation.

        Args:
            t (float): Julian centuries since J2000.0.
            name (str): "Venus", "Mars", "Jupiter" or "Saturn".

        Returns:
            tuple[float, float, float]: (x, y, z) in AU, ecliptic frame
            (x towards the vernal equinox).
        """
        L0, L1, a, e0, e1, i_deg, omega_deg, peri_deg = _ORBITAL_ELEMENTS[name]
        L     = cls.mod360(L0 + L1*t)
        e     = e0 + e1*t
        i     = math.radians(i_deg)
        omega = math.radians(omega_deg)
        peri  = math.radians(peri_deg)

        M = math.radians(cls.mod360(L - peri_deg))
        E = M
        for _ in range(50):
            dE = (M - E + e*math.sin(E))/(1.0 - e*math.cos(E))
            E += dE
            if abs(dE) < 1e-10: break

        nu  = 2.0*math.atan2(math.sqrt(1+e)*math.sin(E/2), math.sqrt(1-e)*math.cos(E/2))
        r   = a*(1.0 - e*math.cos(E))
        lam = cls.mod360(math.degrees(peri + nu))
        beta = math.degrees(math.asin(math.sin(i)*math.sin(math.radians(lam) - omega)))

        lr, br = math.radians(lam), math.radians(beta)
        xp = r*math.cos(br)*math.cos(lr)
        yp = r*math.cos(br)*math.sin(lr)
        zp = r*math.sin(br)
        return xp, yp, zp

    @classmethod
    def planet_position(cls, t, name):
        """
        Geocentric planet position in equatorial coordinates.
        Precision: ~1-2° (Meeus, chap. 33 / App. II).

        Returns:
            tuple[float, float, float]: (RA hours, Dec degrees, distance AU)
        """
        xp, yp, zp = cls.planet_heliocentric(t, name)

        ls, r_e = cls.sun_position(t)
        ls_r = math.radians(cls.mod360(ls + 180.0))
        xe, ye = r_e*math.cos(ls_r), r_e*math.sin(ls_r)

        dx, dy, dz = xp-xe, yp-ye, zp
        dist = math.sqrt(dx*dx + dy*dy + dz*dz)
        ra, dec = cls.ecliptic_to_equatorial(
            cls.mod360(math.degrees(math.atan2(dy, dx))),
            math.degrees(math.atan2(dz, math.sqrt(dx*dx + dy*dy))), t)
        return ra, dec, dist

    # ──────────────────────────────────────────────────────────────────
    # ANGULAR SEPARATION, CONJUNCTIONS, ECLIPSES
    # ──────────────────────────────────────────────────────────────────

    @staticmethod
    def angular_separation(ra1_h, dec1_deg, ra2_h, dec2_deg):
        """Angular separation between two objects (Meeus, chap. 17)."""
        ra1, ra2 = math.radians(ra1_h*15), math.radians(ra2_h*15)
        d1,  d2  = math.radians(dec1_deg), math.radians(dec2_deg)
        cos_d = math.sin(d1)*math.sin(d2) + math.cos(d1)*math.cos(d2)*math.cos(ra1-ra2)
        return math.degrees(math.acos(max(-1.0, min(1.0, cos_d))))

    @classmethod
    def find_conjunctions(cls, dte_start, num_days=365):
        """
        Searches for planetary conjunctions and oppositions (Meeus, chap. 36).

        Returns:
            list[dict]: sorted by date, keys: date, type, bodies, separation, details
        """
        planets = ["Venus", "Mars", "Jupiter", "Saturn"]
        pairs   = [(a, b) for i, a in enumerate(planets) for b in planets[i+1:]]
        results = []
        prev_seps, prev_elongs = {}, {}

        for day in range(num_days):
            dte = dte_start + timedelta(days=day)
            t   = cls.julian_century_j2000(dte)
            s_l, _ = cls.sun_position(t)
            s_ra, s_dec = cls.ecliptic_to_equatorial(s_l, 0, t)
            positions = {p: cls.planet_position(t, p)[:2] for p in planets}

            for a, b in pairs:
                sep = cls.angular_separation(*positions[a], *positions[b])
                key = (a, b)
                if key in prev_seps and len(prev_seps[key]) >= 2:
                    p2, p1 = prev_seps[key]
                    if p1 < p2 and p1 < sep and p1 < 5.0:
                        results.append({'date': dte-timedelta(days=1), 'type': 'conjunction',
                                        'bodies': (a,b), 'separation': p1,
                                        'details': f"{a} – {b} : {p1:.1f}°"})
                prev_seps[key] = (prev_seps.get(key, (sep,))[-1], sep)

            for pname in planets:
                elong = cls.angular_separation(*positions[pname], s_ra, s_dec)
                key   = pname
                if key in prev_elongs and len(prev_elongs[key]) >= 2:
                    p2, p1 = prev_elongs[key]
                    if p1 < p2 and p1 < elong and p1 < 5.0:
                        results.append({'date': dte-timedelta(days=1), 'type': 'conjunction',
                                        'bodies': (pname,'Sun'), 'separation': p1,
                                        'details': f"{pname} in solar conjunction: {p1:.1f}°"})
                    if (pname in ("Mars","Jupiter","Saturn")
                            and p1 > p2 and p1 > elong and p1 > 175.0):
                        results.append({'date': dte-timedelta(days=1), 'type': 'opposition',
                                        'bodies': (pname,'Sun'), 'separation': p1,
                                        'details': f"{pname} in opposition: {p1:.1f}°"})
                prev_elongs[key] = (prev_elongs.get(key, (elong,))[-1], elong)

        results.sort(key=lambda r: r['date'])
        return results

    @classmethod
    def _find_syzygy(cls, dte_approx, target_phase=0):
        """Refines syzygy date using short series (~1 min precision)."""
        best_dt, best_diff = dte_approx, 999.0
        for h in range(-48, 49):
            dt    = dte_approx + timedelta(hours=h)
            t     = cls.julian_century_j2000(dt)
            s_l,_ = cls.sun_position(t)
            m_l,_,_ = cls.moon_position(t)
            diff  = min(abs(cls.mod360(m_l-s_l)-target_phase),
                        360-abs(cls.mod360(m_l-s_l)-target_phase))
            if diff < best_diff: best_diff, best_dt = diff, dt

        center, best_diff = best_dt, 999.0
        for mn in range(-60, 61):
            dt    = center + timedelta(minutes=mn)
            t     = cls.julian_century_j2000(dt)
            s_l,_ = cls.sun_position(t)
            m_l,_,_ = cls.moon_position(t)
            diff  = min(abs(cls.mod360(m_l-s_l)-target_phase),
                        360-abs(cls.mod360(m_l-s_l)-target_phase))
            if diff < best_diff: best_diff, best_dt = diff, dt
        return best_dt

    @classmethod
    def _find_syzygy_hp(cls, dte_approx, target_phase=0):
        """Refines syzygy date using VSOP87 + ELP2000 (~1 min precision)."""
        best_dt, best_diff = dte_approx, 999.0
        for h in range(-48, 49):
            dt       = dte_approx + timedelta(hours=h)
            t        = cls.julian_century_j2000(dt)
            s_l,_    = cls.sun_position_hp(t)
            m_l,_,_,_ = cls.moon_position_elp2000(t)
            diff     = min(abs(cls.mod360(m_l-s_l)-target_phase),
                           360-abs(cls.mod360(m_l-s_l)-target_phase))
            if diff < best_diff: best_diff, best_dt = diff, dt

        center, best_diff = best_dt, 999.0
        for mn in range(-60, 61):
            dt       = center + timedelta(minutes=mn)
            t        = cls.julian_century_j2000(dt)
            s_l,_    = cls.sun_position_hp(t)
            m_l,_,_,_ = cls.moon_position_elp2000(t)
            diff     = min(abs(cls.mod360(m_l-s_l)-target_phase),
                           360-abs(cls.mod360(m_l-s_l)-target_phase))
            if diff < best_diff: best_diff, best_dt = diff, dt
        return best_dt

    @classmethod
    def find_eclipses(cls, dte_start, num_months=12):
        """
        Searches for solar and lunar eclipses using VSOP87 + ELP2000.

        For solar eclipses, computes:
          • sub_type        : 'total' | 'annular' | 'hybrid' | 'partial'
          • diameter_ratio  : Moon/Sun apparent diameter ratio
          • magnitude       : eclipse magnitude (Meeus, chap. 54)
          • duration_min    : central phase duration in minutes (if applicable)

        Args:
            dte_start (datetime): Start date.
            num_months (int): Synodic months to scan (default 12).

        Returns:
            list[dict]: Sorted by date. Solar eclipse dicts contain:
                date, type='solar', certainty, moon_latitude, details,
                sub_type, diameter_ratio, magnitude, duration_min.
            Lunar eclipse dicts contain:
                date, type='lunar', certainty, moon_latitude, details.

        Reference: Meeus, chap. 54.
        """
        synodic_month = 29.530588
        results       = []

        _EMOJI = {'total': '🌑', 'annular': '⭕', 'hybrid': '🔄', 'partial': '🌘'}

        for i in range(num_months):
            # ── New Moon ───────────────────────────────────────────────
            dte_nm  = dte_start + timedelta(days=i * synodic_month)
            nm      = cls._find_syzygy_hp(dte_nm, target_phase=0)
            t_nm    = cls.julian_century_j2000(nm)

            _, b_nm, dist_moon_nm, _ = cls.moon_position_elp2000(t_nm)
            _, r_sun_nm              = cls.sun_position_hp(t_nm)

            if abs(b_nm) < 1.58:
                certainty = 'certain' if abs(b_nm) < 0.90 else 'possible'

                dd_sun   = cls._sun_semi_diameter(r_sun_nm)
                dd_moon  = cls._moon_semi_diameter(dist_moon_nm)
                ratio    = dd_moon / dd_sun

                gamma = math.sin(math.radians(b_nm)) / math.sin(math.radians(1.57))
                u     = 0.0059 + 0.0046 * (1.0 - ratio)

                if abs(gamma) < 0.9972:
                    if ratio > 1.0:      sub_type = "total"
                    elif ratio < 0.9972: sub_type = "annular"
                    else:                sub_type = "hybrid"
                    duration = cls._totality_duration(u, gamma)
                else:
                    sub_type = "partial"
                    duration = None

                try:    mag = cls._eclipse_magnitude(u, gamma)
                except: mag = None

                parts = [f"Solar eclipse {sub_type} ({certainty})"]
                parts.append(f"Diameter ratio: {ratio:.4f}")
                if mag is not None:
                    parts.append(f"Magnitude: {mag:.3f}")
                if duration is not None:
                    parts.append(f"Central phase: ~{duration} min")
                parts.append(f"Moon lat: {b_nm:+.2f}°")

                results.append({
                    'date':           nm,
                    'type':           'solar',
                    'certainty':      certainty,
                    'moon_latitude':  b_nm,
                    'sub_type':       sub_type,
                    'diameter_ratio': ratio,
                    'magnitude':      mag,
                    'duration_min':   duration,
                    'details':        f"{_EMOJI.get(sub_type,'🌘')}  " + "  |  ".join(parts),
                })

            # ── Full Moon ──────────────────────────────────────────────
            dte_fm  = dte_nm + timedelta(days=synodic_month/2)
            fm      = cls._find_syzygy_hp(dte_fm, target_phase=180)
            t_fm    = cls.julian_century_j2000(fm)

            _, b_fm, _, _ = cls.moon_position_elp2000(t_fm)

            if abs(b_fm) < 1.58:
                if abs(b_fm) < 0.90:   certainty = 'certain'
                elif abs(b_fm) < 1.09: certainty = 'penumbral'
                else:                   certainty = 'possible'
                results.append({
                    'date':          fm,
                    'type':          'lunar',
                    'certainty':     certainty,
                    'moon_latitude': b_fm,
                    'details':       (f"🌕  Lunar eclipse ({certainty}) — "
                                      f"Moon lat: {b_fm:+.2f}°"),
                })

        results.sort(key=lambda r: r['date'])
        return results
