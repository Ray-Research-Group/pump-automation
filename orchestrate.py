import sys
import signal
sys.path.insert(0, 'src')
from pump_controller import PumpController

ctrl = None

def signal_handler(signum, frame):
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
    pass

except Exception as e:
    print(f'Experiment error: {e}')
    ctrl.stop_all()

finally:
    ctrl.close_all()
