"""
Example: Graceful Ctrl+C handling for pump experiments.

Press Ctrl+C at any time to stop all pumps and exit cleanly.
This is the pattern to use in your own orchestrate.py scripts.
"""

import sys
sys.path.insert(0, '..')

import signal
from pump_controller import PumpController


def signal_handler(signum, frame):
    """Called when user presses Ctrl+C."""
    print('\n\n[KEYBOARD INTERRUPT] Stopping all pumps...')
    ctrl.stop_all()
    ctrl.close_all()
    print('[CLOSED] All connections closed.')
    sys.exit(0)


# Register the Ctrl+C handler
signal.signal(signal.SIGINT, signal_handler)

# Your experiment code here
ctrl = PumpController(log_file='experiment.log')

try:
    ctrl.add_harvard('pump_a', port='COM6')
    ctrl.add_new_era('pump_b', port='COM7', address=0)
    ctrl.add_new_era('pump_c', port='COM7', address=1)

    # Example: run all three pumps for 1 minute
    print('Starting experiment. Press Ctrl+C to stop.')
    ctrl.run_parallel([
        {'pump_id': 'pump_a', 'rate': 0.5, 'units': 'ml/min',
         'volume': 0.5, 'diameter_mm': 12.36, 'direction': 'infuse'},
        {'pump_id': 'pump_b', 'rate': 0.1, 'units': 'ml/min',
         'volume': 0.5, 'diameter_mm': 12.36, 'direction': 'infuse'},
        {'pump_id': 'pump_c', 'rate': 0.1, 'units': 'ml/min',
         'volume': 0.5, 'diameter_mm': 12.36, 'direction': 'infuse'},
    ])
    print('Experiment complete.')

except KeyboardInterrupt:
    # signal_handler catches Ctrl+C before this, but belt and suspenders
    print('\n[ERROR] Interrupted unexpectedly.')
    ctrl.stop_all()
    ctrl.close_all()
    sys.exit(1)

except Exception as e:
    print(f'[ERROR] {e}')
    ctrl.stop_all()
    ctrl.close_all()
    sys.exit(1)

finally:
    ctrl.close_all()
