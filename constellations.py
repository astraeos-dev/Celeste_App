"""
constellations.py — Star catalog and constellation figures for the sky map
==========================================================================
Bright stars (right ascension, declination, magnitude), the lines drawn
between them, and a reverse lookup from a star to its constellations.
"""

# Bright stars: {name: (RA hours, Dec degrees, visual magnitude)}
BRIGHT_STARS = {
    "Sirius":      ( 6.7523, -16.7161, -1.46),
    "Arcturus":    (14.2612,  19.1822, -0.05),
    "Vega":        (18.6157,  38.7836,  0.03),
    "Capella":     ( 5.2782,  45.9980,  0.08),
    "Rigel":       ( 5.2423,  -8.2016,  0.13),
    "Procyon":     ( 7.6550,   5.2250,  0.34),
    "Betelgeuse":  ( 5.9194,   7.4070,  0.42),
    "Altair":      (19.8463,   8.8683,  0.77),
    "Aldebaran":   ( 4.5988,  16.5093,  0.87),
    "Spica":       (13.4199, -11.1613,  1.04),
    "Antares":     (16.4900, -26.4319,  1.06),
    "Pollux":      ( 7.7553,  28.0262,  1.16),
    "Fomalhaut":   (22.9608, -29.6223,  1.17),
    "Deneb":       (20.6905,  45.2803,  1.25),
    "Regulus":     (10.1395,  11.9672,  1.36),
    "Adhara":      ( 6.9771, -28.9722,  1.50),
    "Castor":      ( 7.5766,  31.8883,  1.58),
    "El Nath":     ( 5.4381,  28.6075,  1.65),
    "Bellatrix":   ( 5.4186,   6.3497,  1.64),
    "Alnilam":     ( 5.6036,  -1.2019,  1.70),
    "Alioth":      (12.9006,  55.9598,  1.76),
    "Alnitak":     ( 5.6791,  -1.9425,  1.77),
    "Mirfak":      ( 3.4054,  49.8614,  1.79),
    "Dubhe":       (11.0623,  61.7508,  1.81),
    "Alkaid":      (13.7924,  49.3133,  1.85),
    "Alhena":      ( 6.6285,  16.3992,  1.93),
    "Alphard":     ( 9.4597,  -8.6584,  1.99),
    "Hamal":       ( 2.1197,  23.4622,  2.01),
    "Denebola":    (11.8174,  14.5723,  2.14),
    "Merak":       (11.0307,  56.3824,  2.37),
    "Phecda":      (11.8966,  53.6948,  2.44),
    "Polaris":     ( 2.5303,  89.2641,  1.97),
}

# Additional stars that complete the constellation figures
STARS_EXTRA = {
    # Orion
    "Mintaka":   ( 5.5335,  -0.2991, 2.23),
    "Saiph":     ( 5.7954,  -9.6697, 2.07),
    # Big Dipper (Ursa Major)
    "Mizar":     (13.3988,  54.9254, 2.23),
    "Megrez":    (12.2571,  57.0326, 3.31),
    # Cassiopeia
    "Schedar":   ( 0.6751,  56.5372, 2.24),
    "Caph":      ( 0.1530,  59.1498, 2.28),
    "Navi":      ( 0.9451,  60.7167, 2.47),
    "Ruchbah":   ( 1.4301,  60.2353, 2.68),
    "Segin":     ( 1.9068,  63.6700, 3.37),
    # Little Dipper (Ursa Minor)
    "Kochab":    (14.8451,  74.1555, 2.07),
    # Scorpius
    "Shaula":    (17.5603, -37.1038, 1.62),
    "Dschubba":  (16.0055, -22.6217, 2.29),
    "Sargas":    (17.6217, -42.9978, 1.87),
}

# Every star drawn on the sky map
STARS = {**BRIGHT_STARS, **STARS_EXTRA}

# Constellations: {name: list of (star_a, star_b)}
# Star names must match keys in STARS. The names are also the translation
# keys of the "constellations" section of the locale files.
CONSTELLATIONS = {
    "Orion": [
        ("Betelgeuse", "Bellatrix"),
        ("Bellatrix", "Mintaka"),
        ("Mintaka", "Alnilam"),
        ("Alnilam", "Alnitak"),
        ("Alnitak", "Saiph"),
        ("Saiph", "Rigel"),
        ("Rigel", "Bellatrix"),
    ],
    "Ursa Major": [
        ("Dubhe", "Merak"),
        ("Merak", "Phecda"),
        ("Phecda", "Megrez"),
        ("Megrez", "Alioth"),
        ("Alioth", "Mizar"),
        ("Mizar", "Alkaid"),
    ],
    "Cassiopeia": [
        ("Caph", "Schedar"),
        ("Schedar", "Navi"),
        ("Navi", "Ruchbah"),
        ("Ruchbah", "Segin"),
    ],
    "Gemini": [
        ("Castor", "Pollux"),
        ("Pollux", "Alhena"),
    ],
    "Leo": [
        ("Regulus", "Denebola"),
    ],
    "Scorpius": [
        ("Dschubba", "Antares"),
        ("Antares", "Shaula"),
        ("Antares", "Sargas"),
    ],
    "Summer Triangle": [
        ("Vega", "Deneb"),
        ("Deneb", "Altair"),
        ("Altair", "Vega"),
    ],
    "Ursa Minor": [
        ("Polaris", "Kochab"),
    ],
}

# Reverse lookup: star name → list of constellations
STAR_CONSTELLATION = {}
for _const_name, _edges in CONSTELLATIONS.items():
    for _a, _b in _edges:
        STAR_CONSTELLATION.setdefault(_a, []).append(_const_name)
        STAR_CONSTELLATION.setdefault(_b, []).append(_const_name)
# Deduplicate
for _k in STAR_CONSTELLATION:
    STAR_CONSTELLATION[_k] = list(dict.fromkeys(STAR_CONSTELLATION[_k]))
