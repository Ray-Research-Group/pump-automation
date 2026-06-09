"""
Comprehensive hardware test. Run on the lab machine:  python orchestrate.py
Paste the full output back. This validates the whole chain — connection,
diameter, rate/volume limit checks, a real low-rate dispense, and that
out-of-range values fail loudly instead of running wrong.

Nothing here pumps more than ~1 mL or runs longer than a few seconds.
Adjust DIAMETER_MM / PORTS / ADDRESSES at the top if your setup differs.
"""

import traceback
from pump_controller import PumpController
from pump_limits import (
    harvard_rate_limits_ul_min, newera_max_rate_ul_min,
    RateOutOfRange, VolumeOutOfRange,
)

# ── CONFIG — edit if your hardware differs ────────────────────────────────────
DIAMETER_MM   = 12.36
HARVARD_PORT  = 'COM6'
NEWERA_PORT   = 'COM7'
NEWERA_ADDRS  = [0, 1]          # pump_b, pump_c
TEST_VOLUME_ML = 0.5            # small, safe dispense
# Pick a rate that is valid on BOTH pumps at this diameter (New Era is the limit).
SAFE_NEWERA_UL_MIN = newera_max_rate_ul_min(DIAMETER_MM) * 0.5   # half of max, safe
SAFE_RATE_ML_MIN   = round(SAFE_NEWERA_UL_MIN / 1000.0, 4)


def banner(t):
    print('\n' + '=' * 70 + f'\n{t}\n' + '=' * 70)

def ok(msg):   print(f'  [PASS] {msg}')
def bad(msg):  print(f'  [FAIL] {msg}')
def info(msg): print(f'  ...... {msg}')


def expect_raises(label, fn, exc):
    """Pass if fn() raises exc; fail if it runs or raises something else."""
    try:
        fn()
        bad(f'{label}: expected {exc.__name__}, but it was ACCEPTED (silent bug!)')
    except exc as e:
        ok(f'{label}: rejected as expected — {e}')
    except Exception as e:
        bad(f'{label}: raised {type(e).__name__} instead of {exc.__name__} — {e}')


def main():
    banner('COMPUTED LIMITS AT DIAMETER %.3f mm' % DIAMETER_MM)
    h_lo, h_hi = harvard_rate_limits_ul_min(DIAMETER_MM)
    n_hi = newera_max_rate_ul_min(DIAMETER_MM)
    info(f'Harvard allowed:  {h_lo:.4g} – {h_hi:.4g} µL/min ({h_lo/1000:.4g} – {h_hi/1000:.4g} mL/min)')
    info(f'New Era max:      {n_hi:.4g} µL/min ({n_hi/1000:.4g} mL/min)')
    info(f'Safe test rate:   {SAFE_RATE_ML_MIN} mL/min ({SAFE_NEWERA_UL_MIN:.4g} µL/min), volume {TEST_VOLUME_ML} mL')

    # ── LIMIT CHECKS (no hardware needed — pure logic) ────────────────────────
    banner('LIMIT CHECKS — these must REJECT loudly')
    from new_era import NewEraPump
    from harvard_elite import HarvardElite

    # New Era: your original values must be rejected
    np_ = NewEraPump.__new__(NewEraPump)
    np_._diameter_mm = DIAMETER_MM
    expect_raises('New Era 10.76 mL/min', lambda: np_.set_rate(10.76, 'ml/min'), RateOutOfRange)
    expect_raises('New Era 1.076 mL/min', lambda: np_.set_rate(1.076, 'ml/min'), RateOutOfRange)
    expect_raises('New Era volume 107.6 mL', lambda: np_.set_volume(107600), VolumeOutOfRange)

    # New Era: safe value must pass the check (will try to send — guard against no serial)
    try:
        from pump_limits import check_newera_rate, check_newera_volume
        check_newera_rate(SAFE_NEWERA_UL_MIN, DIAMETER_MM)
        check_newera_volume(TEST_VOLUME_ML * 1000)
        ok(f'New Era {SAFE_RATE_ML_MIN} mL/min + {TEST_VOLUME_ML} mL: within limits')
    except Exception as e:
        bad(f'safe value unexpectedly rejected — {e}')

    # Harvard: 10.76 should be allowed (well under ~19 mL/min)
    from pump_limits import check_harvard_rate
    try:
        check_harvard_rate(10760, DIAMETER_MM)
        ok('Harvard 10.76 mL/min: within limits (as expected)')
    except Exception as e:
        bad(f'Harvard 10.76 unexpectedly rejected — {e}')
    expect_raises('Harvard 50 mL/min', lambda: check_harvard_rate(50000, DIAMETER_MM), RateOutOfRange)

    # ── HARDWARE TEST ─────────────────────────────────────────────────────────
    banner('HARDWARE — connect, configure, run a small dispense')
    ctrl = PumpController(log_file='experiment.log')
    try:
        info('Registering pumps...')
        ctrl.add_harvard('pump_a', port=HARVARD_PORT)
        for i, addr in enumerate(NEWERA_ADDRS):
            ctrl.add_new_era(f'pump_{chr(98+i)}', port=NEWERA_PORT, address=addr)
        ok('All pumps registered (serial ports opened)')

        info('Reading status from each pump...')
        for pid in ['pump_a'] + [f'pump_{chr(98+i)}' for i in range(len(NEWERA_ADDRS))]:
            try:
                st = ctrl.get_status(pid)
                ok(f'{pid} responded: {st}')
            except Exception as e:
                bad(f'{pid} status failed — {e}')

        info(f'Running a safe parallel dispense: {SAFE_RATE_ML_MIN} mL/min, {TEST_VOLUME_ML} mL each...')
        configs = [
            {'pump_id': 'pump_a', 'rate': SAFE_RATE_ML_MIN, 'units': 'ml/min',
             'volume': TEST_VOLUME_ML, 'diameter_mm': DIAMETER_MM, 'direction': 'infuse'},
        ]
        for i in range(len(NEWERA_ADDRS)):
            configs.append({'pump_id': f'pump_{chr(98+i)}', 'rate': SAFE_RATE_ML_MIN,
                            'units': 'ml/min', 'volume': TEST_VOLUME_ML,
                            'diameter_mm': DIAMETER_MM, 'direction': 'infuse'})
        ctrl.run_parallel(configs)
        ok('Parallel dispense completed without error')

        info('Reading dispensed volume from each pump...')
        for pid in ['pump_a'] + [f'pump_{chr(98+i)}' for i in range(len(NEWERA_ADDRS))]:
            try:
                v = ctrl.get_volume_dispensed(pid)
                ok(f'{pid} dispensed: {v}')
            except Exception as e:
                bad(f'{pid} volume readback failed — {e}')

        info('Now confirming an OUT-OF-RANGE run fails loudly on real hardware...')
        try:
            ctrl.run_parallel([
                {'pump_id': 'pump_b', 'rate': 10.76, 'units': 'ml/min',
                 'volume': TEST_VOLUME_ML, 'diameter_mm': DIAMETER_MM, 'direction': 'infuse'},
            ])
            bad('out-of-range run was ACCEPTED — limit check did not fire on hardware path!')
        except Exception as e:
            ok(f'out-of-range run rejected loudly — {type(e).__name__}: {e}')

    except Exception:
        bad('UNEXPECTED FAILURE:')
        traceback.print_exc()
        ctrl.stop_all()
    finally:
        ctrl.close_all()
        banner('TEST COMPLETE — paste everything above')


if __name__ == '__main__':
    main()
