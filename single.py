import sys
sys.path.insert(0, 'src')

import signal
from pump_controller import PumpController

ctrl = None

def signal_handler(signum, frame):
    """Called when user presses Ctrl+C."""
    print('\n[KEYBOARD INTERRUPT] Stopping pump...')
    if ctrl:
        ctrl.stop_all()
        ctrl.close_all()
    print('[CLOSED] All connections closed.')
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

ctrl = PumpController(log_file='experiment.log')

# Harvard Apparatus Pump 11 Elite
ctrl.add_harvard('pump_a', port='COM6')

try:
    print("Starting infusion...")

    # Infuse 1 mL at 20 µL/min
    ctrl.infuse(
        pump_id='pump_a',
        rate=15,
        units='ul/min',
        volume=1.0,      # mL
        diameter_mm=12.36
    )

    print("Infusion complete.")

except Exception as e:
    print(f'Experiment error: {e}')
    ctrl.stop_all()

finally:
    ctrl.close_all()