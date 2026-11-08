"""
High-precision ephemeris sheet for one date and place (PDF export).

A side script, independent of the application: it uses Skyfield and the JPL DE421 ephemeris,
which Skyfield downloads by itself at the first run (de421.bsp, ~17 MB).

    pip install skyfield fpdf2
    python scripts/fiche_haute_precision.py
"""
from skyfield.api import load, wgs84
from skyfield import almanac
from fpdf import FPDF
import math

# --- CONFIGURATION ---
DATE_CALCUL = "2026-03-23"
LATITUDE = 49.6337
LONGITUDE = -1.6221
ALTITUDE = 5.0

def format_ra(ra):
    h, m, s = ra.hms()
    return f"+{int(h):02d}:{int(m):02d}:{s:06.3f}"

def format_dec(dec):
    d, m, s = dec.dms()
    sign = "+" if d >= 0 and dec.radians >= 0 else "-"
    return f"{sign}{abs(int(d)):02d}:{int(m):02d}:{s:05.2f}"

def get_events(ts, eph, body, topos_wgs84, t0, t1):
    """
    topos_wgs84 must be the bare wgs84.latlon object for the almanac.
    """
    t_rise, t_set, t_transit = "N/A", "N/A", "N/A"
    
    # Rises and sets
    f_rs, edges_rs = almanac.find_discrete(t0, t1, almanac.risings_and_settings(eph, body, topos_wgs84))
    for t, is_rise in zip(f_rs, edges_rs):
        time_str = t.utc_strftime('%H:%M') + " UTC"
        if is_rise:
            t_rise = time_str
        else:
            t_set = time_str

    # Transit (meridian passage)
    f_tr, edges_tr = almanac.find_discrete(t0, t1, almanac.meridian_transits(eph, body, topos_wgs84))
    for t, is_transit in zip(f_tr, edges_tr):
        if is_transit == 1: 
            t_transit = t.utc_strftime('%H:%M') + " UTC"

    return t_rise, t_transit, t_set

def generate_pro_pdf():
    print("[*] Loading the Skyfield engine (JPL DE421)...")
    eph = load('de421.bsp')
    ts = load.timescale()
    
    earth, sun, moon = eph['earth'], eph['sun'], eph['moon']
    
    # The place itself, for the almanac
    cherbourg_topos = wgs84.latlon(LATITUDE, LONGITUDE, elevation_m=ALTITUDE)
    # The full vector (Earth -> Cherbourg), for the observation
    cherbourg_obs = earth + cherbourg_topos
    
    # Dates of the calculation (t0 to t1 for the events of the day)
    t0 = ts.utc(2026, 3, 23, 0, 0, 0)
    t1 = ts.utc(2026, 3, 24, 0, 0, 0)
    # Date of the physical values, at noon
    t_12h = ts.utc(2026, 3, 23, 12, 0, 0)
    
    print("[*] Computing the apparent topocentric ephemerides for Cherbourg...")
    
    # --- SUN ---
    # cherbourg_obs for the position
    sun_app = cherbourg_obs.at(t_12h).observe(sun).apparent()
    sun_ra, sun_dec, sun_dist = sun_app.radec(epoch='date')
    # cherbourg_topos for the events (almanac)
    sun_rise, sun_transit, sun_set = get_events(ts, eph, sun, cherbourg_topos, t0, t1)
    sun_diam = (1392700 / sun_dist.km) * (180 / math.pi) * 60
    
    # --- MOON ---
    moon_app = cherbourg_obs.at(t_12h).observe(moon).apparent()
    moon_ra, moon_dec, moon_dist = moon_app.radec(epoch='date')
    moon_rise, moon_transit, moon_set = get_events(ts, eph, moon, cherbourg_topos, t0, t1)
    moon_diam = (3474.8 / moon_dist.km) * (180 / math.pi) * 60
    moon_phase = almanac.phase_angle(eph, 'moon', t_12h).degrees
    
    # --- THE ASCII CONTENT ---
    ascii_content = f"""
======================================================================
              * A S T R O N O M I C A L   B U L L E T I N *
======================================================================
 Place        : CHERBOURG-EN-COTENTIN (Lat: {LATITUDE} N, Lon: {abs(LONGITUDE)} W)
 Date         : {DATE_CALCUL}
 Computation  : Skyfield engine (offline) - apparent topocentric
----------------------------------------------------------------------

 [ S U N ]
      \\ | /       * DAILY MOTION
    '- ( ) -'       Rise      : {sun_rise:<10} 
      / | \\         Transit   : {sun_transit:<10} 
                    Set       : {sun_set:<10} 
                    
                  * PHYSICAL DATA (AT 12:00 UTC)
                    Right ascension  : {format_ra(sun_ra)}
                    Declination      : {format_dec(sun_dec)}
                    Distance (Earth) : {sun_dist.au:.16f} AU
                    Apparent diam.   : {sun_diam:.1f}'

----------------------------------------------------------------------

 [ M O O N ]
       _.._       * DAILY MOTION
     /   a \\        Rise      : {moon_rise:<10} 
     \\  ~  /        Transit   : {moon_transit:<10} 
       \\._/         Set       : {moon_set:<10} 
                    
                  * PHYSICAL DATA (AT 12:00 UTC)
                    Right ascension  : {format_ra(moon_ra)}
                    Declination      : {format_dec(moon_dec)}
                    Distance (Earth) : {moon_dist.au:.16f} AU
                    Apparent diam.   : {moon_diam:.1f}'
                    Phase angle      : {moon_phase:.1f} deg

======================================================================
 Generator    : Celeste_App v_PRO (offline & high precision)
======================================================================
"""

    print("[*] Writing the PDF file...")
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font("Courier", size=10)
    
    for line in ascii_content.split('\n'):
        pdf.cell(0, 5, txt=line, ln=True, align='L')
        
    filename = f"Ephemerides_Pro_Cherbourg_{DATE_CALCUL}.pdf"
    pdf.output(filename)
    print(f"\n[DONE] The PDF '{filename}' is ready.")

if __name__ == "__main__":
    generate_pro_pdf()