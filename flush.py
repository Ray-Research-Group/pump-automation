import sys
sys.path.insert(0, 'src')

import signal
from pump_controller import PumpController

ctrl = None

def signal_handler(signum, frame):
    """Called when user presses Ctrl+C."""
    print('\n[KEYBOARD INTERRUPT] Stopping all pumps...')
    if ctrl:
        ctrl.stop_all()
        ctrl.close_all()
    print('[CLOSED] All connections closed.')
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

ctrl = PumpController(log_file='experiment.log')

ctrl.add_harvard('pump_a', port='COM6')
ctrl.add_new_era('pump_b', port='COM7', address=0)
ctrl.add_new_era('pump_c', port='COM7', address=1)

try:
    # 10 uL/min for 30 minutes
    # Total volume = 300 uL = 0.3 mL per pump

    ctrl.run_parallel([
        {
            'pump_id': 'pump_a',
            'rate': 40,
            'units': 'ul/min',
            'volume': 1,
            'diameter_mm': 12.36,
            'direction': 'infuse'
        },
        {
            'pump_id': 'pump_b',
            'rate': 40,
            'units': 'ul/min',
            'volume': 1,
            'diameter_mm': 12.36,
            'direction': 'infuse'
        },
        {
            'pump_id': 'pump_c',
            'rate': 40,
            'units': 'ul/min',
            'volume': 1,
            'diameter_mm': 12.36,
            'direction': 'infuse'
        }
    ])

    print("All pumps completed successfully.")

except Exception as e:
    print(f'Experiment error: {e}')
    ctrl.stop_all()

finally:
    ctrl.close_all()