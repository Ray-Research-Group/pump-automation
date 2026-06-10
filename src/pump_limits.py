"""
Flow-rate and volume limit checks for both pumps.

Both pumps compute flow from pusher velocity times syringe cross-sectional area,
so the achievable flow rate depends on the syringe diameter. Pushing a rate the
mechanism cannot reach gets silently mangled or rejected by the firmware. These
functions compute the real limits from diameter and raise loudly when a request
is out of range, before anything hits the serial port.

Sources:
  Harvard Pump 11 Elite — Harvard.txt, spec table + Appendix B.
    Limits come from pusher travel rate (min 0.000153 mm/min, max 159.0 mm/min).
    Validated against Appendix B to 4 significant figures.
  New Era NE-4002X — NE4002X.txt (www.SyringePump.com rates sheet).
    Per-diameter max rate table; absolute max 1226 µL/min; 4-digit field caps
    a single "volume to be dispensed" at 9999 µL (~10 mL), µL units only.
"""

import math


class RateOutOfRange(ValueError):
    """Requested flow rate is outside the pump's mechanical limits."""


class VolumeOutOfRange(ValueError):
    """Requested volume is outside the pump's settable range."""


def _area_mm2(diameter_mm):
    return math.pi / 4.0 * diameter_mm * diameter_mm


# ── HARVARD PUMP 11 ELITE ─────────────────────────────────────────────────────
# Flow = pusher_velocity * cross-sectional area.
# pusher units mm/min, area mm^2 -> mm^3/min = µL/min.

HARVARD_PUSHER_MIN_MM_MIN = 0.000153   # back-solved from Appendix B, validated
HARVARD_PUSHER_MAX_MM_MIN = 159.0      # spec table "Pusher Travel Rate: Maximum"


def harvard_rate_limits_ul_min(diameter_mm):
    """Return (min_ul_min, max_ul_min) achievable at this diameter."""
    area = _area_mm2(diameter_mm)
    return (HARVARD_PUSHER_MIN_MM_MIN * area, HARVARD_PUSHER_MAX_MM_MIN * area)


# ── NEW ERA NE-4002X ──────────────────────────────────────────────────────────
# Per-diameter max rate (µL/min) straight from the spec sheet. The achievable
# max is the table value, never above the absolute ceiling.

NEWERA_ABS_MAX_UL_MIN = 1226.0     # B-D 60 mL, fastest any syringe goes
NEWERA_MAX_VOLUME_UL = 9999.0      # 4-digit field, µL only on firmware 4.670

# (inside_diameter_mm, max_rate_ul_min) — parsed directly from NE4002X.txt.
# Values are pusher-limited maxima; some exceed NEWERA_ABS_MAX_UL_MIN and are
# clamped to it by newera_max_rate_ul_min.
NEWERA_MAX_RATE_TABLE = [
    (4.69, 38.16), (4.699, 38.31), (4.7, 38.33), (5.74, 57.17), (6.7, 77.89),
    (8.585, 127.8), (8.91, 137.7), (8.941, 138.7), (8.95, 138.9), (9.06, 142.4),
    (9.538, 157.8), (9.65, 161.5), (11.75, 239.5), (11.99, 249.4), (12.45, 268.9),
    (12.7, 279.8), (13.0, 293.2), (14.43, 361.3), (14.67, 373.4), (15.72, 428.8),
    (15.8, 433.1), (15.9, 438.6), (19.05, 629.7), (19.13, 635.0), (19.62, 667.9),
    (20.05, 697.5), (20.12, 702.4), (20.15, 704.5), (21.59, 808.8), (22.69, 893.3),
    (22.9, 909.9), (23.1, 925.9), (23.52, 959.9), (26.59, 1226.0), (26.64, 1231.0),
    (26.96, 1261.0), (28.6, 1419.0), (29.2, 1479.0), (29.7, 1530.0), (38.0, 2505.0),
]


def newera_max_rate_ul_min(diameter_mm):
    """
    Max achievable rate (µL/min) at this diameter. Interpolates between the two
    nearest table diameters, then clamps to the absolute pump ceiling.
    """
    tbl = sorted(NEWERA_MAX_RATE_TABLE)
    if diameter_mm <= tbl[0][0]:
        m = tbl[0][1]
    elif diameter_mm >= tbl[-1][0]:
        m = tbl[-1][1]
    else:
        lo = max(d for d, _ in tbl if d <= diameter_mm)
        hi = min(d for d, _ in tbl if d >= diameter_mm)
        lo_r = dict(tbl)[lo]
        hi_r = dict(tbl)[hi]
        if hi == lo:
            m = lo_r
        else:
            frac = (diameter_mm - lo) / (hi - lo)
            m = lo_r + frac * (hi_r - lo_r)
    return min(m, NEWERA_ABS_MAX_UL_MIN)


# ── PUBLIC CHECKS ─────────────────────────────────────────────────────────────

def check_harvard_rate(rate_ul_min, diameter_mm):
    lo, hi = harvard_rate_limits_ul_min(diameter_mm)
    if not (lo <= rate_ul_min <= hi):
        raise RateOutOfRange(
            f'Harvard: {rate_ul_min:.4g} µL/min is out of range at diameter '
            f'{diameter_mm} mm. Allowed {lo:.4g} – {hi:.4g} µL/min '
            f'({lo/1000:.4g} – {hi/1000:.4g} mL/min).'
        )


def check_newera_rate(rate_ul_min, diameter_mm):
    hi = newera_max_rate_ul_min(diameter_mm)
    if rate_ul_min > hi:
        raise RateOutOfRange(
            f'New Era: {rate_ul_min:.4g} µL/min exceeds the max {hi:.4g} µL/min '
            f'({hi/1000:.4g} mL/min) at diameter {diameter_mm} mm '
            f'(absolute pump max {NEWERA_ABS_MAX_UL_MIN:.0f} µL/min).'
        )


def check_newera_volume(volume_ul):
    if volume_ul > NEWERA_MAX_VOLUME_UL:
        raise VolumeOutOfRange(
            f'New Era: {volume_ul:.4g} µL exceeds the {NEWERA_MAX_VOLUME_UL:.0f} µL '
            f'(~10 mL) single-dispense ceiling. Use continuous mode or split it.'
        )
